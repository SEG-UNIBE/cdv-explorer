const analysisContext = require.context('../../ip_data/bitcoin/03_analysis', true, /\.json$/);
const analysisFiles = analysisContext.keys();

const EMPTY_DATASET = {
  stichtag: null,
  nodes: [],
  links: {
    references: [],
    dependencies: [],
    requires: [],
    replaces: [],
    superseded_by: []
  },
  network: { nodes: [], links: { references: [], dependencies: [], requires: [], replaces: [], superseded_by: [] } },
  authorship: { meta: {}, top_authors: [], bips_per_year: [], top_10_share: {} },
  classification: { meta: {}, sankey_grouped: { links: [] }, status_distribution_by_layer: {}, status_over_time: {} },
  conformity: { overall_average_score: null, score_distribution: [], average_score_by_status: {} }
};

function extractStichtag(filename) {
  const cleanPath = filename.replace(/^\.\//, '');
  const [firstSegment] = cleanPath.split('/');
  return /^\d{4}-\d{2}-\d{2}$/.test(firstSegment) ? firstSegment : 'current';
}

function countAllLinks(linksByType) {
  return Object.values(linksByType || {}).reduce((sum, items) => sum + (items?.length || 0), 0);
}

function ensureSnapshotShape(stichtag, snapshot) {
  const network = snapshot.network || EMPTY_DATASET.network;
  const links = network.links || EMPTY_DATASET.links;

  return {
    stichtag,
    nodes: network.nodes || [],
    links: {
      references: links.references || [],
      dependencies: links.dependencies || [],
      requires: links.requires || [],
      replaces: links.replaces || [],
      superseded_by: links.superseded_by || [],
    },
    network,
    authorship: snapshot.authorship || EMPTY_DATASET.authorship,
    classification: snapshot.classification || EMPTY_DATASET.classification,
    conformity: snapshot.conformity || EMPTY_DATASET.conformity,
    meta: {
      node_count: network.nodes?.length || 0,
      link_count: countAllLinks(links),
      ...(snapshot.meta || {}),
    }
  };
}

function collectBitcoinAnalysisSnapshots() {
  const snapshots = {};

  analysisFiles.forEach((filename) => {
    const moduleData = analysisContext(filename);
    const payload = moduleData.default || moduleData;

    const cleanPath = filename.replace(/^\.\//, '');
    const segments = cleanPath.split('/');
    const stichtag = extractStichtag(filename);
    const submodule = segments[1];
    const artifactName = segments[2];

    if (!snapshots[stichtag]) {
      snapshots[stichtag] = {
        network: null,
        authorship: null,
        classification: null,
        conformity: null,
        meta: {},
      };
    }

    if (submodule === 'dependencies' && artifactName === 'network_data.json') {
      snapshots[stichtag].network = payload;
      snapshots[stichtag].meta.node_count = payload?.nodes?.length || 0;
    }

    if (submodule === 'authorship' && artifactName === 'authorship_payload.json') {
      snapshots[stichtag].authorship = payload;
      snapshots[stichtag].meta.author_count = payload?.meta?.author_count || 0;
    }

    if (submodule === 'classification' && artifactName === 'classification_payload.json') {
      snapshots[stichtag].classification = payload;
    }

    if (submodule === 'conformity' && artifactName === 'conformity_metrics.json') {
      snapshots[stichtag].conformity = payload;
    }
  });

  return Object.fromEntries(
    Object.entries(snapshots).map(([stichtag, snapshot]) => [stichtag, ensureSnapshotShape(stichtag, snapshot)])
  );
}

const bitcoinSnapshotDatasets = collectBitcoinAnalysisSnapshots();

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

export const data = getDatasetForSelection('bitcoin');
export default getDatasetForSelection('bitcoin');
