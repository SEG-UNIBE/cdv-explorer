import * as d3 from 'd3';

const EDGE_STROKE_WIDTH_RANGE = [1.5, 10];
const EDGE_STROKE_WIDTH_EXPONENT = 0.6;

export const DEFAULT_EDGE_CURVE_DIRECTION = 1;
export const DEFAULT_EDGE_CURVE_STRENGTH = 1;
export const EDGE_STROKE_WIDTH_HOVER_DELTA = 1.5;

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

export function buildCanonicalEdgeKey(left, right) {
  const a = String(left ?? '');
  const b = String(right ?? '');
  // eslint-disable-next-line no-control-regex
  return a.localeCompare(b) <= 0 ? `${a}\x00${b}` : `${b}\x00${a}`;
}

export function normalizeImportedEdgeCurves(payload) {
  const normalizedCurves = new Map();
  const rawCurves = Array.isArray(payload?.edge_curves) ? payload.edge_curves : [];

  rawCurves.forEach((entry) => {
    const source = String(entry?.source ?? '').trim();
    const target = String(entry?.target ?? '').trim();
    if (!source || !target || source === target) {
      return;
    }
    const rawDirection = Number(entry?.direction);
    const direction = Number.isFinite(rawDirection) && rawDirection < 0 ? -1 : DEFAULT_EDGE_CURVE_DIRECTION;
    const rawStrength = Number(entry?.strength);
    const strength = Number.isFinite(rawStrength) && rawStrength > 0 ? rawStrength : DEFAULT_EDGE_CURVE_STRENGTH;
    normalizedCurves.set(buildCanonicalEdgeKey(source, target), { source, target, direction, strength });
  });

  return normalizedCurves;
}

function proposalRefSource(ref) {
  return String(ref?.source ?? ref?.graphSource ?? '').trim();
}

export function proposalRefsSpanSources(refs) {
  const sources = new Set(
    (Array.isArray(refs) ? refs : [])
      .map(proposalRefSource)
      .filter(Boolean)
  );
  return sources.size > 1;
}

function edgeEndpointId(value) {
  if (value && typeof value === 'object') {
    return String(value.id ?? '');
  }
  return String(value ?? '');
}

export function filterCrossSourceAuthorNetwork(data) {
  const nodes = Array.isArray(data?.nodes) ? data.nodes : [];
  const edges = Array.isArray(data?.edges) ? data.edges : [];
  const visibleNodeIds = new Set(
    nodes
      .filter((node) => proposalRefsSpanSources(node?.bips))
      .map((node) => String(node.id ?? ''))
      .filter(Boolean)
  );
  const visibleEdges = edges.filter((edge) => proposalRefsSpanSources(edge?.bips));

  visibleEdges.forEach((edge) => {
    const sourceId = edgeEndpointId(edge?.source);
    const targetId = edgeEndpointId(edge?.target);
    if (sourceId) {
      visibleNodeIds.add(sourceId);
    }
    if (targetId) {
      visibleNodeIds.add(targetId);
    }
  });

  return {
    ...data,
    nodes: nodes.filter((node) => visibleNodeIds.has(String(node.id ?? ''))),
    edges: visibleEdges,
  };
}

export function authorNetworkHasCrossSourceRefs(data) {
  const nodes = Array.isArray(data?.nodes) ? data.nodes : [];
  const edges = Array.isArray(data?.edges) ? data.edges : [];
  return nodes.some((node) => proposalRefsSpanSources(node?.bips))
    || edges.some((edge) => proposalRefsSpanSources(edge?.bips));
}

export function buildDisplayCollaborationComponents(nodes, adjacency) {
  const isolatedIds = [];
  const visited = new Set();
  const components = [];

  nodes.forEach((node) => {
    const neighbors = adjacency.get(node.id) || new Set();
    if (neighbors.size === 0) {
      isolatedIds.push(node.id);
      return;
    }
    if (visited.has(node.id)) {
      return;
    }
    const queue = [node.id];
    let head = 0;
    const members = [];
    visited.add(node.id);

    while (head < queue.length) {
      const current = queue[head++];
      members.push(current);
      (adjacency.get(current) || new Set()).forEach((neighbor) => {
        if (visited.has(neighbor)) {
          return;
        }
        visited.add(neighbor);
        queue.push(neighbor);
      });
    }

    components.push(members);
  });

  components.sort((left, right) => right.length - left.length);

  if (isolatedIds.length > 0) {
    components.push(isolatedIds.sort((left, right) => left.localeCompare(right)));
  }

  return components;
}

