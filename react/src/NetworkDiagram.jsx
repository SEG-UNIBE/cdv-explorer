import * as d3 from 'd3';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Dropdown } from 'primereact/dropdown';
import { InputText } from 'primereact/inputtext';
import { getClassificationColorMap } from './classificationColors';
import {
  BODY_EXTRACTED_LLM,
  BODY_EXTRACTED_REGEX,
  DEFAULT_DEPENDENCY_APPROACH,
  LINK_TYPE_OPTIONS as DEPENDENCY_LINK_TYPE_OPTIONS,
  PREAMBLE_EXTRACTED,
} from './dependencyApproaches';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { buildProposalRefKeySet, nodeRefKey } from './dashboard/dashboardData';
import { formatProposalReference, getProposalUrl, normalizeProposalId } from './proposalLinks';

export const LINK_TYPE_OPTIONS = DEPENDENCY_LINK_TYPE_OPTIONS;

const BASELINE_NONE_VALUE = '__none__';

const BASELINE_OPTIONS = [
  { label: '(none)', value: BASELINE_NONE_VALUE },
  ...LINK_TYPE_OPTIONS,
];

const LAYOUT_OPTIONS = [
  { label: 'Balanced', value: 'balanced' },
  { label: 'Clustered', value: 'clustered' },
  { label: 'Spread', value: 'spread' },
];

const COLOR_BY_OPTIONS = [
  { label: 'Layer', value: 'layer' },
  { label: 'Status', value: 'status' },
  { label: 'Type', value: 'type' },
];

const COLOR_BY_OPTION_VALUES = new Set(COLOR_BY_OPTIONS.map((option) => option.value));
const LAYOUT_OPTION_VALUES = new Set(LAYOUT_OPTIONS.map((option) => option.value));
const LINK_TYPE_OPTION_VALUES = new Set(LINK_TYPE_OPTIONS.map((option) => option.value));

const EXPLICIT_DEPENDENCY_COLORS = {
  requires: '#667085',
  replaces: '#667085',
  proposed_replacement: '#667085',
};

const DEFAULT_EDGE_COLORS = {
  [BODY_EXTRACTED_REGEX]: '#939AA9',
  [BODY_EXTRACTED_LLM]: '#939AA9',
};

const DIFFERENTIAL_EDGE_COLORS = {
  approach_only: '#b8c0cc',
  overlap: '#2f9e44',
  baseline_only: '#d94841',
};

const DEFAULT_LINK_WIDTH = 1.8;
const ACTIVE_LINK_WIDTH = 2.8;
const PINNED_LINK_WIDTH = 2.6;

const EXPLICIT_DEPENDENCY_STYLES = {
  requires: null,
  replaces: '8 5',
  proposed_replacement: '2.5 4',
};

function getLinkTypeLabel(linkType) {
  return LINK_TYPE_OPTIONS.find((option) => option.value === linkType)?.label || linkType;
}

function buildEdgeKey(source, target) {
  return `${String(source)}->${String(target)}`;
}

function nodeGraphId(node) {
  if (!node || typeof node !== 'object') {
    return String(node ?? '');
  }
  if (node.graphId != null) {
    return String(node.graphId);
  }
  const sourcePart = String(node.graphSource || node.source || '').trim();
  const idPart = String(node.id ?? '').trim();
  return sourcePart ? `${sourcePart}:${idPart}` : idPart;
}

function edgeGraphSourceId(edge) {
  if (edge?.source && typeof edge.source === 'object') {
    return nodeGraphId(edge.source);
  }
  return String(edge?.sourceKey ?? edge?.sourceGraphId ?? edge?.source ?? '');
}

function edgeGraphTargetId(edge) {
  if (edge?.target && typeof edge.target === 'object') {
    return nodeGraphId(edge.target);
  }
  return String(edge?.targetKey ?? edge?.targetGraphId ?? edge?.target ?? '');
}

function edgeSourceProposalId(edge) {
  if (edge?.source && typeof edge.source === 'object') {
    return String(edge.source.id ?? '');
  }
  return String(edge?.sourceProposalId ?? edge?.source ?? '');
}

function edgeTargetProposalId(edge) {
  if (edge?.target && typeof edge.target === 'object') {
    return String(edge.target.id ?? '');
  }
  return String(edge?.targetProposalId ?? edge?.target ?? '');
}

function edgeSourceSourceId(edge) {
  if (edge?.source && typeof edge.source === 'object') {
    return String(edge.source.source || '');
  }
  return String(edge?.sourceSourceId || '');
}

function edgeTargetSourceId(edge) {
  if (edge?.target && typeof edge.target === 'object') {
    return String(edge.target.source || '');
  }
  return String(edge?.targetSourceId || '');
}

function normalizeCategory(value, fallbackLabel) {
  const text = String(value ?? '').trim();
  return text || fallbackLabel;
}

function getSourceScopedEcosystem(ecosystem, sourceId) {
  const source = ecosystem?.sources?.[sourceId];
  return source ? { ...ecosystem, ...source } : ecosystem;
}

function formatProposalFilterValue(value, ecosystem) {
  if (value && typeof value === 'object') {
    return formatProposalReference(
      value.id,
      getSourceScopedEcosystem(ecosystem, value.source)
    );
  }
  return formatProposalReference(value, ecosystem);
}

function sanitizeFilePart(value, fallback = 'unknown') {
  const text = String(value ?? '')
    .trim()
    .replace(/[^a-z0-9._-]+/gi, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  return text || fallback;
}

function formatSnapshotFilePart(value) {
  const text = String(value ?? '').trim();
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) {
    return `${match[1].slice(2)}${match[2]}${match[3]}`;
  }
  return sanitizeFilePart(text, 'snapshot');
}

