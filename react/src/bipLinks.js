import { getRepositoryCommitUrl, getRepositoryProposalUrl } from './proposalLinkResolver';

export function normalizeBipId(value, options = {}) {
  const { lowercaseFallback = false } = options;
  const text = String(value ?? '').trim();
  if (!text) {
    return '';
  }

  const match = text.match(/^(?:bip\s*[- ]*)?0*(\d+)$/i);
  if (match) {
    return String(Number(match[1]));
  }

  return lowercaseFallback ? text.toLowerCase() : text;
}

function buildDefaultFileName(normalizedId) {
  return /^\d+$/.test(normalizedId) ? `bip-${normalizedId.padStart(4, '0')}.mediawiki` : '';
}

export function getBipUrl(id, snapshotLabel = null, options = {}) {
  const normalizedId = normalizeBipId(id);
  return getRepositoryProposalUrl('bitcoin', normalizedId, snapshotLabel, {
    ...options,
    buildDefaultFileName,
  });
}

export function getBipCommitUrl(commitHash, options = {}) {
  const {
    id = null,
    fallbackSnapshotLabel = null,
  } = options;
  const normalizedCommitHash = String(commitHash || '').trim();

  if (normalizedCommitHash) {
    return getRepositoryCommitUrl('bitcoin', normalizedCommitHash);
  }

  return id == null ? '#' : getBipUrl(id, fallbackSnapshotLabel, { linkMode: 'history' });
}
