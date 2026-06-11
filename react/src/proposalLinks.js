import { getBipCommitUrl, getBipUrl, normalizeBipId } from './bipLinks';

function getAcronym(ecosystem) {
  return String(ecosystem?.acronym || 'IP').trim() || 'IP';
}

// Resolve a source object from ecosystem.sources by its sourceSlug (e.g. "bips" → bip source).
function resolveSourceBySlug(ecosystem, sourceSlug) {
  if (!ecosystem?.sources || !sourceSlug) return null;
  return Object.values(ecosystem.sources).find(
    (s) => (s.sourceSlug || s.sourceId) === sourceSlug,
  ) || null;
}

// Split "sourceSlug:proposalId" graph keys (e.g. "bips:32" → {sourceSlug:"bips", proposalId:"32"}).
// Returns {sourceSlug:null, proposalId:id} for plain IDs.
function splitGraphKey(id) {
  const text = String(id ?? '').trim();
  const colon = text.indexOf(':');
  if (colon === -1) return { sourceSlug: null, proposalId: text };
  return { sourceSlug: text.slice(0, colon), proposalId: text.slice(colon + 1) };
}

export function normalizeProposalId(value, ecosystem = null, options = {}) {
  const { sourceSlug, proposalId } = splitGraphKey(value);
  if (sourceSlug) {
    const source = resolveSourceBySlug(ecosystem, sourceSlug);
    if (typeof source?.normalizeProposalId === 'function') return source.normalizeProposalId(proposalId, options);
    return normalizeProposalId(proposalId, ecosystem, options);
  }
  if (typeof ecosystem?.normalizeProposalId === 'function') return ecosystem.normalizeProposalId(value, options);
  return normalizeBipId(value, options);
}

export function getProposalUrl(id, snapshotLabel = null, options = {}, ecosystem = null) {
  const { sourceSlug, proposalId } = splitGraphKey(id);
  if (sourceSlug) {
    const source = resolveSourceBySlug(ecosystem, sourceSlug);
    if (typeof source?.getProposalUrl === 'function') return source.getProposalUrl(proposalId, snapshotLabel, options);
    return getProposalUrl(proposalId, snapshotLabel, options, ecosystem);
  }
  if (typeof ecosystem?.getProposalUrl === 'function') return ecosystem.getProposalUrl(id, snapshotLabel, options);
  return getBipUrl(id, snapshotLabel, options);
}

export function getProposalCommitUrl(commitHash, options = {}, ecosystem = null) {
  if (typeof ecosystem?.getProposalCommitUrl === 'function') {
    return ecosystem.getProposalCommitUrl(commitHash, options);
  }
  return getBipCommitUrl(commitHash, options);
}

export function formatProposalReference(id, ecosystem = null) {
  const { sourceSlug, proposalId } = splitGraphKey(id);
  if (sourceSlug) {
    const source = resolveSourceBySlug(ecosystem, sourceSlug);
    if (typeof source?.formatProposalReference === 'function') return source.formatProposalReference(proposalId);
    return formatProposalReference(proposalId, ecosystem);
  }
  if (typeof ecosystem?.formatProposalReference === 'function') return ecosystem.formatProposalReference(id);
  const normalized = normalizeBipId(id, { lowercaseFallback: true });
  return normalized ? `${getAcronym(ecosystem)}${normalized}` : String(id ?? '');
}

export function formatProposalLabel(id, ecosystem = null) {
  const { sourceSlug, proposalId } = splitGraphKey(id);
  if (sourceSlug) {
    const source = resolveSourceBySlug(ecosystem, sourceSlug);
    if (typeof source?.formatProposalLabel === 'function') return source.formatProposalLabel(proposalId);
    return formatProposalLabel(proposalId, ecosystem);
  }
  if (typeof ecosystem?.formatProposalLabel === 'function') return ecosystem.formatProposalLabel(id);
  const normalized = normalizeBipId(id, { lowercaseFallback: true });
  return normalized ? `${getAcronym(ecosystem)} ${normalized}` : String(id ?? '');
}
