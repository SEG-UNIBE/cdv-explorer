import {
  BODY_EXTRACTED_LLM,
  BODY_EXTRACTED_REGEX,
  LINK_TYPE_OPTIONS as DEPENDENCY_LINK_TYPE_OPTIONS,
  PREAMBLE_EXTRACTED,
} from '../dependencyApproaches';
import { formatProposalReference, normalizeProposalId } from '../proposalLinks';

export { PREAMBLE_EXTRACTED, normalizeProposalId };

export const LINK_TYPE_OPTIONS = DEPENDENCY_LINK_TYPE_OPTIONS;

export const BASELINE_NONE_VALUE = '__none__';

export const BASELINE_OPTIONS = [
  { label: '(none)', value: BASELINE_NONE_VALUE },
  ...LINK_TYPE_OPTIONS,
];

export const LAYOUT_OPTIONS = [
  { label: 'Balanced', value: 'balanced' },
  { label: 'Clustered', value: 'clustered' },
  { label: 'Spread', value: 'spread' },
];

export const COLOR_BY_OPTIONS = [
  { label: 'Layer', value: 'layer' },
  { label: 'Status', value: 'status' },
  { label: 'Type', value: 'type' },
];

export const COLOR_BY_OPTION_VALUES = new Set(COLOR_BY_OPTIONS.map((option) => option.value));
export const LAYOUT_OPTION_VALUES = new Set(LAYOUT_OPTIONS.map((option) => option.value));
export const LINK_TYPE_OPTION_VALUES = new Set(LINK_TYPE_OPTIONS.map((option) => option.value));

export const EXPLICIT_DEPENDENCY_COLORS = {
  requires: '#667085',
  replaces: '#667085',
  proposed_replacement: '#667085',
};

export const DEFAULT_EDGE_COLORS = {
  [BODY_EXTRACTED_REGEX]: '#939AA9',
  [BODY_EXTRACTED_LLM]: '#939AA9',
};

export const DIFFERENTIAL_EDGE_COLORS = {
  approach_only: '#b8c0cc',
  overlap: '#2f9e44',
  baseline_only: '#d94841',
};

export const DEFAULT_LINK_WIDTH = 1.8;
export const ACTIVE_LINK_WIDTH = 2.8;
export const PINNED_LINK_WIDTH = 2.6;

export const EXPLICIT_DEPENDENCY_STYLES = {
  requires: null,
  replaces: '8 5',
  proposed_replacement: '2.5 4',
};

export function getLinkTypeLabel(linkType) {
  return LINK_TYPE_OPTIONS.find((option) => option.value === linkType)?.label || linkType;
}

export function formatRelationTypeLabel(relationType) {
  if (!relationType) return 'Dependency';
  return String(relationType)
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function buildEdgeKey(source, target) {
  return `${String(source)}->${String(target)}`;
}

export function nodeGraphId(node) {
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

export function edgeGraphSourceId(edge) {
  if (edge?.source && typeof edge.source === 'object') {
    return nodeGraphId(edge.source);
  }
  return String(edge?.sourceKey ?? edge?.sourceGraphId ?? edge?.source ?? '');
}

export function edgeGraphTargetId(edge) {
  if (edge?.target && typeof edge.target === 'object') {
    return nodeGraphId(edge.target);
  }
  return String(edge?.targetKey ?? edge?.targetGraphId ?? edge?.target ?? '');
}

export function edgeSourceProposalId(edge) {
  if (edge?.source && typeof edge.source === 'object') {
    return String(edge.source.id ?? '');
  }
  return String(edge?.sourceProposalId ?? edge?.source ?? '');
}

export function edgeTargetProposalId(edge) {
  if (edge?.target && typeof edge.target === 'object') {
    return String(edge.target.id ?? '');
  }
  return String(edge?.targetProposalId ?? edge?.target ?? '');
}

export function edgeSourceSourceId(edge) {
  if (edge?.source && typeof edge.source === 'object') {
    return String(edge.source.source || '');
  }
  return String(edge?.sourceSourceId || '');
}

export function edgeTargetSourceId(edge) {
  if (edge?.target && typeof edge.target === 'object') {
    return String(edge.target.source || '');
  }
  return String(edge?.targetSourceId || '');
}

function graphSourceIdFromKey(value) {
  const text = String(value ?? '').trim();
  const separatorIndex = text.indexOf(':');
  return separatorIndex > 0 ? text.slice(0, separatorIndex) : '';
}

export function edgeSourceGraphSourceId(edge) {
  return String(edge?.sourceGraphSource || graphSourceIdFromKey(edgeGraphSourceId(edge)) || edgeSourceSourceId(edge) || '');
}

export function edgeTargetGraphSourceId(edge) {
  return String(edge?.targetGraphSource || graphSourceIdFromKey(edgeGraphTargetId(edge)) || edgeTargetSourceId(edge) || '');
}

export function isCrossSourceDependencyEdge(edge) {
  const sourceId = edgeSourceGraphSourceId(edge).trim();
  const targetId = edgeTargetGraphSourceId(edge).trim();
  return Boolean(sourceId && targetId && sourceId !== targetId);
}

export function filterCrossSourceDependencyGraph(nodes, links) {
  const filteredLinks = (Array.isArray(links) ? links : []).filter(isCrossSourceDependencyEdge);
  const linkedNodeIds = new Set();

  filteredLinks.forEach((edge) => {
    linkedNodeIds.add(edgeGraphSourceId(edge));
    linkedNodeIds.add(edgeGraphTargetId(edge));
  });

  return {
    nodes: (Array.isArray(nodes) ? nodes : []).filter((node) => linkedNodeIds.has(nodeGraphId(node))),
    links: filteredLinks,
  };
}

export function normalizeCategory(value, fallbackLabel) {
  const text = String(value ?? '').trim();
  return text || fallbackLabel;
}

export function getSourceScopedEcosystem(ecosystem, sourceId) {
  const source = ecosystem?.sources?.[sourceId];
  return source ? { ...ecosystem, ...source } : ecosystem;
}

export function formatProposalFilterValue(value, ecosystem) {
  if (value && typeof value === 'object') {
    return formatProposalReference(
      value.id,
      getSourceScopedEcosystem(ecosystem, value.source)
    );
  }
  return formatProposalReference(value, ecosystem);
}

export function allowGraphZoomGesture(event) {
  if (event?.type === 'wheel') {
    return event.ctrlKey || event.metaKey;
  }
  return !event?.button;
}

export function sanitizeFilePart(value, fallback = 'unknown') {
  const text = String(value ?? '')
    .trim()
    .replace(/[^a-z0-9._-]+/gi, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  return text || fallback;
}

export function formatSnapshotFilePart(value) {
  const text = String(value ?? '').trim();
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) {
    return `${match[1].slice(2)}${match[2]}${match[3]}`;
  }
  return sanitizeFilePart(text, 'snapshot');
}

export function normalizeImportedPositions(payload) {
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

export function buildDisplayedLinks(linksByType, linkType) {
  if (linkType === PREAMBLE_EXTRACTED) {
    const explicit = linksByType?.[PREAMBLE_EXTRACTED] || {};
    return Object.entries(explicit)
      .flatMap(([relationType, edges]) => (edges || []).map((edge, index) => ({
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

export function getLinkSetForType(linksByType, linkType) {
  if (linkType === PREAMBLE_EXTRACTED) {
    const explicit = linksByType?.[PREAMBLE_EXTRACTED] || {};
    return Object.values(explicit)
      .flatMap((edges) => (edges || []).map((edge) => ({
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

export function buildComparisonLinks(linksByType, approachType, baselineType) {
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
