import { useEffect, useMemo, useRef, useState } from 'react';
import { DEFAULT_DEPENDENCY_APPROACH } from '../dependencyApproaches';
import {
  ATTRIBUTE_FILTER_DIMENSION_VALUES,
  BASELINE_NONE_VALUE,
  COLOR_BY_OPTION_VALUES,
  LAYOUT_OPTION_VALUES,
  LINK_TYPE_OPTION_VALUES,
  GROUND_TRUTH_CURATED,
  RELATION_SUBTYPE_ALL_VALUE,
  buildComparisonLinks,
  buildDisplayedLinks,
  filterCrossSourceDependencyGraph,
  formatProposalFilterValue,
  formatSnapshotFilePart,
  getGroundTruthRelationSubtypeOptions,
  getDependencyNodeAttributeFallbackLabel,
  isCrossSourceDependencyEdge,
  normalizeImportedPositions,
  normalizeProposalId,
  normalizeCategory,
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
  const [linkSubtype, setLinkSubtype] = useState(RELATION_SUBTYPE_ALL_VALUE);
  const [baselineSubtype, setBaselineSubtype] = useState(RELATION_SUBTYPE_ALL_VALUE);
  const [layoutMode, setLayoutMode] = useState('balanced');
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [importedLayout, setImportedLayout] = useState(null);
  const [onlyCrossSource, setOnlyCrossSource] = useState(false);
  const [attributeFilterDimension, setAttributeFilterDimension] = useState('');
  const [attributeFilterValues, setAttributeFilterValues] = useState([]);
  const linksByType = data?.links || {};
  const groundTruthRelationSubtypeOptions = useMemo(
    () => getGroundTruthRelationSubtypeOptions(linksByType),
    [linksByType]
  );
  const validGroundTruthRelationSubtypeValues = useMemo(
    () => new Set(groundTruthRelationSubtypeOptions.map((option) => option.value)),
    [groundTruthRelationSubtypeOptions]
  );

  const isDifferentialMode = baselineType !== BASELINE_NONE_VALUE;

  useEffect(() => {
    if (!validGroundTruthRelationSubtypeValues.has(linkSubtype)) {
      setLinkSubtype(RELATION_SUBTYPE_ALL_VALUE);
    }
  }, [linkSubtype, validGroundTruthRelationSubtypeValues]);

  useEffect(() => {
    if (!validGroundTruthRelationSubtypeValues.has(baselineSubtype)) {
      setBaselineSubtype(RELATION_SUBTYPE_ALL_VALUE);
    }
  }, [baselineSubtype, validGroundTruthRelationSubtypeValues]);

  const baseNodes = useMemo(
    () => (Array.isArray(data?.nodes) ? data.nodes.map((node) => ({ ...node })) : []),
    [data]
  );

  const baseLinks = useMemo(() => {
    if (isDifferentialMode) {
      return buildComparisonLinks(data?.links || {}, linkType, baselineType, {
        approachRelationSubtype: linkType === GROUND_TRUTH_CURATED ? linkSubtype : RELATION_SUBTYPE_ALL_VALUE,
        baselineRelationSubtype: baselineType === GROUND_TRUTH_CURATED ? baselineSubtype : RELATION_SUBTYPE_ALL_VALUE,
      });
    }
    return buildDisplayedLinks(data?.links || {}, linkType, {
      relationSubtype: linkType === GROUND_TRUTH_CURATED ? linkSubtype : RELATION_SUBTYPE_ALL_VALUE,
    }).map((edge) => ({
      ...edge,
      comparisonStatus: 'approach_only',
    }));
  }, [baselineSubtype, baselineType, data, isDifferentialMode, linkSubtype, linkType]);

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

  const attributeFilterOptions = useMemo(() => {
    if (!attributeFilterDimension) {
      return [];
    }
    const fallbackLabel = getDependencyNodeAttributeFallbackLabel(attributeFilterDimension);
    const labels = Array.from(new Set(
      nodes.map((node) => normalizeCategory(node?.[attributeFilterDimension], fallbackLabel))
    ));
    labels.sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base', numeric: true }));
    return labels.map((label) => ({ label, value: label }));
  }, [attributeFilterDimension, nodes]);

  useEffect(() => {
    if (!attributeFilterDimension && attributeFilterValues.length > 0) {
      setAttributeFilterValues([]);
    }
  }, [attributeFilterDimension, attributeFilterValues]);

  useEffect(() => {
    if (attributeFilterValues.length === 0) {
      return;
    }
    const validValues = new Set(attributeFilterOptions.map((option) => option.value));
    const filteredValues = attributeFilterValues.filter((value) => validValues.has(value));
    if (filteredValues.length !== attributeFilterValues.length) {
      setAttributeFilterValues(filteredValues);
    }
  }, [attributeFilterOptions, attributeFilterValues]);

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

      const importedLinkSubtype = String(payload?.link_subtype || '').trim();
      setLinkSubtype(
        validGroundTruthRelationSubtypeValues.has(importedLinkSubtype)
          ? importedLinkSubtype
          : RELATION_SUBTYPE_ALL_VALUE
      );
      const importedBaselineSubtype = String(payload?.baseline_subtype || '').trim();
      setBaselineSubtype(
        validGroundTruthRelationSubtypeValues.has(importedBaselineSubtype)
          ? importedBaselineSubtype
          : RELATION_SUBTYPE_ALL_VALUE
      );

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

      const importedAttributeDimension = String(payload?.filter?.attribute_dimension || '').trim();
      if (ATTRIBUTE_FILTER_DIMENSION_VALUES.has(importedAttributeDimension)) {
        setAttributeFilterDimension(importedAttributeDimension);
      } else {
        setAttributeFilterDimension('');
      }

      if (Array.isArray(payload?.filter?.attribute_values)) {
        setAttributeFilterValues(
          payload.filter.attribute_values
            .map((value) => String(value).trim())
            .filter(Boolean)
        );
      } else {
        setAttributeFilterValues([]);
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
    linkSubtype,
    setLinkSubtype,
    baselineSubtype,
    setBaselineSubtype,
    groundTruthRelationSubtypeOptions,
    layoutMode,
    setLayoutMode,
    physicsEnabled,
    importedLayout,
    isDifferentialMode,
    onlyCrossSource,
    setOnlyCrossSource,
    attributeFilterDimension,
    setAttributeFilterDimension,
    attributeFilterValues,
    setAttributeFilterValues,
    attributeFilterOptions,
    canFilterCrossSource,
    nodes,
    links,
    linksByType,
    handleLayoutExport,
    handlePhysicsToggle,
    handleLayoutImportClick,
    handleLayoutImport,
  };
}
