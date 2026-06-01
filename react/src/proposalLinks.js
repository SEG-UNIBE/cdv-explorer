import { getBipCommitUrl, getBipUrl, normalizeBipId } from './bipLinks';

function getAcronym(ecosystem) {
  return String(ecosystem?.acronym || 'IP').trim() || 'IP';
}

export function normalizeProposalId(value, ecosystem = null, options = {}) {
  if (typeof ecosystem?.normalizeProposalId === 'function') {
    return ecosystem.normalizeProposalId(value, options);
  }
  return normalizeBipId(value, options);
}

export function getProposalUrl(id, snapshotLabel = null, options = {}, ecosystem = null) {
  if (typeof ecosystem?.getProposalUrl === 'function') {
    return ecosystem.getProposalUrl(id, snapshotLabel, options);
  }
  return getBipUrl(id, snapshotLabel, options);
}

export function getProposalCommitUrl(commitHash, options = {}, ecosystem = null) {
  if (typeof ecosystem?.getProposalCommitUrl === 'function') {
    return ecosystem.getProposalCommitUrl(commitHash, options);
  }
  return getBipCommitUrl(commitHash, options);
}

export function formatProposalReference(id, ecosystem = null) {
  if (typeof ecosystem?.formatProposalReference === 'function') {
    return ecosystem.formatProposalReference(id);
  }

  const normalized = normalizeBipId(id, { lowercaseFallback: true });
  return normalized ? `${getAcronym(ecosystem)}${normalized}` : String(id ?? '');
}

export function formatProposalLabel(id, ecosystem = null) {
  if (typeof ecosystem?.formatProposalLabel === 'function') {
    return ecosystem.formatProposalLabel(id);
  }

  const normalized = normalizeBipId(id, { lowercaseFallback: true });
  return normalized ? `${getAcronym(ecosystem)} ${normalized}` : String(id ?? '');
}
