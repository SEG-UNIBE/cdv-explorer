export const PREAMBLE_EXTRACTED = 'preamble_extracted';
export const BODY_EXTRACTED_REGEX = 'body_extracted_regex';
export const BODY_EXTRACTED_LLM = 'body_extracted_llm';
export const DEFAULT_DEPENDENCY_APPROACH = PREAMBLE_EXTRACTED;

export const LINK_TYPE_OPTIONS = [
  { label: 'Preamble', value: PREAMBLE_EXTRACTED },
  { label: 'Regex', value: BODY_EXTRACTED_REGEX },
  { label: 'LLM', value: BODY_EXTRACTED_LLM },
];

export const DEPENDENCY_SHORT_LABELS = {
  [PREAMBLE_EXTRACTED]: 'Preamble',
  [BODY_EXTRACTED_REGEX]: 'Regex',
  [BODY_EXTRACTED_LLM]: 'LLM',
};

function linkFromDependencyEdge(edge) {
  return {
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

export function normalizeDependencyLinks(rawLinks) {
  const dependencyEdges = Array.isArray(rawLinks)
    ? rawLinks
    : (Array.isArray(rawLinks?.dependency_edges) ? rawLinks.dependency_edges : null);
  const links = dependencyEdges
    ? linksFromDependencyEdges(dependencyEdges)
    : (rawLinks || {});
  const preambleExtracted = links[PREAMBLE_EXTRACTED] || {};
  const preambleRelationTypes = Array.from(new Set([
    ...Object.keys(preambleExtracted),
    ...['requires', 'replaces', 'proposed_replacement'].filter((relationType) => Array.isArray(links[relationType])),
  ]));
  const normalizedPreamble = Object.fromEntries(
    preambleRelationTypes.map((relationType) => [
      relationType,
      preambleExtracted[relationType] || links[relationType] || [],
    ])
  );

  return {
    [BODY_EXTRACTED_REGEX]: links[BODY_EXTRACTED_REGEX] || [],
    [PREAMBLE_EXTRACTED]: normalizedPreamble,
    ...normalizedPreamble,
    [BODY_EXTRACTED_LLM]: links[BODY_EXTRACTED_LLM] || [],
  };
}
