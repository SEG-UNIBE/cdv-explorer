const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const reactRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(reactRoot, '..');
const analysisRoot = path.join(repoRoot, 'ip_data', 'nostr', 'nips', '03_analysis');
const harvestRoot = path.join(repoRoot, 'ip_data', 'nostr', 'nips', '01_harvest');
const outputDir = path.join(reactRoot, 'src', 'generated');
const outputPath = path.join(outputDir, 'nipLinkIndex.json');
const tempOutputPath = path.join(outputDir, 'nipLinkIndex.json.tmp');

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function runGit(args, fallback = '') {
  try {
    return execFileSync('git', args, {
      cwd: repoRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return fallback;
  }
}

function getDefaultBranchRef(localDir) {
  const symbolicRef = runGit(['-C', localDir, 'symbolic-ref', 'refs/remotes/origin/HEAD']);
  if (symbolicRef) {
    return symbolicRef;
  }

  for (const candidate of ['origin/master', 'origin/main']) {
    const verified = runGit(['-C', localDir, 'rev-parse', '--verify', candidate]);
    if (verified) {
      return candidate;
    }
  }

  return '';
}

function getSnapshotLabels() {
  if (!fs.existsSync(analysisRoot)) {
    return [];
  }

  return fs.readdirSync(analysisRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(entry.name))
    .map((entry) => entry.name)
    .sort();
}

function normalizeNipIdFromFileName(fileName) {
  const match = path.posix.basename(fileName).match(/^([0-9A-Fa-f]{2,3})\.md$/);
  return match ? match[1].toUpperCase() : '';
}

function listNipFilesForCommit(localDir, commitHash) {
  if (!commitHash) {
    return {};
  }

  const tree = runGit(['-C', localDir, 'ls-tree', '-r', '--name-only', commitHash]);
  const nipFiles = {};

  tree
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((filePath) => {
      const fileName = path.posix.basename(filePath);
      const normalizedId = normalizeNipIdFromFileName(fileName);
      if (normalizedId && !nipFiles[normalizedId]) {
        nipFiles[normalizedId] = fileName;
      }
    });

  return nipFiles;
}

function buildSnapshotFiles(manifestFiles) {
  const snapshotFiles = {};

  Object.values(manifestFiles || {}).forEach((fileName) => {
    const normalizedId = normalizeNipIdFromFileName(fileName);
    if (normalizedId) {
      snapshotFiles[normalizedId] = String(fileName);
    }
  });

  return snapshotFiles;
}

function buildIndex() {
  const branchRef = getDefaultBranchRef(harvestRoot);
  const defaultBranch = (branchRef || 'master')
    .replace(/^refs\/remotes\/origin\//, '')
    .replace(/^origin\//, '');
  const snapshotLabels = getSnapshotLabels();
  const snapshotCommits = {};
  const snapshotFiles = {};
  const nipFiles = {};

  snapshotLabels.forEach((snapshotLabel) => {
    const manifestPath = path.join(analysisRoot, snapshotLabel, 'nip_files.json');
    if (!fs.existsSync(manifestPath)) {
      return;
    }

    const manifest = readJson(manifestPath);
    const commitHash = String(manifest.commit || '').trim();
    const files = buildSnapshotFiles(manifest.files);
    if (!commitHash || Object.keys(files).length === 0) {
      return;
    }

    snapshotCommits[snapshotLabel] = commitHash;
    snapshotFiles[snapshotLabel] = files;
  });

  const headCommit = branchRef ? runGit(['-C', harvestRoot, 'rev-parse', branchRef]) : '';
  Object.assign(nipFiles, listNipFilesForCommit(harvestRoot, headCommit));

  return {
    repositoryUrl: 'https://github.com/nostr-protocol/nips',
    defaultBranch,
    nipFiles,
    snapshotCommits,
    snapshotFiles,
  };
}

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(tempOutputPath, `${JSON.stringify(buildIndex(), null, 2)}\n`, 'utf8');
fs.renameSync(tempOutputPath, outputPath);
console.log(`Wrote ${path.relative(reactRoot, outputPath)}`);
