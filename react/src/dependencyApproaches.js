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

export function normalizeDependencyLinks(rawLinks) {
  const links = rawLinks || {};
  const preambleExtracted = links[PREAMBLE_EXTRACTED] || links.explicit_dependencies || {};
  const requires = preambleExtracted.requires || links.requires || [];
  const replaces = preambleExtracted.replaces || links.replaces || [];
  const proposedReplacement =
    preambleExtracted.proposed_replacement
    || preambleExtracted.superseded_by
    || links.proposed_replacement
    || links.superseded_by
    || [];

  return {
    [BODY_EXTRACTED_REGEX]: links[BODY_EXTRACTED_REGEX] || links.explicit_references || [],
    [PREAMBLE_EXTRACTED]: {
      requires,
      replaces,
      proposed_replacement: proposedReplacement,
    },
    requires,
    replaces,
    proposed_replacement: proposedReplacement,
    [BODY_EXTRACTED_LLM]: links[BODY_EXTRACTED_LLM] || links.implicit_dependencies || [],
  };
}
