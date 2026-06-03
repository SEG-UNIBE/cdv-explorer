import {
  BODY_EXTRACTED_LLM,
  BODY_EXTRACTED_REGEX,
  PREAMBLE_EXTRACTED,
  normalizeDependencyLinks,
} from './dependencyApproaches';
import { ecosystemsById } from './ecosystems';
import snapshotIndex from './generated/snapshotIndex.json';

const EMPTY_DATASET = {
  snapshot: null,
  nodes: [],
  links: {
    [BODY_EXTRACTED_REGEX]: [],
    [PREAMBLE_EXTRACTED]: {
      requires: [],
      replaces: [],
      proposed_replacement: [],
    },
    requires: [],
    replaces: [],
    proposed_replacement: [],
    [BODY_EXTRACTED_LLM]: []
  },
  network: {
    nodes: [],
    links: {
      [BODY_EXTRACTED_REGEX]: [],
      [PREAMBLE_EXTRACTED]: [],
      requires: [],
      replaces: [],
      proposed_replacement: [],
      [BODY_EXTRACTED_LLM]: [],
    },
  },
  dependencyMetrics: { by_approach: {}, pairwise_comparisons: {} },
  authorship: { meta: {}, top_authors: [], bips_per_year: [], top_10_share: {} },
  classification: { meta: {}, sankey_grouped: { links: [] }, status_over_time: {} },
  evolution: { meta: {}, status_evolution: { categories: [], rows: [] } },
  conformity: { per_proposal: [] }
};

function countAllLinks(linksByType) {
  const links = linksByType || {};
  const explicit = links[PREAMBLE_EXTRACTED] || {};
  return (
    (links[BODY_EXTRACTED_REGEX]?.length || 0)
    + (links[BODY_EXTRACTED_LLM]?.length || 0)
    + (explicit.requires?.length || links.requires?.length || 0)
    + (explicit.replaces?.length || links.replaces?.length || 0)
    + (explicit.proposed_replacement?.length || links.proposed_replacement?.length || 0)
  );
}

function ensureSnapshotShape(snapshotLabel, snapshotData) {
  const network = snapshotData.network || EMPTY_DATASET.network;
  const links = normalizeDependencyLinks(network.links || EMPTY_DATASET.links);

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
    evolution: snapshotData.evolution || EMPTY_DATASET.evolution,
    conformity: snapshotData.conformity || EMPTY_DATASET.conformity,
    meta: {
      node_count: network.nodes?.length || 0,
      link_count: countAllLinks(links),
      ...(snapshotData.meta || {}),
    }
  };
}

function fetchJson(url) {
  return fetch(url).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
    return res.json();
  });
}

// In-memory cache: "<ecosystemId>/<snapshot>" → Promise<dataset>
// Promises are stored directly — awaiting a resolved promise is instant,
// so cache hits on already-loaded snapshots cost nothing.
const fetchCache = new Map();

export function isDatasetCached(ecosystemId, snapshot) {
  return fetchCache.has(`${ecosystemId}/${snapshot}`);
}

export function getAvailableSnapshots(ecosystemId) {
  return snapshotIndex[ecosystemId] || [];
}

export function fetchDatasetForSelection(ecosystemId, snapshot) {
  const ecosystem = ecosystemsById[ecosystemId];
  if (!ecosystem || ecosystem.status !== 'available' || !ecosystem.dataPath || !snapshot) {
    return Promise.resolve(EMPTY_DATASET);
  }

  const key = `${ecosystemId}/${snapshot}`;
  if (fetchCache.has(key)) return fetchCache.get(key);

  const base = `./${ecosystem.dataPath}/${snapshot}`;
  const promise = Promise.all([
    fetchJson(`${base}/dependencies/network_data.json`),
    fetchJson(`${base}/dependencies/dependency_metrics.json`),
    fetchJson(`${base}/authorship/authorship_payload.json`),
    fetchJson(`${base}/classification/classification_payload.json`),
    fetchJson(`${base}/evolution/evolution_payload.json`),
    fetchJson(`${base}/conformity/conformity_metrics.json`),
  ]).then(([network, dependencyMetrics, authorship, classification, evolution, conformity]) =>
    ensureSnapshotShape(snapshot, { network, dependencyMetrics, authorship, classification, evolution, conformity })
  ).catch((err) => {
    fetchCache.delete(key); // don't cache failures — allow retry on next attempt
    throw err;
  });

  fetchCache.set(key, promise);
  return promise;
}
