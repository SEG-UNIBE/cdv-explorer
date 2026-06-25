import { buildProposalRefKeySet, nodeRefKey, normalizeProposalFilterValue } from './proposalFilters';

const WORD_CLOUD_STOPWORDS = new Set([
  'code', 'tt', '0', '1', '2', '3', '4', '32', 'x',
  'key', 'not', 'if', 'can', 'pre', 'must', 'which', 's',
  'https', 'com', 'should', 'may', 'have', 'new', 'any', 'no',
  'using', 'use', 'only', 'used', 'all', 'we', 'they', 'when',
  'each', 'time', 'i', 'but', 'would', 'than', 'same', 'm',
  'their', 'more', 'also', 'such', 'there', 'then', 'these',
  'bit', 'bytes', 'byte', 'message', 'comments', 'data', 'value',
  'type', 'size', 'set', 'path', 'ref', 'org', 'p', 'n',
  'github', 'mediawiki', 'sub', 'script', 'public', 'one', 'number', 'keys', 'other', 'first',
  'following', 'implementation', 'string', 'case', 'node', 'private',
  'master', 'does', 'specification', 'two', 'change',
  'valid', 'where', 'after', 'return', 'e', 'g', 'without', 'standard',
  'user', 'order', 't', 'index', 'b', 'example', 'nodes', 'non', 'style',
  'format', 'bits', 'so', 'license', 'some', 'field', 'length',
  'messages', 'defined', 'being', 'uri', 'created', 'k', 'required',
  'possible', 'both', 'see', 'let', 'however', 'list', 'wiki', 'into', 'based',
  'them', 'blob', 'stack', 'sup', 'been', 'name', 'c', 'do', 'r', '5', '8', 'up', 'make', 'since', 'given', 'per', 'while',
]);

export function buildWordCloudData(nodes, selectedProposalRefs = [], ecosystem = null) {
  const selectedRefs = selectedProposalRefs || [];
  const selectedRefKeySet = buildProposalRefKeySet(
    selectedRefs.filter((entry) => entry && typeof entry === 'object')
  );
  const selectedIdSet = new Set(
    selectedRefs
      .filter((entry) => !entry || typeof entry !== 'object')
      .map(normalizeProposalFilterValue)
      .filter(Boolean)
  );
  const hasSourceAwareFilter = selectedRefKeySet.size > 0;
  const hasLegacyFilter = selectedIdSet.size > 0;
  const wordCounts = {};

  (nodes || []).forEach((node) => {
    const proposalId = normalizeProposalFilterValue(node?.id);
    if (hasSourceAwareFilter && !selectedRefKeySet.has(nodeRefKey(node, ecosystem))) {
      return;
    }
    if (!hasSourceAwareFilter && hasLegacyFilter && !selectedIdSet.has(proposalId)) {
      return;
    }

    const wordList = node?.word_list;
    if (!wordList) {
      return;
    }

    Object.entries(wordList).forEach(([word, count]) => {
      wordCounts[word] = (wordCounts[word] || 0) + count;
    });
  });

  return Object.entries(wordCounts)
    .filter(([word]) => !WORD_CLOUD_STOPWORDS.has(word.toLowerCase()))
    .map(([word, count]) => ({ word, count }))
    .sort((left, right) => right.count - left.count)
    .slice(0, 100);
}
