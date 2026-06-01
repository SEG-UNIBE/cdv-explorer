const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const reactRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(reactRoot, '..');
const externalLinksPath = path.join(reactRoot, 'src', 'externalLinks.json');
const analysisRoot = path.join(repoRoot, 'ip_data', 'bitcoin', '03_analysis');
const harvestRoot = path.join(repoRoot, 'ip_data', 'bitcoin', '01_harvest');
const outputDir = path.join(reactRoot, 'src', 'generated');
const outputPath = path.join(outputDir, 'bipLinkIndex.json');
const tempOutputPath = path.join(outputDir, 'bipLinkIndex.json.tmp');

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function normalizeBipId(value) {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }

  const match = text.match(/^(?:bip\s*[- ]*)?0*(\d+)$/i);
  return match ? String(Number(match[1])) : text;
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

function listBipFilesForCommit(localDir, commitHash) {
  if (!commitHash) {
    return {};
  }

  const tree = runGit(['-C', localDir, 'ls-tree', '-r', '--name-only', commitHash]);
  const bipFiles = {};

  tree
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((filePath) => {
      const fileName = path.posix.basename(filePath);
      const match = fileName.match(/^bip-(\d+)\.(md|mediawiki)$/i);
      if (!match) {
        return;
      }

      const normalizedId = normalizeBipId(match[1]);
      if (normalizedId && !bipFiles[normalizedId]) {
        bipFiles[normalizedId] = fileName;
      }
    });

  return bipFiles;
}

function buildIndex() {
  const externalLinks = fs.existsSync(externalLinksPath) ? readJson(externalLinksPath) : {};
  const branchRef = getDefaultBranchRef(harvestRoot);
  const defaultBranch = (branchRef || externalLinks.bitcoinBipsDefaultBranch || 'master')
    .replace(/^refs\/remotes\/origin\//, '')
    .replace(/^origin\//, '');
  const snapshotLabels = getSnapshotLabels();
  const snapshotCommits = {};
  const snapshotFiles = {};
  const bipFiles = {};

  snapshotLabels.forEach((snapshotLabel) => {
    const manifestPath = path.join(analysisRoot, snapshotLabel, 'bip_files.json');
    if (!fs.existsSync(manifestPath)) {
      return;
    }

    const manifest = readJson(manifestPath);
    const commitHash = String(manifest.commit || '').trim();
    const files = manifest.files && typeof manifest.files === 'object' ? manifest.files : {};
    if (!commitHash || Object.keys(files).length === 0) {
      return;
    }

    snapshotCommits[snapshotLabel] = commitHash;
    snapshotFiles[snapshotLabel] = files;
  });

  // Build bipFiles from the current HEAD so fallback links to master use the correct file names.
  // Building from snapshots is wrong: it uses the oldest known name per BIP, causing renamed
  // files (e.g. .mediawiki → .md) or BIPs added after all snapshots to resolve incorrectly.
  const headCommit = branchRef ? runGit(['-C', harvestRoot, 'rev-parse', branchRef]) : '';
  Object.assign(bipFiles, listBipFilesForCommit(harvestRoot, headCommit));

  return {
    repositoryUrl: externalLinks.bitcoinBipsRepositoryUrl || 'https://github.com/bitcoin/bips',
    defaultBranch,
    bipFiles,
    snapshotCommits,
    snapshotFiles,
  };
}

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(tempOutputPath, `${JSON.stringify(buildIndex(), null, 2)}\n`, 'utf8');
fs.renameSync(tempOutputPath, outputPath);
console.log(`Wrote ${path.relative(reactRoot, outputPath)}`);
