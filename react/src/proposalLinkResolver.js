import proposalLinkIndex from './generated/proposalLinkIndex.json';

function cleanRef(value) {
  return String(value || '')
    .replace(/^refs\/remotes\/origin\//, '')
    .replace(/^origin\//, '');
}

function cleanUrl(value) {
  return String(value || '').replace(/\/+$/, '');
}

export function getProposalLinkSource(ecosystemId) {
  return proposalLinkIndex?.[ecosystemId] || {};
}

export function getProposalLinkDefaultBranch(ecosystemId) {
  return cleanRef(getProposalLinkSource(ecosystemId).defaultBranch || 'master');
}

export function getRepositoryProposalUrl(ecosystemId, id, snapshotLabel = null, options = {}) {
  const {
    linkMode = 'history',
    buildDefaultFileName = () => '',
  } = options;
  const source = getProposalLinkSource(ecosystemId);
  const repositoryUrl = cleanUrl(source.repositoryUrl);
  const normalizedId = String(id || '').trim();

  if (!normalizedId) {
    return '#';
  }

  const currentBaseUrl = cleanUrl(source.currentBaseUrl);
  if (linkMode === 'current' && currentBaseUrl) {
    return `${currentBaseUrl}/${normalizedId}/`;
  }

  if (linkMode === 'history' && snapshotLabel) {
    const snapshotFileName = source.snapshotFiles?.[snapshotLabel]?.[normalizedId] || '';
    const commitHash = source.snapshotCommits?.[snapshotLabel] || '';
    if (repositoryUrl && snapshotFileName && commitHash) {
      return `${repositoryUrl}/blob/${commitHash}/${snapshotFileName}`;
    }
  }

  const fileName = source.files?.[normalizedId] || buildDefaultFileName(normalizedId);
  const defaultBranch = getProposalLinkDefaultBranch(ecosystemId);
  return repositoryUrl && defaultBranch && fileName
    ? `${repositoryUrl}/blob/${defaultBranch}/${fileName}`
    : '#';
}

export function getRepositoryCommitUrl(ecosystemId, commitHash, fallback = '#') {
  const repositoryUrl = cleanUrl(getProposalLinkSource(ecosystemId).repositoryUrl);
  const normalizedCommitHash = String(commitHash || '').trim();
  return repositoryUrl && normalizedCommitHash
    ? `${repositoryUrl}/commit/${normalizedCommitHash}`
    : fallback;
}
