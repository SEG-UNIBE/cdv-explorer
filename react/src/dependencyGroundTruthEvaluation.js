import {
  BODY_EXTRACTED_LLM,
  BODY_EXTRACTED_REGEX,
  DEPENDENCY_SHORT_LABELS,
  GROUND_TRUTH_CURATED,
  PREAMBLE_EXTRACTED,
} from './dependencyApproaches';

export const EVALUATED_DEPENDENCY_APPROACHES = [
  PREAMBLE_EXTRACTED,
  BODY_EXTRACTED_REGEX,
  BODY_EXTRACTED_LLM,
];

function flattenApproachLinks(linksByType, approach) {
  if (approach === PREAMBLE_EXTRACTED) {
    return Object.values(linksByType?.[PREAMBLE_EXTRACTED] || {}).flat().filter(Boolean);
  }
  return Array.isArray(linksByType?.[approach]) ? linksByType[approach].filter(Boolean) : [];
}

function edgeSourceKey(edge) {
  return String(edge?.sourceKey || edge?.source || '').trim();
}

function edgeTargetKey(edge) {
  return String(edge?.targetKey || edge?.target || '').trim();
}

function buildDirectedEdgeKey(edge) {
  const source = edgeSourceKey(edge);
  const target = edgeTargetKey(edge);
  return source && target ? `${source}->${target}` : '';
}

function dedupeEdgesByKey(edges) {
  const entries = new Map();
  edges.forEach((edge) => {
    const key = buildDirectedEdgeKey(edge);
    if (!key || entries.has(key)) {
      return;
    }
    entries.set(key, {
      source: edgeSourceKey(edge),
      target: edgeTargetKey(edge),
      relationType: String(edge?.relation_type || '').trim(),
    });
  });
  return entries;
}

function summarizeApproach(predictedEdges, goldEdgeMap) {
  const predictedEdgeMap = dedupeEdgesByKey(predictedEdges);
  const predictedEdgeKeys = new Set(predictedEdgeMap.keys());
  const goldEdgeKeys = new Set(goldEdgeMap.keys());

  let tp = 0;
  predictedEdgeKeys.forEach((key) => {
    if (goldEdgeKeys.has(key)) {
      tp += 1;
    }
  });

  const fp = predictedEdgeKeys.size - tp;
  const fn = Array.from(goldEdgeKeys).reduce((count, key) => (
    count + (predictedEdgeKeys.has(key) ? 0 : 1)
  ), 0);
  const precision = tp + fp > 0 ? tp / (tp + fp) : 0;
  const recall = tp + fn > 0 ? tp / (tp + fn) : 0;
  const f1 = precision + recall > 0 ? (2 * precision * recall) / (precision + recall) : 0;
  const matchedEdges = Array.from(predictedEdgeKeys)
    .filter((key) => goldEdgeKeys.has(key))
    .map((key) => goldEdgeMap.get(key) || predictedEdgeMap.get(key));
  const falsePositiveEdges = Array.from(predictedEdgeKeys)
    .filter((key) => !goldEdgeKeys.has(key))
    .map((key) => predictedEdgeMap.get(key));
  const falseNegativeEdges = Array.from(goldEdgeKeys)
    .filter((key) => !predictedEdgeKeys.has(key))
    .map((key) => goldEdgeMap.get(key));

  return {
    tp,
    fp,
    fn,
    precision,
    recall,
    f1,
    matchedEdges,
    falsePositiveEdges,
    falseNegativeEdges,
  };
}

export function buildGroundTruthEvaluation(dataset) {
  const linksByType = dataset?.links || {};
  const groundTruthEdges = flattenApproachLinks(linksByType, GROUND_TRUTH_CURATED);

  if (!groundTruthEdges.length) {
    return null;
  }

  const curatedSourceKeys = new Set(
    groundTruthEdges
      .map(edgeSourceKey)
      .filter(Boolean)
  );
  const goldEdgeMap = dedupeEdgesByKey(groundTruthEdges);
  const goldEdgeKeys = new Set(goldEdgeMap.keys());

  if (!curatedSourceKeys.size || !goldEdgeKeys.size) {
    return null;
  }

  return {
    matchMode: 'Directed edge recovery',
    curatedProposalCount: curatedSourceKeys.size,
    goldEdgeCount: goldEdgeKeys.size,
    approaches: EVALUATED_DEPENDENCY_APPROACHES.map((approach) => {
      const predictedEdges = flattenApproachLinks(linksByType, approach)
        .filter((edge) => curatedSourceKeys.has(edgeSourceKey(edge)));

      return {
        approach,
        label: DEPENDENCY_SHORT_LABELS[approach] || approach,
        ...summarizeApproach(predictedEdges, goldEdgeMap),
      };
    }),
  };
}
