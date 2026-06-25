import proposalLinkIndex from './generated/proposalLinkIndex.json';

function cleanRef(value) {
  return String(value || '')
    .replace(/^refs\/remotes\/origin\//, '')
    .replace(/^origin\//, '');
}

function cleanUrl(value) {
  return String(value || '').replace(/\/+$/, '');
}

function normalizeProposalId(value, source) {
  const text = String(value ?? '').trim();
  if (!text) {
    return '';
  }

  const acronym = String(source.acronym || '').trim();
  if (acronym.toUpperCase() === 'NIP') {
    const nipMatch = text.match(new RegExp(`^(?:${acronym}\\s*[- ]*)?([0-9a-f]{1,3})$`, 'i'));
    return nipMatch ? nipMatch[1].toUpperCase().padStart(2, '0') : text.toUpperCase();
  }

  if (acronym) {
    const numericMatch = text.match(new RegExp(`^(?:${acronym}\\s*[- ]*)?0*(\\d+)$`, 'i'));
    if (numericMatch) {
      return String(Number(numericMatch[1]));
    }
  }

  return text;
}

export function getProposalLinkSource(ecosystemId, sourceSlug = null) {
  const ecosystem = proposalLinkIndex?.[ecosystemId] || {};
  const resolvedSourceSlug = sourceSlug || ecosystem.defaultSource;
  return ecosystem.sources?.[resolvedSourceSlug] || {};
}

export function getProposalLinkDefaultBranch(ecosystemId, sourceSlug = null) {
  return cleanRef(getProposalLinkSource(ecosystemId, sourceSlug).defaultBranch || 'master');
}

export function getRepositoryProposalUrl(ecosystemId, id, snapshotLabel = null, options = {}) {
  const {
    linkMode = 'history',
    buildDefaultFileName = () => '',
    sourceSlug = null,
  } = options;
  const source = getProposalLinkSource(ecosystemId, sourceSlug);
  const repositoryUrl = cleanUrl(source.repositoryUrl);
  const normalizedId = normalizeProposalId(id, source);

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
  const defaultBranch = getProposalLinkDefaultBranch(ecosystemId, sourceSlug);
  return repositoryUrl && defaultBranch && fileName
    ? `${repositoryUrl}/blob/${defaultBranch}/${fileName}`
    : '#';
}

export function getRepositoryCommitUrl(ecosystemId, commitHash, fallback = '#', sourceSlug = null) {
  const repositoryUrl = cleanUrl(getProposalLinkSource(ecosystemId, sourceSlug).repositoryUrl);
  const normalizedCommitHash = String(commitHash || '').trim();
  return repositoryUrl && normalizedCommitHash
    ? `${repositoryUrl}/commit/${normalizedCommitHash}`
    : fallback;
}
