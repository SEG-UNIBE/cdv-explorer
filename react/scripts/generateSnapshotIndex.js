const fs = require('fs');
const path = require('path');

const reactRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(reactRoot, '..');
const ipDataRoot = path.join(repoRoot, 'ip_data');
const outputDir = path.join(reactRoot, 'src', 'generated');
const outputPath = path.join(outputDir, 'snapshotIndex.json');
const tempOutputPath = path.join(outputDir, `snapshotIndex.json.${process.pid}.tmp`);

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

function findSourceAnalysisRoots(ecosystemDir, ecosystemId) {
  const directRoot = path.join(ecosystemDir, '03_analysis');
  if (fs.existsSync(directRoot)) {
    return [{ sourceSlug: ecosystemId, analysisRoot: directRoot }];
  }

  const sourceRoots = fs.readdirSync(ecosystemDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .filter((entry) => entry.name !== '_combined')
    .map((entry) => ({
      sourceSlug: entry.name,
      analysisRoot: path.join(ecosystemDir, entry.name, '03_analysis'),
    }))
    .filter(({ analysisRoot }) => fs.existsSync(analysisRoot));

  const combinedRoot = path.join(ecosystemDir, '_combined');
  const combinedRoots = fs.existsSync(combinedRoot)
    ? fs.readdirSync(combinedRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => ({
        sourceSlug: entry.name,
        analysisRoot: path.join(combinedRoot, entry.name, '03_analysis'),
      }))
      .filter(({ analysisRoot }) => fs.existsSync(analysisRoot))
    : [];

  return sourceRoots.concat(combinedRoots);
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
      const bySource = {};

      findSourceAnalysisRoots(ecosystemDir, ecosystemId).forEach(({ sourceSlug, analysisRoot }) => {
        const snapshots = listSnapshots(analysisRoot);
        if (snapshots.length > 0) {
          bySource[sourceSlug] = snapshots;
        }
      });

      if (Object.keys(bySource).length > 0) {
        index[ecosystemId] = bySource;
      }
    });

  return index;
}

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(tempOutputPath, `${JSON.stringify(buildSnapshotIndex(), null, 2)}\n`, 'utf8');
fs.renameSync(tempOutputPath, outputPath);
console.log(`Wrote ${path.relative(reactRoot, outputPath)}`);
