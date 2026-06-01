import nipLinkIndex from './generated/nipLinkIndex.json';

const NOSTR_NIPS_REPOSITORY_URL = String(
  nipLinkIndex.repositoryUrl || 'https://github.com/nostr-protocol/nips'
).replace(/\/+$/, '');

const NOSTR_NIPS_DEFAULT_BRANCH = String(
  nipLinkIndex.defaultBranch || 'master'
)
  .replace(/^refs\/remotes\/origin\//, '')
  .replace(/^origin\//, '');

const NIP_FILES = nipLinkIndex.nipFiles || {};
const SNAPSHOT_COMMITS = nipLinkIndex.snapshotCommits || {};
const SNAPSHOT_FILES = nipLinkIndex.snapshotFiles || {};

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

function getSnapshotCommit(snapshotLabel) {
  if (!snapshotLabel) {
    return '';
  }

  return SNAPSHOT_COMMITS[snapshotLabel] || '';
}

function getLatestKnownNipFileName(id) {
  const normalizedId = normalizeNipId(id);
  if (!normalizedId) {
    return '';
  }

  return NIP_FILES[normalizedId] || buildDefaultFileName(normalizedId);
}

function getSnapshotNipFileName(id, snapshotLabel) {
  const normalizedId = normalizeNipId(id);
  if (!normalizedId || !snapshotLabel) {
    return '';
  }

  return SNAPSHOT_FILES[snapshotLabel]?.[normalizedId] || '';
}

function buildRepositoryNipUrl(ref, fileName) {
  if (!NOSTR_NIPS_REPOSITORY_URL || !ref || !fileName) {
    return '#';
  }

  return `${NOSTR_NIPS_REPOSITORY_URL}/blob/${ref}/${fileName}`;
}

function buildRepositoryCommitUrl(commitHash) {
  if (!NOSTR_NIPS_REPOSITORY_URL || !commitHash) {
    return '#';
  }

  return `${NOSTR_NIPS_REPOSITORY_URL}/commit/${commitHash}`;
}

export function getNipUrl(id, snapshotLabel = null, options = {}) {
  const { linkMode = 'history' } = options;
  const normalizedId = normalizeNipId(id);

  if (linkMode === 'history' && snapshotLabel) {
    const snapshotFileName = getSnapshotNipFileName(normalizedId, snapshotLabel);
    const commitHash = getSnapshotCommit(snapshotLabel);
    if (snapshotFileName && commitHash) {
      return buildRepositoryNipUrl(commitHash, snapshotFileName);
    }
  }

  const fileName = getLatestKnownNipFileName(normalizedId);
  return buildRepositoryNipUrl(NOSTR_NIPS_DEFAULT_BRANCH, fileName);
}

export function getNipCommitUrl(commitHash, options = {}) {
  const {
    id = null,
    fallbackSnapshotLabel = null,
  } = options;
  const normalizedCommitHash = String(commitHash || '').trim();

  if (normalizedCommitHash) {
    return buildRepositoryCommitUrl(normalizedCommitHash);
  }

  return id == null ? '#' : getNipUrl(id, fallbackSnapshotLabel, { linkMode: 'history' });
}