export function prepareAuthorNetworkScene({
  data,
  importedLayout,
  minClusterCollaborations,
  physicsEnabled,
}) {
  const rawNodes = Array.isArray(data?.nodes) ? data.nodes : [];
  const rawEdges = Array.isArray(data?.edges) ? data.edges : [];
  const nodes = rawNodes.map((node) => ({ ...node }));
  const links = rawEdges.map((edge) => ({ ...edge }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const adjacency = new Map(nodes.map((node) => [node.id, new Set()]));
  const getEdgeSourceId = (edge) => (typeof edge.source === 'object' ? edge.source.id : edge.source);
  const getEdgeTargetId = (edge) => (typeof edge.target === 'object' ? edge.target.id : edge.target);

  links.forEach((edge) => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      return;
    }
    adjacency.get(edge.source).add(edge.target);
    adjacency.get(edge.target).add(edge.source);
  });

  const components = buildDisplayCollaborationComponents(nodes, adjacency);
  const clusterMeta = components.map((members, clusterIndex) => {
    const memberIds = new Set(members);
    const edgeCount = links.filter((edge) => (
      memberIds.has(getEdgeSourceId(edge)) && memberIds.has(getEdgeTargetId(edge))
    )).length;
    return { clusterId: clusterIndex, members, clusterSize: members.length, edgeCount };
  });

  const clusterByNodeId = new Map();
  clusterMeta.forEach((cluster) => {
    cluster.members.forEach((member) => {
      clusterByNodeId.set(member, {
        clusterId: cluster.clusterId,
        clusterSize: cluster.clusterSize,
        clusterCollaborations: cluster.edgeCount,
      });
    });
  });

  nodes.forEach((node) => {
    const cluster = clusterByNodeId.get(node.id) || { clusterId: -1, clusterSize: 1, clusterCollaborations: 0 };
    node.clusterId = cluster.clusterId;
    node.clusterSize = cluster.clusterSize;
    node.clusterCollaborations = cluster.clusterCollaborations;
  });

  const collaborationThreshold = Math.max(0, Number(String(minClusterCollaborations).trim() || '0') || 0);
  const visibleClusterIds = new Set(
    clusterMeta
      .filter((cluster) => cluster.edgeCount >= collaborationThreshold)
      .map((cluster) => cluster.clusterId)
  );
  const visibleNodes = nodes.filter((node) => visibleClusterIds.has(node.clusterId));
  const visibleNodeIds = new Set(visibleNodes.map((node) => node.id));
  const visibleLinks = links.filter((edge) => (
    visibleNodeIds.has(getEdgeSourceId(edge)) && visibleNodeIds.has(getEdgeTargetId(edge))
  ));
  const visibleClusters = clusterMeta.filter((cluster) => visibleClusterIds.has(cluster.clusterId));
  const importedPositions = importedLayout?.positions || null;
  const importedEdgeCurves = importedLayout?.edgeCurves || new Map();
  const importedPositionedNodeCount = importedPositions
    ? visibleNodes.filter((node) => importedPositions[String(node.id)]).length
    : 0;

  visibleNodes.forEach((node) => {
    const coords = importedPositions?.[String(node.id)];
    if (!coords) {
      return;
    }
    node.x = coords[0];
    node.y = coords[1];
    if (!physicsEnabled) {
      node.fx = coords[0];
      node.fy = coords[1];
    }
  });

  return {
    visibleNodes,
    visibleLinks,
    visibleClusters,
    clusterByNodeId,
    collaborationThreshold,
    importedEdgeCurves,
    importedPositionedNodeCount,
  };
}

export function createEdgeStrokeWidthScale(links) {
  const weights = links
    .map((link) => Number(link?.weight || 1))
    .filter((value) => Number.isFinite(value) && value > 0);

  if (weights.length === 0) {
    return () => EDGE_STROKE_WIDTH_RANGE[0];
  }

  const [minWeight, maxWeight] = d3.extent(weights);
  if (!Number.isFinite(minWeight) || !Number.isFinite(maxWeight)) {
    return () => EDGE_STROKE_WIDTH_RANGE[0];
  }

  if (minWeight === maxWeight) {
    const midpoint = (EDGE_STROKE_WIDTH_RANGE[0] + EDGE_STROKE_WIDTH_RANGE[1]) / 2;
    return () => midpoint;
  }

  return d3.scalePow()
    .exponent(EDGE_STROKE_WIDTH_EXPONENT)
    .domain([minWeight, maxWeight])
    .range(EDGE_STROKE_WIDTH_RANGE)
    .clamp(true);
}

export function allowGraphZoomGesture(event) {
  if (event?.type === 'wheel') {
    return event.ctrlKey || event.metaKey;
  }
  return !event?.button;
}
