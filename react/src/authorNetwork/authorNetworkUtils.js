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
