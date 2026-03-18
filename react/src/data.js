const analysisContext = require.context('../../ip_data/bitcoin/03_analysis', true, /\.json$/);
const analysisFiles = analysisContext.keys();

const EMPTY_DATASET = {
  snapshot: null,
  nodes: [],
  links: {
    explicit_references: [],
    explicit_dependencies: {
      requires: [],
      replaces: [],
      superseded_by: [],
    },
    requires: [],
    replaces: [],
    superseded_by: [],
    implicit_dependencies: []
  },
  network: {
    nodes: [],
    links: {
      explicit_references: [],
      explicit_dependencies: [],
      requires: [],
      replaces: [],
      superseded_by: [],
      implicit_dependencies: [],
    },
  },
  dependencyMetrics: { by_approach: {}, pairwise_comparisons: {} },
  authorship: { meta: {}, top_authors: [], bips_per_year: [], top_10_share: {} },
  classification: { meta: {}, sankey_grouped: { links: [] }, status_over_time: {} },
  conformity: { per_proposal: [] }
};

function extractSnapshotLabel(filename) {
  const cleanPath = filename.replace(/^\.\//, '');
  const [firstSegment] = cleanPath.split('/');
  return /^\d{4}-\d{2}-\d{2}$/.test(firstSegment) ? firstSegment : 'current';
}

function countAllLinks(linksByType) {
  const links = linksByType || {};
  const explicit = links.explicit_dependencies || {};
  return (
    (links.explicit_references?.length || 0)
    + (links.implicit_dependencies?.length || 0)
    + (explicit.requires?.length || links.requires?.length || 0)
    + (explicit.replaces?.length || links.replaces?.length || 0)
    + (explicit.superseded_by?.length || links.superseded_by?.length || 0)
  );
}

function normalizeLinks(rawLinks) {
  const links = rawLinks || {};
  const explicitDependencies = links.explicit_dependencies || {};
  const requires = explicitDependencies.requires || links.requires || [];
  const replaces = explicitDependencies.replaces || links.replaces || [];
  const supersededBy = explicitDependencies.superseded_by || links.superseded_by || [];

  return {
    explicit_references: links.explicit_references || [],
    explicit_dependencies: {
      requires,
      replaces,
      superseded_by: supersededBy,
    },
    requires,
    replaces,
    superseded_by: supersededBy,
    implicit_dependencies: links.implicit_dependencies || [],
  };
}

function ensureSnapshotShape(snapshotLabel, snapshotData) {
  const network = snapshotData.network || EMPTY_DATASET.network;
  const links = normalizeLinks(network.links || EMPTY_DATASET.links);

  return {
    snapshot: snapshotLabel,
    nodes: network.nodes || [],
    links,
    network: {
      ...network,
      links,
    },
    dependencyMetrics: snapshotData.dependencyMetrics || EMPTY_DATASET.dependencyMetrics,
    authorship: snapshotData.authorship || EMPTY_DATASET.authorship,
    classification: snapshotData.classification || EMPTY_DATASET.classification,
    conformity: snapshotData.conformity || EMPTY_DATASET.conformity,
    meta: {
      node_count: network.nodes?.length || 0,
      link_count: countAllLinks(links),
      ...(snapshotData.meta || {}),
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
    const snapshotLabel = extractSnapshotLabel(filename);
    const submodule = segments[1];
    const artifactName = segments[2];

    if (!snapshots[snapshotLabel]) {
      snapshots[snapshotLabel] = {
        network: null,
        dependencyMetrics: null,
        authorship: null,
        classification: null,
        conformity: null,
        meta: {},
      };
    }

    if (submodule === 'dependencies' && artifactName === 'network_data.json') {
      snapshots[snapshotLabel].network = payload;
      snapshots[snapshotLabel].meta.node_count = payload?.nodes?.length || 0;
    }

    if (submodule === 'dependencies' && artifactName === 'dependency_metrics.json') {
      snapshots[snapshotLabel].dependencyMetrics = payload;
    }

    if (submodule === 'authorship' && artifactName === 'authorship_payload.json') {
      snapshots[snapshotLabel].authorship = payload;
      snapshots[snapshotLabel].meta.author_count = payload?.meta?.author_count || 0;
    }

    if (submodule === 'classification' && artifactName === 'classification_payload.json') {
      snapshots[snapshotLabel].classification = payload;
    }

    if (submodule === 'conformity' && artifactName === 'conformity_metrics.json') {
      snapshots[snapshotLabel].conformity = payload;
    }
  });

  return Object.fromEntries(
    Object.entries(snapshots).map(([snapshotLabel, snapshotData]) => [
      snapshotLabel,
      ensureSnapshotShape(snapshotLabel, snapshotData),
    ])
  );
}

const bitcoinSnapshotDatasets = collectBitcoinAnalysisSnapshots();

export function getAvailableSnapshots(ecosystemId) {
  if (ecosystemId !== 'bitcoin') {
    return [];
  }

  const datedEntries = Object.keys(bitcoinSnapshotDatasets)
    .filter((snapshot) => snapshot !== 'current')
    .sort((left, right) => right.localeCompare(left));

  if (datedEntries.length > 0) {
    return datedEntries;
  }

  return bitcoinSnapshotDatasets.current ? ['current'] : [];
}

export function getDatasetForSelection(ecosystemId, snapshot) {
  if (ecosystemId !== 'bitcoin') {
    return EMPTY_DATASET;
  }

  if (snapshot && bitcoinSnapshotDatasets[snapshot]) {
    return bitcoinSnapshotDatasets[snapshot];
  }

  const fallbackSnapshot = getAvailableSnapshots(ecosystemId)[0];
  return fallbackSnapshot ? bitcoinSnapshotDatasets[fallbackSnapshot] : EMPTY_DATASET;
}

export const data = getDatasetForSelection('bitcoin');
export default getDatasetForSelection('bitcoin');
