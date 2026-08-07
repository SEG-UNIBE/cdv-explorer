export const PREAMBLE_EXTRACTED = 'preamble_extracted';
export const BODY_EXTRACTED_REGEX = 'body_extracted_regex';
export const BODY_EXTRACTED_LLM = 'body_extracted_llm';
export const GROUND_TRUTH_CURATED = 'ground_truth_curated';
export const DEFAULT_DEPENDENCY_APPROACH = PREAMBLE_EXTRACTED;

export const LINK_TYPE_OPTIONS = [
  { label: 'Preamble', value: PREAMBLE_EXTRACTED },
  { label: 'Regex', value: BODY_EXTRACTED_REGEX },
  { label: 'LLM', value: BODY_EXTRACTED_LLM },
  { label: 'Ground Truth', value: GROUND_TRUTH_CURATED },
];

export const PAIRWISE_LINK_TYPE_OPTIONS = [
  { label: 'Preamble', value: PREAMBLE_EXTRACTED },
  { label: 'Regex', value: BODY_EXTRACTED_REGEX },
  { label: 'LLM', value: BODY_EXTRACTED_LLM },
];

// Which precomputed pairwise_comparisons* payload to read from
// dependency_metrics.json. Both variants are computed server-side (Python);
// the UI only selects between them, it never recomputes the comparison.
export const PAIRWISE_MATCH_MODE_ALL = 'all';
export const PAIRWISE_MATCH_MODE_DEPENDS_ON = 'depends_on';

export const PAIRWISE_MATCH_MODE_OPTIONS = [
  { label: 'Edge Only', value: PAIRWISE_MATCH_MODE_ALL },
  { label: 'Exact Type', value: PAIRWISE_MATCH_MODE_DEPENDS_ON },
];

export const DEPENDENCY_SHORT_LABELS = {
  [PREAMBLE_EXTRACTED]: 'Preamble',
  [BODY_EXTRACTED_REGEX]: 'Regex',
  [BODY_EXTRACTED_LLM]: 'LLM',
  [GROUND_TRUTH_CURATED]: 'Ground Truth',
};

export function getDependencyApproachLabel(approach, llmModel = '') {
  const baseLabel = DEPENDENCY_SHORT_LABELS[approach] || approach;
  if (approach !== BODY_EXTRACTED_LLM) {
    return baseLabel;
  }
  const model = String(llmModel || '').trim();
  return model ? `${baseLabel} (${model})` : baseLabel;
}

export function buildDependencyLinkTypeOptions(llmModel = '') {
  return LINK_TYPE_OPTIONS.map((option) => ({
    ...option,
    label: getDependencyApproachLabel(option.value, llmModel),
  }));
}

export function buildPairwiseLinkTypeOptions(llmModel = '') {
  return PAIRWISE_LINK_TYPE_OPTIONS.map((option) => ({
    ...option,
    label: getDependencyApproachLabel(option.value, llmModel),
  }));
}

function linkFromDependencyEdge(edge) {
  return {
    ...edge,
    source: edge.source,
    target: edge.target,
    value: edge.value ?? 1,
    extraction_method: edge.extraction_method,
    relation_type: edge.relation_type,
  };
}

function linksFromDependencyEdges(dependencyEdges) {
  const links = {
    [BODY_EXTRACTED_REGEX]: [],
    [PREAMBLE_EXTRACTED]: {},
    [BODY_EXTRACTED_LLM]: [],
    [GROUND_TRUTH_CURATED]: [],
  };

  (dependencyEdges || []).forEach((edge) => {
    if (!edge || edge.source == null || edge.target == null) return;
    const link = linkFromDependencyEdge(edge);
    if (edge.extraction_method === PREAMBLE_EXTRACTED) {
      const relationType = edge.relation_type;
      if (!links[PREAMBLE_EXTRACTED][relationType]) {
        links[PREAMBLE_EXTRACTED][relationType] = [];
      }
      links[PREAMBLE_EXTRACTED][relationType].push(link);
      return;
    }
    if (links[edge.extraction_method]) {
      links[edge.extraction_method].push(link);
    }
  });

  return links;
}

function normalizePreambleLinks(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value)
      .filter(([, edges]) => Array.isArray(edges))
      .map(([relationType, edges]) => [relationType, edges])
  );
}

export function normalizeDependencyLinks(rawLinks) {
  const dependencyEdges = Array.isArray(rawLinks)
    ? rawLinks
    : (Array.isArray(rawLinks?.dependency_edges) ? rawLinks.dependency_edges : null);
  const links = dependencyEdges
    ? linksFromDependencyEdges(dependencyEdges)
    : (rawLinks || {});

  return {
    [BODY_EXTRACTED_REGEX]: links[BODY_EXTRACTED_REGEX] || [],
    [PREAMBLE_EXTRACTED]: normalizePreambleLinks(links[PREAMBLE_EXTRACTED]),
    [BODY_EXTRACTED_LLM]: links[BODY_EXTRACTED_LLM] || [],
    [GROUND_TRUTH_CURATED]: links[GROUND_TRUTH_CURATED] || [],
  };
}