function normalizeImportedPositions(payload) {
  const normalizedPositions = {};
  const rawPositions = payload?.positions;

  if (rawPositions && typeof rawPositions === 'object' && !Array.isArray(rawPositions)) {
    Object.entries(rawPositions).forEach(([nodeId, coords]) => {
      if (!Array.isArray(coords) || coords.length < 2) {
        return;
      }

      const xCoord = Number(coords[0]);
      const yCoord = Number(coords[1]);
      if (!Number.isFinite(xCoord) || !Number.isFinite(yCoord)) {
        return;
      }

      normalizedPositions[String(nodeId)] = [xCoord, yCoord];
    });
  }

  if (Object.keys(normalizedPositions).length > 0) {
    return normalizedPositions;
  }

  if (Array.isArray(payload?.nodes)) {
    payload.nodes.forEach((node) => {
      const nodeId = node?.id;
      const xCoord = Number(node?.x);
      const yCoord = Number(node?.y);

      if (nodeId == null || !Number.isFinite(xCoord) || !Number.isFinite(yCoord)) {
        return;
      }

      normalizedPositions[String(nodeId)] = [xCoord, yCoord];
    });
  }

  return normalizedPositions;
}

function buildDisplayedLinks(linksByType, linkType) {
  if (linkType === PREAMBLE_EXTRACTED) {
    return ['requires', 'replaces', 'proposed_replacement']
      .flatMap((relationType) => (linksByType?.[relationType] || []).map((edge, index) => ({
        ...edge,
        relationType,
        key: `${relationType}-${edgeGraphSourceId(edge)}-${edgeGraphTargetId(edge)}-${index}`,
      })));
  }

  return (linksByType?.[linkType] || []).map((edge, index) => ({
    ...edge,
    relationType: linkType,
    key: `${linkType}-${edgeGraphSourceId(edge)}-${edgeGraphTargetId(edge)}-${index}`,
  }));
}

function getLinkSetForType(linksByType, linkType) {
  if (linkType === PREAMBLE_EXTRACTED) {
    return ['requires', 'replaces', 'proposed_replacement']
      .flatMap((relationType) => (linksByType?.[relationType] || []).map((edge) => ({
        ...edge,
        source: edgeGraphSourceId(edge),
        target: edgeGraphTargetId(edge),
      })));
  }

  return (linksByType?.[linkType] || []).map((edge) => ({
    ...edge,
    source: edgeGraphSourceId(edge),
    target: edgeGraphTargetId(edge),
  }));
}

function buildComparisonLinks(linksByType, approachType, baselineType) {
  const approachEdges = getLinkSetForType(linksByType, approachType);
  const baselineEdges = getLinkSetForType(linksByType, baselineType);
  const approachByKey = new Map(approachEdges.map((edge) => [buildEdgeKey(edge.source, edge.target), edge]));
  const baselineByKey = new Map(baselineEdges.map((edge) => [buildEdgeKey(edge.source, edge.target), edge]));
  const approachKeys = new Set(approachByKey.keys());
  const baselineKeys = new Set(baselineByKey.keys());
  const combinedKeys = new Set([...approachKeys, ...baselineKeys]);

  return Array.from(combinedKeys).map((edgeKey, index) => {
    const [source, target] = edgeKey.split('->');
    const sourceEdge = approachByKey.get(edgeKey) || baselineByKey.get(edgeKey) || {};
    let comparisonStatus = 'approach_only';

    if (approachKeys.has(edgeKey) && baselineKeys.has(edgeKey)) {
      comparisonStatus = 'overlap';
    } else if (baselineKeys.has(edgeKey)) {
      comparisonStatus = 'baseline_only';
    }

    return {
      ...sourceEdge,
      source,
      target,
      relationType: approachType,
      comparisonStatus,
      key: `${approachType}-${baselineType}-${comparisonStatus}-${source}-${target}-${index}`,
    };
  });
}

