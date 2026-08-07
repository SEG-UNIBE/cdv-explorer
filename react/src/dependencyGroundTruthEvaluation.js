import {
  BODY_EXTRACTED_LLM,
  BODY_EXTRACTED_REGEX,
  DEPENDENCY_SHORT_LABELS,
  GROUND_TRUTH_CURATED,
  PREAMBLE_EXTRACTED,
} from './dependencyApproaches';
import { DEFAULT_RELATION_ONTOLOGY } from './dependencyRelationOntology';

export const EVALUATED_DEPENDENCY_APPROACHES = [
  PREAMBLE_EXTRACTED,
  BODY_EXTRACTED_REGEX,
  BODY_EXTRACTED_LLM,
];

export const GROUND_TRUTH_MATCH_MODE_EDGE_ONLY = 'edge_only';
export const GROUND_TRUTH_MATCH_MODE_EXACT_TYPE = 'exact_type';

export const GROUND_TRUTH_MATCH_MODE_OPTIONS = [
  { label: 'Edge Only', value: GROUND_TRUTH_MATCH_MODE_EDGE_ONLY },
  { label: 'Exact Type', value: GROUND_TRUTH_MATCH_MODE_EXACT_TYPE },
];

export const GROUND_TRUTH_CUTOFF_MODE_ALL = 'all';
export const GROUND_TRUTH_CUTOFF_MODE_ON_OR_BEFORE = 'on_or_before';
export const GROUND_TRUTH_CUTOFF_MODE_ON_OR_AFTER = 'on_or_after';
export const GROUND_TRUTH_CUTOFF_MODE_BETWEEN = 'between';

export const GROUND_TRUTH_CUTOFF_MODE_OPTIONS = [
  { label: 'All completed reviews', value: GROUND_TRUTH_CUTOFF_MODE_ALL },
  { label: 'Reviewed on or before', value: GROUND_TRUTH_CUTOFF_MODE_ON_OR_BEFORE },
  { label: 'Reviewed on or later', value: GROUND_TRUTH_CUTOFF_MODE_ON_OR_AFTER },
  { label: 'Reviewed between', value: GROUND_TRUTH_CUTOFF_MODE_BETWEEN },
];

// Sentinel target meaning "match any ground-truth type for this directed pair".
// Lets a generic subtype (e.g. Regex `reference`) count whenever the edge exists
// in the ground truth, regardless of the curated relation type.
export const GT_TYPE_ALL = '*';

// The LLM approach's subtypes (depends_on/references/supersedes/
// superseded_by) already equal their canonical ground-truth names, so they
// need no override here: the generic canonicalToGtType fallback in
// buildDefaultTypeMapping resolves them directly.
const DEFAULT_GT_TARGET_BY_APPROACH_SUBTYPE = {
  [BODY_EXTRACTED_REGEX]: {
    reference: 'depends_on',
  },
};

function normalizeRelationType(relationType) {
  return String(relationType || '').trim().toLowerCase();
}

function normalizeReviewDate(value) {
  const text = String(value || '').trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year
    || date.getUTCMonth() !== month - 1
    || date.getUTCDate() !== day
  ) {
    return null;
  }
  return text;
}

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

function reviewedIpKey(entry) {
  return String(entry?.ip || entry?.graph_key || entry?.graphKey || '').trim();
}

function buildDirectedEdgeKey(edge) {
  const source = edgeSourceKey(edge);
  const target = edgeTargetKey(edge);
  return source && target ? `${source}->${target}` : '';
}

// A typed key pins the directed edge to a relation-type label. In Exact Type mode
// predicted edges use their user-mapped ground-truth type, while gold edges use
// their own type, so the two only match when both agree.
function buildTypedEdgeKey(edge, typeLabel) {
  const baseKey = buildDirectedEdgeKey(edge);
  const type = normalizeRelationType(typeLabel);
  return baseKey && type ? `${baseKey}:::${type}` : baseKey;
}

function edgeEntry(edge) {
  return {
    source: edgeSourceKey(edge),
    target: edgeTargetKey(edge),
    relationType: String(edge?.relation_type || '').trim(),
  };
}

// Collapse [{ key, edge }] into a Map keyed by `key`, keeping the first edge seen.
function dedupeEntries(entries) {
  const map = new Map();
  entries.forEach(({ key, edge }) => {
    if (!key || map.has(key)) {
      return;
    }
    map.set(key, edgeEntry(edge));
  });
  return map;
}

