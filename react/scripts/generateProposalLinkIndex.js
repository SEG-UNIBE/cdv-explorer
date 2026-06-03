const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const reactRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(reactRoot, '..');
const ecosystemsRoot = path.join(repoRoot, 'ecosystems');
const outputDir = path.join(reactRoot, 'src', 'generated');
const outputPath = path.join(outputDir, 'proposalLinkIndex.json');
const tempOutputPath = path.join(outputDir, `proposalLinkIndex.json.${process.pid}.tmp`);
const externalLinksPath = path.join(reactRoot, 'src', 'externalLinks.json');

function readJson(filePath, fallback = {}) {
  if (!fs.existsSync(filePath)) {
    return fallback;
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function stripYamlValue(value) {
  return String(value || '')
    .trim()
    .replace(/^['"]|['"]$/g, '');
}

function parseEcosystemYaml(filePath) {
  const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/);
  const ecosystem = { slug: path.basename(filePath, '.yml'), sources: {} };
  let inSources = false;
  let currentSource = null;

  lines.forEach((line) => {
    if (!line.trim() || line.trim().startsWith('#')) {
      return;
    }

    const rootMatch = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (rootMatch) {
      const [, key, value] = rootMatch;
      inSources = key === 'sources';
      currentSource = null;
      if (key === 'slug' && value.trim()) {
        ecosystem.slug = stripYamlValue(value);
      }
      return;
    }

    if (!inSources) {
      return;
    }

    const sourceMatch = line.match(/^  ([A-Za-z0-9_-]+):\s*$/);
    if (sourceMatch) {
      currentSource = sourceMatch[1];
      ecosystem.sources[currentSource] = {};
      return;
    }

    const sourceValueMatch = line.match(/^    ([A-Za-z0-9_-]+):\s*(.*)$/);
    if (currentSource && sourceValueMatch) {
      const [, key, value] = sourceValueMatch;
      if (value.trim()) {
        ecosystem.sources[currentSource][key] = stripYamlValue(value);
      }
    }
  });

  return ecosystem;
}

function runGit(localDir, args, fallback = '') {
  if (!fs.existsSync(path.join(localDir, '.git'))) {
    return fallback;
  }
  try {
    return execFileSync('git', ['-C', localDir, ...args], {
      cwd: repoRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return fallback;
  }
}

function normalizeBranchRef(ref) {
  return String(ref || '')
    .replace(/^refs\/remotes\/origin\//, '')
    .replace(/^origin\//, '');
}

function getDefaultBranch(localDir, fallback = 'master') {
  const symbolicRef = runGit(localDir, ['symbolic-ref', 'refs/remotes/origin/HEAD']);
  if (symbolicRef) {
    return normalizeBranchRef(symbolicRef);
  }

  for (const candidate of ['origin/master', 'origin/main']) {
    const verified = runGit(localDir, ['rev-parse', '--verify', candidate]);
    if (verified) {
      return normalizeBranchRef(candidate);
    }
  }

  return fallback;
}

function listSnapshotLabels(analysisRoot) {
  if (!fs.existsSync(analysisRoot)) {
    return [];
  }

  return fs.readdirSync(analysisRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(entry.name))
    .map((entry) => entry.name)
    .sort();
}

function normalizeIdFromManifestKey(value, acronym) {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }
  if (acronym === 'NIP') {
    return text.toUpperCase().padStart(text.length === 1 ? 2 : text.length, '0');
  }
  const numeric = Number(text);
  return Number.isFinite(numeric) ? String(numeric) : text.toUpperCase();
}

function normalizeIdFromFileName(fileName, source) {
  const acronym = String(source.proposal_acronym || '').toUpperCase();
  const prefix = String(source.document_prefix || '').toLowerCase();
  const basename = path.posix.basename(fileName);

  if (acronym === 'NIP') {
    const match = basename.match(/^([0-9A-Fa-f]{1,3})\.md$/);
    return match ? match[1].toUpperCase().padStart(match[1].length === 1 ? 2 : match[1].length, '0') : '';
  }

  const prefixedMatch = basename.match(new RegExp(`^${prefix}-(\\d+)\\.(?:md|mediawiki|rst)$`, 'i'));
  if (prefixedMatch) {
    return String(Number(prefixedMatch[1]));
  }

  return '';
}

function buildSnapshotFiles(manifestFiles, source) {
  const files = {};
  Object.entries(manifestFiles || {}).forEach(([rawId, fileName]) => {
    const normalizedId = normalizeIdFromManifestKey(rawId, source.proposal_acronym);
    if (normalizedId) {
      files[normalizedId] = String(fileName);
    }
  });
  return files;
}

function listFilesForCommit(localDir, commitHash, source) {
  if (!commitHash) {
    return {};
  }

  const tree = runGit(localDir, ['ls-tree', '-r', '--name-only', commitHash]);
  const files = {};

  tree
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((filePath) => {
      const fileName = path.posix.basename(filePath);
      const normalizedId = normalizeIdFromFileName(fileName, source);
      if (normalizedId && !files[normalizedId]) {
        files[normalizedId] = fileName;
      }
    });

  return files;
}

function buildSourceIndex(ecosystemId, source, existingSourceIndex = {}) {
  const externalLinks = readJson(externalLinksPath, {});
  const harvestRoot = path.resolve(repoRoot, source.harvest || '');
  const analysisRoot = path.resolve(repoRoot, source.analysis || '');
  const repositoryUrl = existingSourceIndex.repositoryUrl
    || `https://github.com/${source.repository_owner}/${source.repository_name}`;
  const fallbackBranch = existingSourceIndex.defaultBranch
    || (ecosystemId === 'bitcoin' ? externalLinks.bitcoinBipsDefaultBranch : '')
    || 'master';
  const defaultBranch = getDefaultBranch(harvestRoot, fallbackBranch);
  const snapshotLabels = listSnapshotLabels(analysisRoot);
  const snapshotCommits = {};
  const snapshotFiles = {};
  const files = { ...(existingSourceIndex.files || {}) };

  snapshotLabels.forEach((snapshotLabel) => {
    const manifestPath = path.join(analysisRoot, snapshotLabel, `${source.document_prefix}_files.json`);
    if (!fs.existsSync(manifestPath)) {
      return;
    }
    const manifest = readJson(manifestPath, {});
    const commitHash = String(manifest.commit || '').trim();
    const manifestFiles = buildSnapshotFiles(manifest.files, source);
    if (!commitHash || Object.keys(manifestFiles).length === 0) {
      return;
    }
    snapshotCommits[snapshotLabel] = commitHash;
    snapshotFiles[snapshotLabel] = manifestFiles;
  });

  const headCommit = runGit(harvestRoot, ['rev-parse', `origin/${defaultBranch}`]);
  Object.assign(files, listFilesForCommit(harvestRoot, headCommit, source));
  if (Object.keys(files).length === 0) {
    const newestSnapshot = snapshotLabels[snapshotLabels.length - 1];
    Object.assign(files, snapshotFiles[newestSnapshot] || {});
  }

  return {
    sourceSlug: source.sourceSlug,
    acronym: source.proposal_acronym,
    repositoryUrl,
    defaultBranch,
    files,
    snapshotCommits,
    snapshotFiles,
    currentBaseUrl: ecosystemId === 'bitcoin' ? externalLinks.bipsDevBaseUrl : '',
  };
}

function buildIndex() {
  const index = {};
  const existingIndex = readJson(outputPath, {});
  const ecosystemFiles = fs.existsSync(ecosystemsRoot)
    ? fs.readdirSync(ecosystemsRoot).filter((fileName) => fileName.endsWith('.yml')).sort()
    : [];

  ecosystemFiles.forEach((fileName) => {
    const ecosystem = parseEcosystemYaml(path.join(ecosystemsRoot, fileName));
    const sourceEntries = Object.entries(ecosystem.sources || {});
    if (sourceEntries.length === 0) {
      return;
    }

    const [sourceSlug, source] = sourceEntries[0];
    index[ecosystem.slug] = buildSourceIndex(ecosystem.slug, {
      ...source,
      sourceSlug,
    }, existingIndex[ecosystem.slug] || {});
  });

  return index;
}

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(tempOutputPath, `${JSON.stringify(buildIndex(), null, 2)}\n`, 'utf8');
fs.renameSync(tempOutputPath, outputPath);
console.log(`Wrote ${path.relative(reactRoot, outputPath)}`);
