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

function listSnapshots(payloadRoot) {
  if (!fs.existsSync(payloadRoot)) {
    return [];
  }

  return fs.readdirSync(payloadRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && isSnapshotDirectoryName(entry.name))
    .map((entry) => entry.name)
    .sort((left, right) => right.localeCompare(left));
}

function findSourcePayloadRoots(ecosystemDir, ecosystemId) {
  const directRoot = path.join(ecosystemDir, '04_postprocess');
  if (fs.existsSync(directRoot)) {
    return [{ sourceSlug: ecosystemId, payloadRoot: directRoot }];
  }

  const sourceRoots = fs.readdirSync(ecosystemDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .filter((entry) => entry.name !== '_combined')
    .map((entry) => ({
      sourceSlug: entry.name,
      payloadRoot: path.join(ecosystemDir, entry.name, '04_postprocess'),
    }))
    .filter(({ payloadRoot }) => fs.existsSync(payloadRoot));

  const combinedRoot = path.join(ecosystemDir, '_combined');
  const combinedRoots = fs.existsSync(combinedRoot)
    ? fs.readdirSync(combinedRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => ({
        sourceSlug: entry.name,
        payloadRoot: path.join(combinedRoot, entry.name, '04_postprocess'),
      }))
      .filter(({ payloadRoot }) => fs.existsSync(payloadRoot))
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

      findSourcePayloadRoots(ecosystemDir, ecosystemId).forEach(({ sourceSlug, payloadRoot }) => {
        const snapshots = listSnapshots(payloadRoot);
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