function summarize(predictedEdgeMap, goldEdgeMap) {
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

const EMPTY_METRICS = {
  tp: 0, fp: 0, fn: 0, precision: 0, recall: 0, f1: 0,
  matchedEdges: [], falsePositiveEdges: [], falseNegativeEdges: [],
};

function distinctRelationTypes(edges) {
  const seen = new Set();
  const order = [];
  edges.forEach((edge) => {
    const type = normalizeRelationType(edge?.relation_type);
    if (type && !seen.has(type)) {
      seen.add(type);
      order.push(type);
    }
  });
  return order;
}

// Discover the relation subtypes present per approach and prefill a sensible
// default mapping. This is fully data-driven (any ecosystem/source) with the
// declared ontology only supplying the default include/target suggestions.
export function buildDefaultTypeMapping(dataset, ontology = DEFAULT_RELATION_ONTOLOGY) {
  const linksByType = dataset?.links || {};
  const { canonicalMap, excludedTypes } = ontology;

  const gtTypes = distinctRelationTypes(flattenApproachLinks(linksByType, GROUND_TRUTH_CURATED));
  const canonicalToGtType = {};
  gtTypes.forEach((type) => {
    const canonical = canonicalMap[type] || type;
    if (!(canonical in canonicalToGtType)) {
      canonicalToGtType[canonical] = type;
    }
  });

  const rows = [];
  EVALUATED_DEPENDENCY_APPROACHES.forEach((approach) => {
    const subtypes = distinctRelationTypes(flattenApproachLinks(linksByType, approach));
    if (!subtypes.length) {
      // Keep the approach visible even when it extracted no relations in this
      // dataset, so the table always lists every approach. The placeholder row
      // is inert (no subtype) and never participates in matching.
      rows.push({ approach, subtype: null, include: false, target: null, empty: true });
      return;
    }
    subtypes.forEach((subtype) => {
      const canonical = canonicalMap[subtype] || subtype;
      const preferredTarget = DEFAULT_GT_TARGET_BY_APPROACH_SUBTYPE[approach]?.[subtype] || null;
      let target = preferredTarget && gtTypes.includes(preferredTarget)
        ? preferredTarget
        : (canonicalToGtType[canonical] || null);
      const excluded = excludedTypes.has(subtype);
      rows.push({
        approach,
        subtype,
        include: !excluded && Boolean(target),
        target,
      });
    });
  });

  return { gtTypes, rows };
}

// Restrict a gold edge map to the given set of relation types. Used so an
// approach is only scored against the gold edges of the types it is mapped to
// detect (its recall/false-negatives ignore relation types it never targets).
function filterGoldMapByTypes(goldEdgeMap, types) {
  const filtered = new Map();
  goldEdgeMap.forEach((entry, key) => {
    if (types.has(normalizeRelationType(entry.relationType))) {
      filtered.set(key, entry);
    }
  });
  return filtered;
}

// approach -> Map(subtype -> mapped ground-truth type) for included rows only.
function indexIncludedMapping(typeMapping) {
  const byApproach = new Map();
  (typeMapping?.rows || []).forEach((row) => {
    if (!row.include || !row.target) {
      return;
    }
    if (!byApproach.has(row.approach)) {
      byApproach.set(row.approach, new Map());
    }
    byApproach.get(row.approach).set(normalizeRelationType(row.subtype), normalizeRelationType(row.target));
  });
  return byApproach;
}

export function buildGroundTruthEvaluation(dataset, options = {}) {
  const {
    matchMode = GROUND_TRUTH_MATCH_MODE_EDGE_ONLY,
    ontology = DEFAULT_RELATION_ONTOLOGY,
    typeMapping = null,
    restrictToReviewedSources = true,
    allowCrossSourceTargets = true,
    gtCutoffMode = GROUND_TRUTH_CUTOFF_MODE_ALL,
    gtCutoffDate = '',
    gtCutoffStartDate = '',
    gtCutoffEndDate = '',
  } = options;
  const isExactType = matchMode === GROUND_TRUTH_MATCH_MODE_EXACT_TYPE;
  const linksByType = dataset?.links || {};
  const networkNodeKeys = new Set(
    (Array.isArray(dataset?.nodes) ? dataset.nodes : [])
      .map((n) => String(n?.graph_key || n?.graphKey || n?.id || '').trim())
      .filter(Boolean)
  );
  const allGroundTruthEdges = flattenApproachLinks(linksByType, GROUND_TRUTH_CURATED)
    .filter((edge) => allowCrossSourceTargets || !networkNodeKeys.size || networkNodeKeys.has(edgeTargetKey(edge)));
  const allReviewedIps = Array.isArray(dataset?.groundTruthReviewedIps)
    ? dataset.groundTruthReviewedIps.filter(Boolean)
    : [];

  const normalizedCutoffDate = normalizeReviewDate(gtCutoffDate);
  const normalizedCutoffStartDate = normalizeReviewDate(gtCutoffStartDate || gtCutoffDate);
  const normalizedCutoffEndDate = normalizeReviewDate(gtCutoffEndDate || gtCutoffDate);
  const matchesCutoff = (reviewedAt) => {
    if (!reviewedAt) {
      return false;
    }
    if (gtCutoffMode === GROUND_TRUTH_CUTOFF_MODE_ON_OR_BEFORE && normalizedCutoffDate) {
      return reviewedAt <= normalizedCutoffDate;
    }
    if (gtCutoffMode === GROUND_TRUTH_CUTOFF_MODE_ON_OR_AFTER && normalizedCutoffDate) {
      return reviewedAt >= normalizedCutoffDate;
    }
    if (
      gtCutoffMode === GROUND_TRUTH_CUTOFF_MODE_BETWEEN
      && normalizedCutoffStartDate
      && normalizedCutoffEndDate
    ) {
      const rangeStart = normalizedCutoffStartDate <= normalizedCutoffEndDate
        ? normalizedCutoffStartDate
        : normalizedCutoffEndDate;
      const rangeEnd = normalizedCutoffStartDate <= normalizedCutoffEndDate
        ? normalizedCutoffEndDate
        : normalizedCutoffStartDate;
      return reviewedAt >= rangeStart && reviewedAt <= rangeEnd;
    }
    return true;
  };
  const reviewedIps = allReviewedIps.filter((entry) => {
    const reviewedAt = normalizeReviewDate(entry?.reviewed_at);
    return matchesCutoff(reviewedAt);
  });
  const groundTruthEdges = gtCutoffMode === GROUND_TRUTH_CUTOFF_MODE_ALL
    ? allGroundTruthEdges
    : allGroundTruthEdges.filter((edge) => matchesCutoff(normalizeReviewDate(edge?.reviewed_at)));

  const reviewedSourceKeys = new Set(reviewedIps.map(reviewedIpKey).filter(Boolean));
  const curatedTargetKeys = new Set(groundTruthEdges.map(edgeTargetKey).filter(Boolean));
  const totalProposalCount = Array.isArray(dataset?.nodes) ? dataset.nodes.length : 0;

  const goldEdgeMap = dedupeEntries(groundTruthEdges.map((edge) => ({
    key: isExactType ? buildTypedEdgeKey(edge, edge?.relation_type) : buildDirectedEdgeKey(edge),
    edge,
  })));
  const goldEdgeKeys = new Set(goldEdgeMap.keys());

  if (!reviewedSourceKeys.size) {
    return null;
  }

  const includedByApproach = isExactType
    ? indexIncludedMapping(typeMapping || buildDefaultTypeMapping(dataset, ontology))
    : null;

  // Directed pair -> set of gold relation types, used to resolve "(all)" targets,
  // plus the full set of gold types for scoping each approach's gold set.
  const goldTypesByPair = new Map();
  const allGoldTypes = new Set();
  if (isExactType) {
    groundTruthEdges.forEach((edge) => {
      const pair = buildDirectedEdgeKey(edge);
      const type = normalizeRelationType(edge?.relation_type);
      if (type) {
        allGoldTypes.add(type);
      }
      if (!pair) {
        return;
      }
      if (!goldTypesByPair.has(pair)) {
        goldTypesByPair.set(pair, new Set());
      }
      if (type) {
        goldTypesByPair.get(pair).add(type);
      }
    });
  }

  // Build the typed prediction key(s) for one edge under a chosen target. A
  // specific type yields one key; "(all)" yields one key per gold type of the
  // pair (so it matches whatever the ground truth recorded), or a single
  // directed key when the pair is absent from the gold set (one false positive).
  const predictedEntriesForEdge = (edge, target) => {
    if (target !== GT_TYPE_ALL) {
      return [{ key: buildTypedEdgeKey(edge, target), edge }];
    }
    const pair = buildDirectedEdgeKey(edge);
    const goldTypes = goldTypesByPair.get(pair);
    if (goldTypes && goldTypes.size) {
      return Array.from(goldTypes).map((type) => ({ key: buildTypedEdgeKey(edge, type), edge }));
    }
    return [{ key: pair, edge }];
  };

  const reviewedBySource = {};
  reviewedIps.forEach((entry) => {
    const slug = String(entry?.ip || '').split(':', 1)[0] || 'unknown';
    reviewedBySource[slug] = (reviewedBySource[slug] || 0) + 1;
  });

  const totalBySource = {};
  (Array.isArray(dataset?.nodes) ? dataset.nodes : []).forEach((node) => {
    const key = String(node?.graph_key || node?.graphKey || node?.id || '').trim();
    const slug = key.includes(':') ? key.split(':', 1)[0] : 'unknown';
    totalBySource[slug] = (totalBySource[slug] || 0) + 1;
  });

  const goldEdgesBySourcePair = {};
  groundTruthEdges.forEach((edge) => {
    const src = String(edgeSourceKey(edge)).split(':', 1)[0] || 'unknown';
    const tgt = String(edgeTargetKey(edge)).split(':', 1)[0] || 'unknown';
    const pair = `${src}->${tgt}`;
    goldEdgesBySourcePair[pair] = (goldEdgesBySourcePair[pair] || 0) + 1;
  });

  return {
    matchMode,
    restrictToReviewedSources,
    gtCutoffMode,
    gtCutoffDate: normalizedCutoffDate,
    gtCutoffStartDate: normalizedCutoffStartDate,
    gtCutoffEndDate: normalizedCutoffEndDate,
    reviewedProposalCount: reviewedSourceKeys.size,
    reviewedBySource,
    curatedTargetCount: curatedTargetKeys.size,
    totalProposalCount,
    totalBySource,
    goldEdgeCount: goldEdgeKeys.size,
    goldEdgesBySourcePair,
    approaches: EVALUATED_DEPENDENCY_APPROACHES.map((approach) => {
      // Restricted mode scores only proposals that were explicitly reviewed in
      // the benchmark scope; non-restricted mode scores every extracted edge.
      const approachEdges = flattenApproachLinks(linksByType, approach)
        .filter((edge) => !restrictToReviewedSources || reviewedSourceKeys.has(edgeSourceKey(edge)))
        .filter((edge) => allowCrossSourceTargets || !networkNodeKeys.size || networkNodeKeys.has(edgeTargetKey(edge)));

      let predictedEntries;
      let evaluated;
      let approachGoldMap = goldEdgeMap;
      if (!isExactType) {
        evaluated = true;
        predictedEntries = approachEdges.map((edge) => ({ key: buildDirectedEdgeKey(edge), edge }));
      } else {
        // In Exact Type mode an approach is only scored when at least one of its
        // subtypes is mapped/included; excluded subtypes are dropped entirely.
        const included = includedByApproach.get(approach);
        evaluated = Boolean(included && included.size);
        if (evaluated) {
          // Scope the gold set to the types this approach is mapped to, so it is
          // not penalised for relation types it was never asked to detect.
          const targetedTypes = new Set();
          included.forEach((target) => {
            if (target === GT_TYPE_ALL) {
              allGoldTypes.forEach((type) => targetedTypes.add(type));
            } else {
              targetedTypes.add(target);
            }
          });
          approachGoldMap = filterGoldMapByTypes(goldEdgeMap, targetedTypes);
          predictedEntries = approachEdges.flatMap((edge) => {
            const target = included.get(normalizeRelationType(edge?.relation_type));
            return target ? predictedEntriesForEdge(edge, target) : [];
          });
        } else {
          predictedEntries = [];
        }
      }

      const metrics = evaluated
        ? summarize(dedupeEntries(predictedEntries), approachGoldMap)
        : EMPTY_METRICS;

      return {
        approach,
        label: DEPENDENCY_SHORT_LABELS[approach] || approach,
        evaluated,
        ...metrics,
      };
    }),
  };
}
