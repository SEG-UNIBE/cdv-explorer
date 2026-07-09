const fs = require('fs');
const path = require('path');

const reactRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(reactRoot, '..');
const generatedDir = path.join(reactRoot, 'src', 'generated');
const targetRoot = path.join(reactRoot, 'public', 'ip_data');

// The exact per-snapshot payloads fetched at runtime — keep in sync with
// fetchSingleSourceDataset / fetchCombinedSourceDataset in src/data.js.
const DATASET_FILES = [
  'dependencies/network_data.json',
  'dependencies/dependency_metrics.json',
  'authorship/authorship_payload.json',
  'classification/classification_payload.json',
  'evolution/evolution_payload.json',
  'conformity/conformity_metrics.json',
];

function readGeneratedJson(fileName) {
  const filePath = path.join(generatedDir, fileName);
  if (!fs.existsSync(filePath)) {
    console.error(`Missing ${path.relative(reactRoot, filePath)} - run the generate:indexes scripts first.`);
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function getCombinedDataPath(ecosystemId, combinationKey) {
  return `ip_data/${ecosystemId}/_combined/${combinationKey}/04_postprocess`;
}

function collectDataRoots(ecosystems, snapshotIndex) {
  const dataRoots = [];

  ecosystems.forEach((ecosystem) => {
    const bySource = snapshotIndex[ecosystem.id] || {};

    Object.values(ecosystem.sources || {}).forEach((source) => {
      const snapshots = bySource[source.sourceSlug] || [];
      if (source.dataPath && snapshots.length > 0) {
        dataRoots.push({ dataPath: source.dataPath, snapshots });
      }
    });

    Object.entries(bySource)
      .filter(([sourceSlug]) => sourceSlug.includes('+'))
      .forEach(([combinationKey, snapshots]) => {
        dataRoots.push({ dataPath: getCombinedDataPath(ecosystem.id, combinationKey), snapshots });
      });
  });

  return dataRoots;
}

function resetTargetRoot() {
  if (!fs.existsSync(path.dirname(targetRoot))) {
    fs.mkdirSync(path.dirname(targetRoot), { recursive: true });
  }
  const stats = fs.lstatSync(targetRoot, { throwIfNoEntry: false });
  if (!stats) {
    return;
  }
  if (stats.isSymbolicLink()) {
    fs.unlinkSync(targetRoot);
    return;
  }
  fs.rmSync(targetRoot, { recursive: true, force: true });
}

function syncPublicData() {
  const ecosystems = readGeneratedJson('ecosystems.json');
  const snapshotIndex = readGeneratedJson('snapshotIndex.json');
  const dataRoots = collectDataRoots(ecosystems, snapshotIndex);

  resetTargetRoot();

  let copiedFiles = 0;
  let copiedBytes = 0;
  const missing = [];

  dataRoots.forEach(({ dataPath, snapshots }) => {
    snapshots.forEach((snapshot) => {
      DATASET_FILES.forEach((relativeFile) => {
        const sourceFile = path.join(repoRoot, dataPath, snapshot, relativeFile);
        if (!fs.existsSync(sourceFile)) {
          missing.push(path.relative(repoRoot, sourceFile));
          return;
        }
        const targetFile = path.join(reactRoot, 'public', dataPath, snapshot, relativeFile);
        fs.mkdirSync(path.dirname(targetFile), { recursive: true });
        fs.copyFileSync(sourceFile, targetFile);
        copiedFiles += 1;
        copiedBytes += fs.statSync(targetFile).size;
      });
    });
  });

  const totalMb = (copiedBytes / (1024 * 1024)).toFixed(1);
  console.log(`Synced ${copiedFiles} dataset files (${totalMb} MB) to ${path.relative(reactRoot, targetRoot)}`);
  if (missing.length > 0) {
    console.warn(`Warning: ${missing.length} expected dataset file(s) not found:`);
    missing.forEach((file) => console.warn(`  - ${file}`));
  }
}

syncPublicData();
