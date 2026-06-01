import externalLinks from './externalLinks.json';
import bipLinkIndex from './generated/bipLinkIndex.json';

const BIPS_DEV_BASE_URL = String(externalLinks.bipsDevBaseUrl || '').replace(/\/+$/, '');

const BITCOIN_BIPS_REPOSITORY_URL = String(
  bipLinkIndex.repositoryUrl || externalLinks.bitcoinBipsRepositoryUrl || ''
).replace(/\/+$/, '');

const BITCOIN_BIPS_DEFAULT_BRANCH = String(
  bipLinkIndex.defaultBranch || externalLinks.bitcoinBipsDefaultBranch || 'master'
)
  .replace(/^refs\/remotes\/origin\//, '')
  .replace(/^origin\//, '');

const BIP_FILES = bipLinkIndex.bipFiles || {};
const SNAPSHOT_COMMITS = bipLinkIndex.snapshotCommits || {};
const SNAPSHOT_FILES = bipLinkIndex.snapshotFiles || {};

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

function getSnapshotCommit(snapshotLabel) {
  if (!snapshotLabel) {
    return '';
  }

  return SNAPSHOT_COMMITS[snapshotLabel] || '';
}

function getLatestKnownBipFileName(id) {
  const normalizedId = normalizeBipId(id);
  if (!normalizedId) {
    return '';
  }

  return BIP_FILES[normalizedId] || buildDefaultFileName(normalizedId);
}

function getSnapshotBipFileName(id, snapshotLabel) {
  const normalizedId = normalizeBipId(id);
  if (!normalizedId || !snapshotLabel) {
    return '';
  }

  return SNAPSHOT_FILES[snapshotLabel]?.[normalizedId] || '';
}

function buildRepositoryBipUrl(ref, fileName) {
  if (!BITCOIN_BIPS_REPOSITORY_URL || !ref || !fileName) {
    return '#';
  }

  return `${BITCOIN_BIPS_REPOSITORY_URL}/blob/${ref}/${fileName}`;
}

function buildRepositoryCommitUrl(commitHash) {
  if (!BITCOIN_BIPS_REPOSITORY_URL || !commitHash) {
    return '#';
  }

  return `${BITCOIN_BIPS_REPOSITORY_URL}/commit/${commitHash}`;
}

export function getBipUrl(id, snapshotLabel = null, options = {}) {
  const { linkMode = 'history' } = options;
  const normalizedId = normalizeBipId(id);

  if (linkMode === 'current') {
    return normalizedId && BIPS_DEV_BASE_URL ? `${BIPS_DEV_BASE_URL}/${normalizedId}/` : '#';
  }

  const snapshotFileName = getSnapshotBipFileName(normalizedId, snapshotLabel);
  if (snapshotLabel) {
    const commitHash = getSnapshotCommit(snapshotLabel);
    if (snapshotFileName && commitHash) {
      return buildRepositoryBipUrl(commitHash, snapshotFileName);
    }
  }

  const fileName = getLatestKnownBipFileName(normalizedId);
  return buildRepositoryBipUrl(BITCOIN_BIPS_DEFAULT_BRANCH, fileName);
}

export function getBipCommitUrl(commitHash, options = {}) {
  const {
    id = null,
    fallbackSnapshotLabel = null,
  } = options;
  const normalizedCommitHash = String(commitHash || '').trim();

  if (normalizedCommitHash) {
    return buildRepositoryCommitUrl(normalizedCommitHash);
  }

  return id == null ? '#' : getBipUrl(id, fallbackSnapshotLabel, { linkMode: 'history' });
}
