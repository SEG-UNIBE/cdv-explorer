import { useEffect, useMemo, useRef, useState } from 'react';
import { DEFAULT_DEPENDENCY_APPROACH } from '../dependencyApproaches';
import {
  BASELINE_NONE_VALUE,
  COLOR_BY_OPTION_VALUES,
  LAYOUT_OPTION_VALUES,
  LINK_TYPE_OPTION_VALUES,
  buildComparisonLinks,
  buildDisplayedLinks,
  filterCrossSourceDependencyGraph,
  formatProposalFilterValue,
  formatSnapshotFilePart,
  isCrossSourceDependencyEdge,
  normalizeImportedPositions,
  normalizeProposalId,
} from './networkDiagramUtils';

export function useNetworkDiagramState({
  data,
  proposalFilterIds,
  snapshotLabel,
  ecosystem,
  setMinRelations,
  setIncludeConnections,
  setIncludeThresholdConnections,
  setProposalFilterText,
}) {
  const importInputRef = useRef(null);
  const physicsEnabledRef = useRef(true);
  const simulationRef = useRef(null);
  const redrawGraphRef = useRef(() => {});
  const exportPayloadRef = useRef(null);
  const updateExportPayloadRef = useRef(() => {});

  const [colorBy, setColorBy] = useState('layer');
  const [linkType, setLinkType] = useState(DEFAULT_DEPENDENCY_APPROACH);
  const [baselineType, setBaselineType] = useState(BASELINE_NONE_VALUE);
  const [layoutMode, setLayoutMode] = useState('balanced');
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [importedLayout, setImportedLayout] = useState(null);
  const [onlyCrossSource, setOnlyCrossSource] = useState(false);

  const isDifferentialMode = baselineType !== BASELINE_NONE_VALUE;

  const baseNodes = useMemo(
    () => (Array.isArray(data?.nodes) ? data.nodes.map((node) => ({ ...node })) : []),
    [data]
  );

  const baseLinks = useMemo(() => {
    if (isDifferentialMode) {
      return buildComparisonLinks(data?.links || {}, linkType, baselineType);
    }
    return buildDisplayedLinks(data?.links || {}, linkType).map((edge) => ({
      ...edge,
      comparisonStatus: 'approach_only',
    }));
  }, [baselineType, data, isDifferentialMode, linkType]);

  const canFilterCrossSource = useMemo(
    () => baseLinks.some(isCrossSourceDependencyEdge),
    [baseLinks]
  );

  useEffect(() => {
    if (!canFilterCrossSource && onlyCrossSource) {
      setOnlyCrossSource(false);
    }
  }, [canFilterCrossSource, onlyCrossSource]);

  const { nodes, links } = useMemo(() => {
    if (!onlyCrossSource || !canFilterCrossSource) {
      return { nodes: baseNodes, links: baseLinks };
    }
    return filterCrossSourceDependencyGraph(baseNodes, baseLinks);
  }, [baseLinks, baseNodes, canFilterCrossSource, onlyCrossSource]);

  useEffect(() => {
    physicsEnabledRef.current = physicsEnabled;

    const simulation = simulationRef.current;
    if (!simulation) {
      return;
    }

    if (physicsEnabled) {
      simulation.alpha(0.35).alphaTarget(0).restart();
      return;
    }

    simulation.alphaTarget(0);
    simulation.stop();
    redrawGraphRef.current();
    updateExportPayloadRef.current();
  }, [physicsEnabled]);

  const handleLayoutExport = () => {
    if (!exportPayloadRef.current) {
      return;
    }

    const focusSuffix = (proposalFilterIds || [])
      .map((value) => (
        value && typeof value === 'object'
          ? formatProposalFilterValue(value, ecosystem)
          : normalizeProposalId(value, ecosystem)
      ))
      .filter(Boolean)
      .sort((left, right) => left.localeCompare(right, undefined, { numeric: true }))
      .join('_') || 'all';
    const snapshotSlug = formatSnapshotFilePart(snapshotLabel);
    const fileName = `dependency_layout_${snapshotSlug}_${focusSuffix}.json`;
    const blob = new Blob([`${JSON.stringify(exportPayloadRef.current, null, 2)}\n`], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(url);
  };

  const handlePhysicsToggle = () => {
    setPhysicsEnabled((current) => !current);
  };

  const handleLayoutImportClick = () => {
    importInputRef.current?.click();
  };

  const handleLayoutImport = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';

    if (!file) {
      return;
    }

    try {
      const payload = JSON.parse(await file.text());
      const importedPositions = normalizeImportedPositions(payload);

      if (Object.keys(importedPositions).length === 0) {
        throw new Error('The selected file does not contain any layout positions.');
      }

      if (COLOR_BY_OPTION_VALUES.has(payload?.color_by)) {
        setColorBy(payload.color_by);
      }

      if (LINK_TYPE_OPTION_VALUES.has(payload?.link_type)) {
        setLinkType(payload.link_type);
      }

      const importedBaselineType = payload?.baseline_type;
      if (importedBaselineType == null || importedBaselineType === BASELINE_NONE_VALUE) {
        setBaselineType(BASELINE_NONE_VALUE);
      } else if (LINK_TYPE_OPTION_VALUES.has(importedBaselineType)) {
        setBaselineType(importedBaselineType);
      }

      if (LAYOUT_OPTION_VALUES.has(payload?.layout_mode)) {
        setLayoutMode(payload.layout_mode);
      }

      const importedMinRelations = payload?.filter?.min_relations;
      if (importedMinRelations != null && setMinRelations) {
        setMinRelations(String(Math.max(0, Number(importedMinRelations) || 0)));
      }

      if (typeof payload?.filter?.include_threshold_connections === 'boolean') {
        setIncludeThresholdConnections?.(payload.filter.include_threshold_connections);
      }

      if (typeof payload?.filter?.include_connections === 'boolean') {
        setIncludeConnections?.(payload.filter.include_connections);
      }

      if (Array.isArray(payload?.filter?.proposal_ids)) {
        setProposalFilterText?.(payload.filter.proposal_ids.map((value) => String(value)).join(','));
      }

      if (typeof payload?.filter?.only_cross_source === 'boolean') {
        setOnlyCrossSource(payload.filter.only_cross_source);
      }

      setImportedLayout({
        fileName: file.name,
        positions: importedPositions,
      });
      setPhysicsEnabled(false);
    } catch (error) {
      window.alert(
        error instanceof Error
          ? `Could not import layout JSON: ${error.message}`
          : 'Could not import layout JSON.'
      );
    }
  };

  return {
    importInputRef,
    physicsEnabledRef,
    simulationRef,
    redrawGraphRef,
    exportPayloadRef,
    updateExportPayloadRef,
    colorBy,
    setColorBy,
    linkType,
    setLinkType,
    baselineType,
    setBaselineType,
    layoutMode,
    setLayoutMode,
    physicsEnabled,
    importedLayout,
    isDifferentialMode,
    onlyCrossSource,
    setOnlyCrossSource,
    canFilterCrossSource,
    nodes,
    links,
    handleLayoutExport,
    handlePhysicsToggle,
    handleLayoutImportClick,
    handleLayoutImport,
  };
}
