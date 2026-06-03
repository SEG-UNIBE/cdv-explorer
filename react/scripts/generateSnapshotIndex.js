const fs = require('fs');
const path = require('path');

const reactRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(reactRoot, '..');
const ipDataRoot = path.join(repoRoot, 'ip_data');
const outputDir = path.join(reactRoot, 'src', 'generated');
const outputPath = path.join(outputDir, 'snapshotIndex.json');
const tempOutputPath = path.join(outputDir, 'snapshotIndex.json.tmp');

function isSnapshotDirectoryName(name) {
  return /^\d{4}-\d{2}-\d{2}$/.test(name);
}

function listSnapshots(analysisRoot) {
  if (!fs.existsSync(analysisRoot)) {
    return [];
  }

  return fs.readdirSync(analysisRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && isSnapshotDirectoryName(entry.name))
    .map((entry) => entry.name)
    .sort((left, right) => right.localeCompare(left));
}

function findAnalysisRoots(ecosystemDir) {
  const directRoot = path.join(ecosystemDir, '03_analysis');
  if (fs.existsSync(directRoot)) {
    return [directRoot];
  }

  return fs.readdirSync(ecosystemDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(ecosystemDir, entry.name, '03_analysis'))
    .filter((analysisRoot) => fs.existsSync(analysisRoot));
}

function buildSnapshotIndex() {
  if (!fs.existsSync(ipDataRoot)) {
    return {};
  }

  const index = {};
  fs.readdirSync(ipDataRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .forEach((entry) => {
      const ecosystemId = entry.name;
      const ecosystemDir = path.join(ipDataRoot, ecosystemId);
      const snapshots = new Set();

      findAnalysisRoots(ecosystemDir).forEach((analysisRoot) => {
        listSnapshots(analysisRoot).forEach((snapshot) => snapshots.add(snapshot));
      });

      if (snapshots.size > 0) {
        index[ecosystemId] = Array.from(snapshots).sort((left, right) => right.localeCompare(left));
      }
    });

  return index;
}

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(tempOutputPath, `${JSON.stringify(buildSnapshotIndex(), null, 2)}\n`, 'utf8');
fs.renameSync(tempOutputPath, outputPath);
console.log(`Wrote ${path.relative(reactRoot, outputPath)}`);
