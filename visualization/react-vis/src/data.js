const context = require.context('../../../bips_json', true, /\.json$/);
const allFiles = context.keys();

const EMPTY_DATASET = {
  nodes: [],
  links: {
    references: [],
    dependencies: [],
    requires: [],
    replaces: [],
    superseded_by: []
  }
};

// Utility: Normalize "BIP 123", "BIP-123", "123, 124" => ["123", "124"]
function normalizeBipIds(field) {
  if (!field) return [];

  const rawItems = Array.isArray(field)
    ? field
    : String(field).split(',');

  return rawItems
    .map(item => String(item).trim())
    .filter(item => item.length > 0)
    .map(item => item.replace(/^BIP[-\s]*/i, ''))
    .filter(id => /^\d+$/.test(id)); // only numeric strings
}

function extractStichtag(filename) {
  const cleanPath = filename.replace(/^\.\//, '');
  const [firstSegment] = cleanPath.split('/');
  return /^\d{4}-\d{2}-\d{2}$/.test(firstSegment) ? firstSegment : 'current';
}

function buildNetworkData(snapshotEntries) {
  if (!snapshotEntries.length) {
    return EMPTY_DATASET;
  }

  const nodes = [];
  const nodeIds = new Set();
  const referenceLinks = [];
  const dependencyLinks = [];
  const requiresLinks = [];
  const replacesLinks = [];
  const supersedesLinks = [];

  snapshotEntries.forEach((bip) => {
    const preamble = bip?.raw?.preamble;
    const insights = bip?.insights || {};
    const normalizedBipId = String(preamble?.bip ?? '').trim();

    if (!normalizedBipId || nodeIds.has(normalizedBipId)) {
      return;
    }

    nodes.push({
      id: normalizedBipId,
      group: preamble.layer,
      compliance_score: preamble.compliance_score,
      created: preamble.created,
      author: preamble.author,
      word_list: insights.word_list,
      status: preamble.status,
      type: preamble.type
    });
    nodeIds.add(normalizedBipId);
  });

  snapshotEntries.forEach((bip) => {
    const preamble = bip?.raw?.preamble;
    const insights = bip?.insights || {};
    const sourceId = String(preamble?.bip ?? '').trim();

    if (!sourceId || !nodeIds.has(sourceId)) {
      return;
    }

    normalizeBipIds(insights.bip_references).forEach((targetId) => {
      if (nodeIds.has(targetId)) {
        referenceLinks.push({ source: sourceId, target: targetId, value: 1 });
      }
    });

    normalizeBipIds(insights.dependencies).forEach((targetId) => {
      if (nodeIds.has(targetId)) {
        dependencyLinks.push({ source: sourceId, target: targetId, value: 1 });
      }
    });

    normalizeBipIds(preamble.requires).forEach((targetId) => {
      if (nodeIds.has(targetId)) {
        requiresLinks.push({ source: sourceId, target: targetId, value: 1 });
      }
    });

    normalizeBipIds(preamble.replaces).forEach((targetId) => {
      if (nodeIds.has(targetId)) {
        replacesLinks.push({ source: sourceId, target: targetId, value: 1 });
      }
    });

    normalizeBipIds(preamble.superseded_by).forEach((targetId) => {
      if (nodeIds.has(targetId)) {
        supersedesLinks.push({ source: sourceId, target: targetId, value: 1 });
      }
    });
  });

  return {
    nodes,
    links: {
      references: referenceLinks,
      dependencies: dependencyLinks,
      requires: requiresLinks,
      replaces: replacesLinks,
      superseded_by: supersedesLinks
    }
  };
}

const bitcoinSnapshots = allFiles.reduce((accumulator, filename) => {
  const snapshotKey = extractStichtag(filename);
  const moduleData = context(filename);
  const snapshotEntries = accumulator[snapshotKey] || [];
  snapshotEntries.push(moduleData.default || moduleData);
  accumulator[snapshotKey] = snapshotEntries;
  return accumulator;
}, {});

const bitcoinSnapshotDatasets = Object.fromEntries(
  Object.entries(bitcoinSnapshots).map(([stichtag, entries]) => [stichtag, buildNetworkData(entries)])
);

export function getAvailableStichtage(ecosystemId) {
  if (ecosystemId !== 'bitcoin') {
    return [];
  }

  const datedEntries = Object.keys(bitcoinSnapshotDatasets)
    .filter((stichtag) => stichtag !== 'current')
    .sort((left, right) => right.localeCompare(left));

  if (datedEntries.length > 0) {
    return datedEntries;
  }

  return bitcoinSnapshotDatasets.current ? ['current'] : [];
}

export function getDatasetForSelection(ecosystemId, stichtag) {
  if (ecosystemId !== 'bitcoin') {
    return EMPTY_DATASET;
  }

  if (stichtag && bitcoinSnapshotDatasets[stichtag]) {
    return bitcoinSnapshotDatasets[stichtag];
  }

  const fallbackStichtag = getAvailableStichtage(ecosystemId)[0];
  return fallbackStichtag ? bitcoinSnapshotDatasets[fallbackStichtag] : EMPTY_DATASET;
}

export default getDatasetForSelection('bitcoin');
