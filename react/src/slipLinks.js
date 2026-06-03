import { getRepositoryCommitUrl, getRepositoryProposalUrl } from './proposalLinkResolver';

export function normalizeSlipId(value, options = {}) {
  const { lowercaseFallback = false } = options;
  const text = String(value ?? '').trim();
  if (!text) {
    return '';
  }

  const match = text.match(/^(?:slip\s*[- ]*)?0*(\d+)$/i);
  if (match) {
    return String(Number(match[1]));
  }

  return lowercaseFallback ? text.toLowerCase() : text;
}

function buildDefaultFileName(normalizedId) {
  return /^\d+$/.test(normalizedId) ? `slip-${normalizedId.padStart(4, '0')}.md` : '';
}

export function getSlipUrl(id, snapshotLabel = null, options = {}) {
  const normalizedId = normalizeSlipId(id);
  return getRepositoryProposalUrl('bitcoin', normalizedId, snapshotLabel, {
    ...options,
    buildDefaultFileName,
    sourceSlug: 'slips',
  });
}

export function getSlipCommitUrl(commitHash, options = {}) {
  const {
    id = null,
    fallbackSnapshotLabel = null,
  } = options;
  const normalizedCommitHash = String(commitHash || '').trim();

  if (normalizedCommitHash) {
    return getRepositoryCommitUrl('bitcoin', normalizedCommitHash, '#', 'slips');
  }

  return id == null ? '#' : getSlipUrl(id, fallbackSnapshotLabel, { linkMode: 'history' });
}
