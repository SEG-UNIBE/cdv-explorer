import { getRepositoryCommitUrl, getRepositoryProposalUrl } from './proposalLinkResolver';

export function normalizeNipId(value, options = {}) {
  const { uppercaseFallback = true } = options;
  const text = String(value ?? '').trim();
  if (!text) {
    return '';
  }

  const match = text.match(/^(?:nip\s*[- ]*)?([0-9a-f]{1,3})$/i);
  if (match) {
    return match[1].toUpperCase().padStart(2, '0');
  }

  return uppercaseFallback ? text.toUpperCase() : text;
}

function buildDefaultFileName(normalizedId) {
  return normalizedId ? `${normalizedId}.md` : '';
}

export function getNipUrl(id, snapshotLabel = null, options = {}) {
  const normalizedId = normalizeNipId(id);
  return getRepositoryProposalUrl('nostr', normalizedId, snapshotLabel, {
    ...options,
    buildDefaultFileName,
  });
}

export function getNipCommitUrl(commitHash, options = {}) {
  const {
    id = null,
    fallbackSnapshotLabel = null,
  } = options;
  const normalizedCommitHash = String(commitHash || '').trim();

  if (normalizedCommitHash) {
    return getRepositoryCommitUrl('nostr', normalizedCommitHash);
  }

  return id == null ? '#' : getNipUrl(id, fallbackSnapshotLabel, { linkMode: 'history' });
}