export const NetworkDiagram = ({
  width = 1200,
  height = 800,
  data,
  highlightProposal = '',
  proposalShortPlural = 'IPs',
  minRelations = '0',
  setMinRelations,
  proposalFilterIds = [],
  setProposalFilterText,
  includeConnections = true,
  setIncludeConnections,
  includeThresholdConnections = false,
  setIncludeThresholdConnections,
}) => {
  const ref = useRef();
  const legendRef = useRef();
  const importInputRef = useRef(null);
  const exportPayloadRef = useRef(null);
  const simulationRef = useRef(null);
  const redrawGraphRef = useRef(() => {});
  const updateExportPayloadRef = useRef(() => {});
  const physicsEnabledRef = useRef(true);
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();
  const [colorBy, setColorBy] = useState('layer');
  const [linkType, setLinkType] = useState(DEFAULT_DEPENDENCY_APPROACH);
  const [baselineType, setBaselineType] = useState(BASELINE_NONE_VALUE);
  const [layoutMode, setLayoutMode] = useState('balanced');
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [importedLayout, setImportedLayout] = useState(null);
  const isDifferentialMode = baselineType !== BASELINE_NONE_VALUE;

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

  const nodes = useMemo(
    () => (Array.isArray(data?.nodes) ? data.nodes.map((node) => ({ ...node })) : []),
    [data]
  );

  const links = useMemo(() => {
    if (isDifferentialMode) {
      return buildComparisonLinks(data?.links || {}, linkType, baselineType);
    }

    return buildDisplayedLinks(data?.links || {}, linkType).map((edge) => ({
      ...edge,
      comparisonStatus: 'approach_only',
    }));
  }, [baselineType, data, isDifferentialMode, linkType]);

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

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.dependency-network-tooltip').remove();
    exportPayloadRef.current = null;
    simulationRef.current = null;
    redrawGraphRef.current = () => {};
    updateExportPayloadRef.current = () => {};

    if (nodes.length === 0) {
      return;
    }

    const allNodes = nodes.map((node) => ({ ...node, graphId: nodeGraphId(node) }));
    const nodeById = new Map(allNodes.map((node) => [nodeGraphId(node), node]));
    const allLinks = links
      .filter((edge) => nodeById.has(edgeGraphSourceId(edge)) && nodeById.has(edgeGraphTargetId(edge)))
      .map((edge) => ({
        ...edge,
        source: edgeGraphSourceId(edge),
        target: edgeGraphTargetId(edge),
        sourceGraphId: edgeGraphSourceId(edge),
        targetGraphId: edgeGraphTargetId(edge),
      }));

    const requestedRefs = (proposalFilterIds || []).filter((value) => value && typeof value === 'object');
    const requestedRefKeys = buildProposalRefKeySet(requestedRefs);
    const requestedIds = new Set(
      (proposalFilterIds || [])
        .filter((value) => !value || typeof value !== 'object')
        .map((value) => String(value))
    );
    const hasFilter = requestedRefKeys.size > 0 || requestedIds.size > 0;
    let displayedNodeIds = new Set(allNodes.map((node) => nodeGraphId(node)));
    let localLinks = allLinks;

    if (hasFilter) {
      const matchedFilterNodeIds = new Set(
        allNodes
          .filter((node) => {
            const rawNodeId = String(node.id);
            const normalizedNodeId = normalizeProposalId(node.id, ecosystem);
            const unpaddedNumericNodeId = /^\d+$/.test(rawNodeId) ? String(Number(rawNodeId)) : rawNodeId;
            return (
              requestedRefKeys.has(nodeRefKey(node, ecosystem))
              || requestedIds.has(normalizedNodeId)
              || requestedIds.has(rawNodeId)
              || requestedIds.has(unpaddedNumericNodeId)
            );
          })
          .map((node) => nodeGraphId(node))
      );

      if (includeConnections) {
        displayedNodeIds = new Set(matchedFilterNodeIds);
        localLinks = allLinks.filter((edge) => {
          const sourceIncluded = matchedFilterNodeIds.has(edgeGraphSourceId(edge));
          const targetIncluded = matchedFilterNodeIds.has(edgeGraphTargetId(edge));

          if (sourceIncluded || targetIncluded) {
            displayedNodeIds.add(edgeGraphSourceId(edge));
            displayedNodeIds.add(edgeGraphTargetId(edge));
            return true;
          }
          return false;
        });
      } else {
        displayedNodeIds = matchedFilterNodeIds;
        localLinks = allLinks.filter((edge) => (
          displayedNodeIds.has(edgeGraphSourceId(edge)) && displayedNodeIds.has(edgeGraphTargetId(edge))
        ));
      }
    }

    const localNodes = allNodes.filter((node) => displayedNodeIds.has(nodeGraphId(node)));
    if (localNodes.length === 0) {
      return;
    }

    const adjacency = new Map(localNodes.map((node) => [nodeGraphId(node), new Set()]));
    const degreeById = new Map(localNodes.map((node) => [nodeGraphId(node), 0]));
    const incomingById = new Map(localNodes.map((node) => [nodeGraphId(node), 0]));
    const outgoingById = new Map(localNodes.map((node) => [nodeGraphId(node), 0]));

    localLinks.forEach((edge) => {
      const sourceId = edgeGraphSourceId(edge);
      const targetId = edgeGraphTargetId(edge);
      adjacency.get(sourceId)?.add(targetId);
      adjacency.get(targetId)?.add(sourceId);
      degreeById.set(sourceId, (degreeById.get(sourceId) || 0) + 1);
      degreeById.set(targetId, (degreeById.get(targetId) || 0) + 1);
      outgoingById.set(sourceId, (outgoingById.get(sourceId) || 0) + 1);
      incomingById.set(targetId, (incomingById.get(targetId) || 0) + 1);
    });

    localNodes.forEach((node) => {
      const nodeId = nodeGraphId(node);
      node.degree = degreeById.get(nodeId) || 0;
      node.incomingDegree = incomingById.get(nodeId) || 0;
      node.outgoingDegree = outgoingById.get(nodeId) || 0;
    });

    const relationThreshold = Math.max(0, Number(String(minRelations).trim() || '0') || 0);
    const thresholdMatchedNodeIds = new Set(
      localNodes
        .filter((node) => Number(node.degree || 0) >= relationThreshold)
        .map((node) => nodeGraphId(node))
    );
    let relationFilteredNodeIds = thresholdMatchedNodeIds;
    let filteredLinks = localLinks.filter((edge) => (
      relationFilteredNodeIds.has(edgeGraphSourceId(edge)) && relationFilteredNodeIds.has(edgeGraphTargetId(edge))
    ));

    if (includeThresholdConnections && thresholdMatchedNodeIds.size > 0) {
      relationFilteredNodeIds = new Set(thresholdMatchedNodeIds);
      filteredLinks = localLinks.filter((edge) => {
        const sourceMatched = thresholdMatchedNodeIds.has(edgeGraphSourceId(edge));
        const targetMatched = thresholdMatchedNodeIds.has(edgeGraphTargetId(edge));

        if (sourceMatched || targetMatched) {
          relationFilteredNodeIds.add(edgeGraphSourceId(edge));
          relationFilteredNodeIds.add(edgeGraphTargetId(edge));
          return true;
        }

        return false;
      });
    }

    const filteredNodes = localNodes.filter((node) => relationFilteredNodeIds.has(nodeGraphId(node)));

    if (filteredNodes.length === 0) {
      exportPayloadRef.current = null;
      svg
        .attr('width', width)
        .attr('height', height)
        .append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', 'var(--app-text-muted)')
        .style('font-size', '14px')
        .text('No proposals match the current relations filter.');
      return;
    }

    const importedPositions = importedLayout?.positions || null;
    let importedPositionedNodeCount = 0;
    filteredNodes.forEach((node) => {
      const coords = importedPositions?.[nodeGraphId(node)] || importedPositions?.[String(node.id)];
      if (!coords) {
        return;
      }

      node.x = coords[0];
      node.y = coords[1];
      importedPositionedNodeCount += 1;
    });

    const highlightText = String(highlightProposal || '').trim();
    const searchMatchedIds = highlightText
      ? new Set(
        filteredNodes
          .filter((node) => {
            const nodeEcosystem = getSourceScopedEcosystem(ecosystem, node.source);
            return normalizeProposalId(node.id, nodeEcosystem) === normalizeProposalId(highlightText, nodeEcosystem);
          })
          .map((node) => nodeGraphId(node))
      )
      : new Set();

    const fallbackLabel = `Unknown ${colorBy.charAt(0).toUpperCase()}${colorBy.slice(1)}`;
    const allGroups = Array.from(new Set(allNodes.map((node) => normalizeCategory(node[colorBy], fallbackLabel))));
    const colorMap = getClassificationColorMap(colorBy, allGroups);
    const color = d3.scaleOrdinal()
      .domain(allGroups)
      .range(allGroups.map((group) => colorMap[group]));

    filteredNodes.forEach((node) => {
      node.colorGroup = normalizeCategory(node[colorBy], fallbackLabel);
    });

    const getEdgeColor = (edge) => {
      if (!isDifferentialMode) {
        if (linkType === PREAMBLE_EXTRACTED) {
          return EXPLICIT_DEPENDENCY_COLORS[edge.relationType] || '#667085';
        }
        return DEFAULT_EDGE_COLORS[edge.relationType] || '#607d8b';
      }

      return DIFFERENTIAL_EDGE_COLORS[edge.comparisonStatus] || DIFFERENTIAL_EDGE_COLORS.approach_only;
    };

    const getEdgeMarkerId = (edge) => {
      if (!isDifferentialMode) {
        return `dependency-arrow-${edge.relationType}`;
      }
      return `dependency-arrow-${edge.comparisonStatus}`;
    };

    const getEdgeDasharray = (edge) => {
      if (isDifferentialMode) {
        return edge.comparisonStatus === 'baseline_only' ? '7 5' : null;
      }
      if (linkType !== PREAMBLE_EXTRACTED) {
        return null;
      }
      return EXPLICIT_DEPENDENCY_STYLES[edge.relationType] || null;
    };

    const updateExportPayload = () => {
      const exportedNodes = filteredNodes.map((entry) => ({
        id: String(entry.id),
        source: entry.source || null,
        graph_id: nodeGraphId(entry),
        x: Number(entry.x || 0),
        y: Number(entry.y || 0),
        degree: Number(entry.degree || 0),
        incomingDegree: Number(entry.incomingDegree || 0),
        outgoingDegree: Number(entry.outgoingDegree || 0),
        group: String(entry.colorGroup || ''),
        layer: entry.layer || null,
        status: entry.status || null,
        type: entry.type || null,
      }));

      exportPayloadRef.current = {
        snapshot: snapshotLabel || null,
        exported_at: new Date().toISOString(),
        width,
        height,
        color_by: colorBy,
        link_type: linkType,
        baseline_type: isDifferentialMode ? baselineType : null,
        layout_mode: layoutMode,
        is_differential_mode: isDifferentialMode,
        filter: {
          proposal_ids: (proposalFilterIds || []).map((value) => formatProposalFilterValue(value, ecosystem)),
          include_connections: Boolean(includeConnections),
          min_relations: relationThreshold,
          include_threshold_connections: Boolean(includeThresholdConnections),
        },
        nodes: exportedNodes,
        links: filteredLinks.map((edge) => ({
          source: edgeSourceProposalId(edge),
          target: edgeTargetProposalId(edge),
          source_source: edgeSourceSourceId(edge) || null,
          target_source: edgeTargetSourceId(edge) || null,
          source_graph_id: edgeGraphSourceId(edge),
          target_graph_id: edgeGraphTargetId(edge),
          relation_type: edge.relationType || null,
          comparison_status: edge.comparisonStatus || 'approach_only',
        })),
        positions: Object.fromEntries(
          exportedNodes.map((entry) => [String(entry.graph_id), [entry.x, entry.y]])
        ),
      };
    };

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const defs = svg.append('defs');
    const markerDefinitions = Array.from(
      new Map(filteredLinks.map((edge) => [getEdgeMarkerId(edge), getEdgeColor(edge)])).entries()
    );
    markerDefinitions.forEach(([markerId, fillColor]) => {
      defs
        .append('marker')
        .attr('id', markerId)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 14)
        .attr('refY', 0)
        .attr('orient', 'auto')
        .attr('markerWidth', 4.5)
        .attr('markerHeight', 4.5)
        .append('path')
        .attr('d', 'M 0,-5 L 10,0 L 0,5')
        .attr('fill', fillColor);
    });

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'dependency-network-tooltip')
      .style('position', 'absolute')
      .style('padding', '8px 12px')
      .style('background', 'var(--tooltip-bg)')
      .style('color', 'var(--tooltip-text)')
      .style('border', '1px solid var(--tooltip-border)')
      .style('border-radius', '6px')
      .style('box-shadow', 'var(--tooltip-shadow)')
      .style('font-size', '13px')
      .style('pointer-events', 'none')
      .style('line-height', '1.45')
      .style('opacity', 0);

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const renderNodeTooltip = (entry) => {
      const nodeEcosystem = getSourceScopedEcosystem(ecosystem, entry.source);
      return (
        `<strong><a href="${getProposalUrl(entry.id, snapshotLabel, { linkMode }, nodeEcosystem)}" target="_blank" rel="noreferrer">${formatProposalReference(entry.id, nodeEcosystem)}</a></strong><br/>` +
        `Outgoing: ${entry.outgoingDegree}<br/>` +
        `Incoming: ${entry.incomingDegree}<br/>` +
        `Layer: ${entry.layer || 'Unknown'}<br/>` +
        `Status: ${entry.status || 'Unknown'}<br/>` +
        `Type: ${entry.type || 'Unknown'}`
      );
    };

    const relationLabel = {
      [BODY_EXTRACTED_REGEX]: 'Regex-Extracted Dependency',
      [BODY_EXTRACTED_LLM]: 'LLM-Extracted Dependency',
      requires: 'Requires',
      replaces: 'Replaces',
      proposed_replacement: 'Proposed Replacement',
    };

    const renderEdgeTooltip = (edge) => {
      const sourceEcosystem = getSourceScopedEcosystem(ecosystem, edgeSourceSourceId(edge));
      const targetEcosystem = getSourceScopedEcosystem(ecosystem, edgeTargetSourceId(edge));
      const sourceId = edgeSourceProposalId(edge);
      const targetId = edgeTargetProposalId(edge);
      return (
        `<strong><a href="${getProposalUrl(sourceId, snapshotLabel, { linkMode }, sourceEcosystem)}" target="_blank" rel="noreferrer">${formatProposalReference(sourceId, sourceEcosystem)}</a></strong>` +
        ` &rarr; ` +
        `<strong><a href="${getProposalUrl(targetId, snapshotLabel, { linkMode }, targetEcosystem)}" target="_blank" rel="noreferrer">${formatProposalReference(targetId, targetEcosystem)}</a></strong><br/>` +
        `Type: ${
          !isDifferentialMode
            ? (relationLabel[edge.relationType] || edge.relationType)
            : (
              edge.comparisonStatus === 'overlap'
                ? `${getLinkTypeLabel(linkType)} + ${getLinkTypeLabel(baselineType)}`
                : edge.comparisonStatus === 'baseline_only'
                  ? `${getLinkTypeLabel(baselineType)} only`
                  : `${getLinkTypeLabel(linkType)} only`
            )
        }` +
        (
          !isDifferentialMode
            ? ''
            : `<br/>Comparison: ${
              edge.comparisonStatus === 'overlap'
                ? `Exists in baseline (${getLinkTypeLabel(baselineType)})`
                : edge.comparisonStatus === 'baseline_only'
                  ? `Missing from ${getLinkTypeLabel(linkType)}`
                  : `Only in ${getLinkTypeLabel(linkType)}`
            }`
        )
      );
    };

    const getWordCount = (node) => {
      const wl = node.word_list;
      if (!wl || typeof wl !== 'object') return 0;
      return Object.values(wl).reduce((sum, count) => sum + Number(count || 0), 0);
    };
    const wordCountExtent = d3.extent(filteredNodes, getWordCount);
    const radius = d3.scaleSqrt()
      .domain([wordCountExtent[0] || 0, wordCountExtent[1] || 1])
      .range([7, 20]);
    const getNodeRadius = (entry) => (
      searchMatchedIds.has(nodeGraphId(entry))
        ? radius(getWordCount(entry)) + 5
        : radius(getWordCount(entry))
    );

    const groupAnchors = new Map();
    const anchorRadius = Math.min(width, height) * 0.24;
    allGroups.forEach((group, index) => {
      const angle = ((Math.PI * 2 * index) / Math.max(allGroups.length, 1)) - (Math.PI / 2);
      groupAnchors.set(group, {
        x: width / 2 + Math.cos(angle) * anchorRadius,
        y: height / 2 + Math.sin(angle) * anchorRadius,
      });
    });

    const linkForce = d3.forceLink(filteredLinks).id((node) => nodeGraphId(node));
    const chargeForce = d3.forceManyBody();
    const collisionForce = d3.forceCollide().radius((node) => radius(Number(node.degree || 0)) + 10);
    const centerForce = d3.forceCenter(width / 2, height / 2);
    const xForce = d3.forceX(width / 2).strength(0.05);
    const yForce = d3.forceY(height / 2).strength(0.05);

    if (layoutMode === 'clustered') {
      linkForce.distance(92).strength(0.28);
      chargeForce.strength(-220);
      xForce
        .x((node) => groupAnchors.get(node.colorGroup)?.x ?? width / 2)
        .strength(0.22);
      yForce
        .y((node) => groupAnchors.get(node.colorGroup)?.y ?? height / 2)
        .strength(0.22);
    } else if (layoutMode === 'spread') {
      linkForce.distance(155).strength(0.22);
      chargeForce.strength(-360);
      xForce.x(width / 2).strength(0.03);
      yForce.y(height / 2).strength(0.03);
    } else {
      linkForce.distance(108).strength(0.26);
      chargeForce.strength(-250);
      xForce.x(width / 2).strength(0.05);
      yForce.y(height / 2).strength(0.05);
    }

    const simulation = d3.forceSimulation(filteredNodes)
      .force('link', linkForce)
      .force('charge', chargeForce)
      .force('center', centerForce)
      .force('x', xForce)
      .force('y', yForce)
      .force('collision', collisionForce);

    const root = svg
      .attr('width', width)
      .attr('height', height)
      .append('g');

    const zoomBehavior = d3.zoom()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        root.attr('transform', event.transform);
      });

    svg.call(zoomBehavior);

    let pinnedInteraction = null;
    let link;
    let node;
    let labels;
    let renderGraph = () => {};

    const applyDefaultLinkStyles = () => {
      link
        .attr('stroke', (edge) => getEdgeColor(edge))
        .attr('stroke-opacity', (edge) => {
          if (searchMatchedIds.size === 0) {
            return 0.72;
          }
          return searchMatchedIds.has(edgeGraphSourceId(edge)) || searchMatchedIds.has(edgeGraphTargetId(edge)) ? 0.95 : 0.08;
        })
        .attr('stroke-width', DEFAULT_LINK_WIDTH)
        .attr('stroke-dasharray', (edge) => getEdgeDasharray(edge));
    };

    const applyDefaultNodeStyles = () => {
      node
        .attr('stroke', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? '#f4a261' : '#fff'))
        .attr('stroke-width', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? 3 : 1.5))
        .attr('fill-opacity', (entry) => {
          if (searchMatchedIds.size === 0) {
            return 0.95;
          }
          return searchMatchedIds.has(nodeGraphId(entry)) ? 1 : 0.18;
        });
    };

    const applyPinnedNodeStyles = (entry) => {
      const selectedGraphId = nodeGraphId(entry);
      node
        .attr('stroke', (candidate) => (nodeGraphId(candidate) === selectedGraphId ? '#f4a261' : '#fff'))
        .attr('stroke-width', (candidate) => (nodeGraphId(candidate) === selectedGraphId ? 3.5 : 1.5))
        .attr('fill-opacity', (candidate) => (nodeGraphId(candidate) === selectedGraphId ? 1 : 0.18));

      link
        .attr('stroke-opacity', (edge) => (
          edgeGraphSourceId(edge) === selectedGraphId || edgeGraphTargetId(edge) === selectedGraphId ? 0.95 : 0.1
        ))
        .attr('stroke-width', (edge) => (
          edgeGraphSourceId(edge) === selectedGraphId || edgeGraphTargetId(edge) === selectedGraphId ? ACTIVE_LINK_WIDTH : DEFAULT_LINK_WIDTH
        ));
    };

    const applyPinnedEdgeStyles = (selectedEdge) => {
      link
        .attr('stroke-opacity', (edge) => (edge.key === selectedEdge.key ? 1 : 0.08))
        .attr('stroke-width', (edge) => (edge.key === selectedEdge.key ? PINNED_LINK_WIDTH : DEFAULT_LINK_WIDTH));

      node
        .attr('fill-opacity', (entry) => (
          nodeGraphId(entry) === edgeGraphSourceId(selectedEdge) || nodeGraphId(entry) === edgeGraphTargetId(selectedEdge) ? 1 : 0.18
        ))
        .attr('stroke', (entry) => (
          nodeGraphId(entry) === edgeGraphSourceId(selectedEdge) || nodeGraphId(entry) === edgeGraphTargetId(selectedEdge) ? '#f4a261' : '#fff'
        ))
        .attr('stroke-width', (entry) => (
          nodeGraphId(entry) === edgeGraphSourceId(selectedEdge) || nodeGraphId(entry) === edgeGraphTargetId(selectedEdge) ? 3 : 1.5
        ));
    };

    const clearPinnedInteraction = () => {
      pinnedInteraction = null;
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
      applyDefaultNodeStyles();
      applyDefaultLinkStyles();
    };

    link = root.append('g')
      .selectAll('path')
      .data(filteredLinks)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke', (edge) => getEdgeColor(edge))
      .attr('stroke-opacity', 0.72)
      .attr('stroke-width', DEFAULT_LINK_WIDTH)
      .attr('stroke-dasharray', (edge) => getEdgeDasharray(edge))
      .attr('marker-end', (edge) => `url(#${getEdgeMarkerId(edge)})`)
      .on('mouseover', function (event, edge) {
        if (pinnedInteraction) {
          return;
        }

        d3.select(this)
          .attr('stroke-opacity', 1)
          .attr('stroke-width', PINNED_LINK_WIDTH);

        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderEdgeTooltip(edge));
      })
      .on('mousemove', function (event) {
        if (pinnedInteraction) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedInteraction) {
          return;
        }

        applyDefaultLinkStyles();
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, edge) {
        event.stopPropagation();
        pinnedInteraction = { type: 'edge', edge };
        applyDefaultNodeStyles();
        applyDefaultLinkStyles();
        applyPinnedEdgeStyles(edge);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderEdgeTooltip(edge));
        setTooltipPosition(event.pageX, event.pageY);
      });

    node = root.append('g')
      .selectAll('circle')
      .data(filteredNodes)
      .join('circle')
      .attr('r', (entry) => getNodeRadius(entry))
      .attr('fill', (entry) => color(normalizeCategory(entry[colorBy], fallbackLabel)))
      .attr('fill-opacity', (entry) => {
        if (searchMatchedIds.size === 0) {
          return 0.95;
        }
        return searchMatchedIds.has(nodeGraphId(entry)) ? 1 : 0.18;
      })
      .attr('stroke', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? '#f4a261' : '#fff'))
      .attr('stroke-width', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? 3 : 1.5))
      .on('mouseover', function (event, entry) {
        if (pinnedInteraction) {
          return;
        }

        d3.select(this)
          .attr('stroke', '#f4a261')
          .attr('stroke-width', 3);

        link
          .attr('stroke-opacity', (edge) => (
            edgeGraphSourceId(edge) === nodeGraphId(entry) || edgeGraphTargetId(edge) === nodeGraphId(entry) ? 0.95 : 0.1
          ))
          .attr('stroke-width', (edge) => (
            edgeGraphSourceId(edge) === nodeGraphId(entry) || edgeGraphTargetId(edge) === nodeGraphId(entry) ? 3.2 : 2.2
          ));

        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderNodeTooltip(entry));
      })
      .on('mousemove', function (event) {
        if (pinnedInteraction) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedInteraction) {
          return;
        }

        applyDefaultNodeStyles();
        applyDefaultLinkStyles();
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, entry) {
        event.stopPropagation();
        pinnedInteraction = { type: 'node', entry };
        applyDefaultNodeStyles();
        applyDefaultLinkStyles();
        applyPinnedNodeStyles(entry);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderNodeTooltip(entry));
        setTooltipPosition(event.pageX, event.pageY);
      })
      .call(
        d3.drag()
          .on('start', (event, entry) => {
            if (physicsEnabledRef.current && !event.active) {
              simulation.alphaTarget(0.3).restart();
            }
            entry.fx = entry.x;
            entry.fy = entry.y;
          })
          .on('drag', (event, entry) => {
            entry.fx = event.x;
            entry.fy = event.y;
            entry.x = event.x;
            entry.y = event.y;
            renderGraph();
          })
          .on('end', (event, entry) => {
            if (physicsEnabledRef.current && !event.active) {
              simulation.alphaTarget(0);
            }
            entry.fx = null;
            entry.fy = null;
            renderGraph();
          })
      );

    const labeledNodeIds = new Set(
      localNodes
        .filter((entry) => relationFilteredNodeIds.has(nodeGraphId(entry)))
        .slice()
        .sort((left, right) => Number(right.degree || 0) - Number(left.degree || 0))
        .slice(0, 16)
        .map((entry) => nodeGraphId(entry))
    );

    labels = root.append('g')
      .selectAll('text')
      .data(filteredNodes.filter((entry) => labeledNodeIds.has(nodeGraphId(entry)) || searchMatchedIds.has(nodeGraphId(entry))))
      .join('text')
      .text((entry) => formatProposalReference(entry.id, getSourceScopedEcosystem(ecosystem, entry.source)))
      .style('font-size', '10.5px')
      .style('fill', 'var(--chart-text)')
      .style('font-weight', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? 700 : 400))
      .style('opacity', (entry) => {
        if (searchMatchedIds.size > 0) {
          return searchMatchedIds.has(nodeGraphId(entry)) ? 1 : 0.22;
        }
        return 1;
      })
      .style('paint-order', 'stroke')
      .style('stroke', 'var(--chart-outline)')
      .style('stroke-width', 3)
      .style('stroke-linecap', 'round')
      .style('stroke-linejoin', 'round');

    renderGraph = () => {
      link
        .attr('d', (edge) => {
          const rawSourceX = edge.source.x ?? (width / 2);
          const rawSourceY = edge.source.y ?? (height / 2);
          const rawTargetX = edge.target.x ?? (width / 2);
          const rawTargetY = edge.target.y ?? (height / 2);
          const dx = rawTargetX - rawSourceX;
          const dy = rawTargetY - rawSourceY;
          const distance = Math.sqrt((dx * dx) + (dy * dy)) || 1;
          const unitX = dx / distance;
          const unitY = dy / distance;
          const sourcePadding = getNodeRadius(edge.source) + 1;
          const targetPadding = getNodeRadius(edge.target) - 5;
          const sourceX = rawSourceX + (unitX * sourcePadding);
          const sourceY = rawSourceY + (unitY * sourcePadding);
          const targetX = rawTargetX - (unitX * targetPadding);
          const targetY = rawTargetY - (unitY * targetPadding);
          const adjustedDx = targetX - sourceX;
          const adjustedDy = targetY - sourceY;
          const adjustedDistance = Math.sqrt((adjustedDx * adjustedDx) + (adjustedDy * adjustedDy)) || 1;
          const midpointX = (sourceX + targetX) / 2;
          const midpointY = (sourceY + targetY) / 2;
          const normalX = -adjustedDy / adjustedDistance;
          const normalY = adjustedDx / adjustedDistance;
          const curveOffset = Math.min(28, Math.max(10, adjustedDistance * 0.08));
          const controlX = midpointX + (normalX * curveOffset);
          const controlY = midpointY + (normalY * curveOffset);
          return `M ${sourceX},${sourceY} Q ${controlX},${controlY} ${targetX},${targetY}`;
        });

      node
        .attr('cx', (entry) => entry.x = Math.max(24, Math.min(width - 24, entry.x ?? (width / 2))))
        .attr('cy', (entry) => entry.y = Math.max(24, Math.min(height - 24, entry.y ?? (height / 2))));

      labels
        .attr('x', (entry) => entry.x + getNodeRadius(entry) + 5)
        .attr('y', (entry) => entry.y + 3);

      updateExportPayload();
    };

    simulationRef.current = simulation;
    redrawGraphRef.current = renderGraph;
    updateExportPayloadRef.current = updateExportPayload;

    svg.on('click', () => {
      clearPinnedInteraction();
    });

    simulation.on('tick', renderGraph);
    if (physicsEnabledRef.current) {
      renderGraph();
    } else {
      if (importedPositions && importedPositionedNodeCount > 0 && importedPositionedNodeCount < filteredNodes.length) {
        filteredNodes.forEach((entry) => {
          const coords = importedPositions[nodeGraphId(entry)] || importedPositions[String(entry.id)];
          if (!coords) {
            return;
          }
          entry.fx = coords[0];
          entry.fy = coords[1];
        });
      }

      if (!(importedPositions && importedPositionedNodeCount === filteredNodes.length)) {
        for (let iteration = 0; iteration < 140; iteration += 1) {
          simulation.tick();
        }
      }

      filteredNodes.forEach((entry) => {
        if (!importedPositions?.[nodeGraphId(entry)] && !importedPositions?.[String(entry.id)]) {
          return;
        }
        entry.fx = null;
        entry.fy = null;
      });
      renderGraph();
      simulation.alphaTarget(0);
      simulation.stop();
    }

    const legend = d3.select(legendRef.current);
    legend.selectAll('*').remove();

    const entries = color.domain().filter(Boolean);
    if (entries.length > 0) {
      const container = legend
        .append('div')
        .attr('class', 'dependency-node-legend');

      entries.forEach((group) => {
        const item = container
          .append('div')
          .attr('class', 'dependency-node-legend__item');

        item
          .append('span')
          .attr('class', 'dependency-node-legend__swatch')
          .style('background-color', color(group));

        item
          .append('span')
          .text(group);
      });
    }

    return () => {
      exportPayloadRef.current = null;
      if (simulationRef.current === simulation) {
        simulationRef.current = null;
      }
      redrawGraphRef.current = () => {};
      updateExportPayloadRef.current = () => {};
      simulation.stop();
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.dependency-network-tooltip').remove();
    };
  }, [baselineType, colorBy, data, ecosystem, height, highlightProposal, importedLayout, includeConnections, includeThresholdConnections, isDifferentialMode, layoutMode, linkMode, linkType, links, minRelations, nodes, proposalFilterIds, snapshotLabel, width]);

  const explicitLegendItems = [
    { label: 'Requires', dasharray: EXPLICIT_DEPENDENCY_STYLES.requires, stroke: '#667085' },
    { label: 'Replaces', dasharray: EXPLICIT_DEPENDENCY_STYLES.replaces, stroke: '#667085' },
    { label: 'Proposed Replacement', dasharray: EXPLICIT_DEPENDENCY_STYLES.proposed_replacement, stroke: '#667085' },
  ];

  const edgeLegendItems = isDifferentialMode
    ? [
      {
        label: getLinkTypeLabel(linkType),
        dasharray: null,
        stroke: DIFFERENTIAL_EDGE_COLORS.approach_only,
      },
      {
        label: `Also in ${getLinkTypeLabel(baselineType)}`,
        dasharray: null,
        stroke: DIFFERENTIAL_EDGE_COLORS.overlap,
      },
      {
        label: `Missing from ${getLinkTypeLabel(linkType)}`,
        dasharray: '7 5',
        stroke: DIFFERENTIAL_EDGE_COLORS.baseline_only,
      },
    ]
    : linkType === PREAMBLE_EXTRACTED
      ? explicitLegendItems
      : [
        {
          label: getLinkTypeLabel(linkType),
          dasharray: null,
          stroke: DEFAULT_EDGE_COLORS[linkType] || '#667085',
        },
      ];

  const approachLegendItems = isDifferentialMode
    ? [
      {
        label: getLinkTypeLabel(linkType),
        dasharray: null,
        stroke: DIFFERENTIAL_EDGE_COLORS.approach_only,
      },
    ]
    : edgeLegendItems;

  const baselineLegendItems = isDifferentialMode
    ? [
      {
        label: `Also in ${getLinkTypeLabel(baselineType)}`,
        dasharray: null,
        stroke: DIFFERENTIAL_EDGE_COLORS.overlap,
      },
      {
        label: `Missing from ${getLinkTypeLabel(linkType)}`,
        dasharray: '7 5',
        stroke: DIFFERENTIAL_EDGE_COLORS.baseline_only,
      },
    ]
    : [];

  return (
    <div>
      <div className="network-control-grid">
        <div className="network-control-row">
          <div className="network-layout-picker">
            <label className="network-layout-picker__label" htmlFor="dependency-colorBy">Coloring</label>
            <Dropdown
              inputId="dependency-colorBy"
              value={colorBy}
              options={COLOR_BY_OPTIONS}
              onChange={(event) => setColorBy(event.value)}
              placeholder="Coloring"
              className="w-full md:w-14rem"
              style={{ minWidth: '180px' }}
            />
          </div>
          <div ref={legendRef} className="network-control-grid__legend" />
        </div>

        <div className="network-control-row">
          <div className="network-layout-picker">
            <label className="network-layout-picker__label" htmlFor="linkType">Approach</label>
            <Dropdown
              inputId="linkType"
              value={linkType}
              options={LINK_TYPE_OPTIONS}
              onChange={(event) => setLinkType(event.value)}
              placeholder="Approach"
              className="w-full md:w-18rem"
              style={{ minWidth: '260px' }}
            />
          </div>
          <div className="dependency-edge-legend">
            {approachLegendItems.map((item) => (
              <div key={item.label} className="dependency-edge-legend__item">
                <svg className="dependency-edge-legend__line" viewBox="0 0 36 12" aria-hidden="true">
                  <line
                    x1="2"
                    y1="6"
                    x2="34"
                    y2="6"
                    stroke={item.stroke}
                    strokeWidth="2.5"
                    strokeDasharray={item.dasharray || undefined}
                    strokeLinecap="round"
                  />
                </svg>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="network-control-row">
          <div className="network-layout-picker">
            <label className="network-layout-picker__label" htmlFor="baselineType">Baseline</label>
            <Dropdown
              inputId="baselineType"
              value={baselineType}
              options={BASELINE_OPTIONS}
              onChange={(event) => setBaselineType(event.value)}
              placeholder="Baseline"
              className="w-full md:w-18rem"
              style={{ minWidth: '260px' }}
            />
          </div>
          {baselineLegendItems.length > 0 ? (
            <div className="dependency-edge-legend">
              {baselineLegendItems.map((item) => (
                <div key={item.label} className="dependency-edge-legend__item">
                  <svg className="dependency-edge-legend__line" viewBox="0 0 36 12" aria-hidden="true">
                    <line
                      x1="2"
                      y1="6"
                      x2="34"
                      y2="6"
                      stroke={item.stroke}
                      strokeWidth="2.5"
                      strokeDasharray={item.dasharray || undefined}
                      strokeLinecap="round"
                    />
                  </svg>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="network-layout-controls">
          <div className="network-layout-picker">
            <div className="network-layout-picker__label">Layout</div>
            <div className="network-layout-picker__options network-layout-picker__options--with-actions">
              <input
                ref={importInputRef}
                type="file"
                accept="application/json,.json"
                onChange={handleLayoutImport}
                hidden
              />
              {LAYOUT_OPTIONS.map((option) => (
                <label key={option.value} className="network-layout-picker__option">
                  <input
                    type="radio"
                    name="dependency-layout"
                    value={option.value}
                    checked={layoutMode === option.value}
                    onChange={() => setLayoutMode(option.value)}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
              <button
                type="button"
                className={`network-layout-action-button ${physicsEnabled ? '' : 'network-layout-action-button--active'}`.trim()}
                onClick={handlePhysicsToggle}
                title={physicsEnabled
                  ? 'Pause the force simulation so you can manually adjust node positions before exporting the layout.'
                  : 'Resume the force simulation for the relationship graph.'}
                aria-label={physicsEnabled
                  ? 'Pause network physics for manual layout adjustments'
                  : 'Resume network physics'}
                aria-pressed={!physicsEnabled}
                disabled={nodes.length === 0}
                  >
                    {physicsEnabled ? 'freeze physics' : 'resume physics'}
                  </button>
                  <button
                    type="button"
                    className={`network-layout-action-button ${importedLayout ? 'network-layout-action-button--active' : ''}`.trim()}
                    onClick={handleLayoutImportClick}
                    title={importedLayout
                      ? `Upload a layout JSON to replace the active imported layout. Current import: ${importedLayout.fileName}.`
                      : 'Upload a layout JSON export and apply its graph construction to the current card.'}
                    aria-label="Upload network layout JSON"
                    disabled={nodes.length === 0}
                  >
                    import layout
                  </button>
              <button
                type="button"
                className="network-layout-action-button"
                onClick={handleLayoutExport}
                title="Download the current visible network layout as JSON."
                aria-label="Download current network layout as JSON"
                disabled={nodes.length === 0}
              >
                export layout
              </button>
            </div>
          </div>
          <div className="network-layout-picker network-layout-picker--filter">
            <div className="network-layout-picker__label">Filter</div>
            <div className="network-layout-threshold">
              <span className="network-layout-threshold__copy">Only show {proposalShortPlural} with</span>
              <InputText
                value={minRelations}
                onChange={(event) => setMinRelations?.(event.target.value.replace(/[^\d]/g, ''))}
                placeholder="0"
                inputMode="numeric"
                aria-label={`Minimum relations threshold for ${proposalShortPlural}`}
                className="network-layout-threshold__input"
              />
              <span className="network-layout-threshold__suffix">or more relations.</span>
              <label className="dependency-filter-checkbox">
                <input
                  type="checkbox"
                  checked={includeThresholdConnections}
                  onChange={(event) => setIncludeThresholdConnections?.(event.target.checked)}
                />
                <span>transient</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <svg ref={ref} role="img" />
    </div>
  );
};
