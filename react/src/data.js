import {
  BODY_EXTRACTED_LLM,
  BODY_EXTRACTED_REGEX,
  PREAMBLE_EXTRACTED,
  normalizeDependencyLinks,
} from './dependencyApproaches';
import { ecosystemsById } from './ecosystems';
import snapshotIndex from './generated/snapshotIndex.json';

const EMPTY_LINKS = {
  [BODY_EXTRACTED_REGEX]: [],
  [PREAMBLE_EXTRACTED]: {
    requires: [],
    replaces: [],
    proposed_replacement: [],
  },
  requires: [],
  replaces: [],
  proposed_replacement: [],
  [BODY_EXTRACTED_LLM]: [],
};

const EMPTY_DATASET = {
  snapshot: null,
  sourceIds: [],
  bySource: {},
  nodes: [],
  links: EMPTY_LINKS,
  network: { nodes: [], links: EMPTY_LINKS },
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

function ensureSingleSourceShape(snapshotLabel, sourceId, snapshotData) {
  const network = snapshotData.network || { nodes: [], links: EMPTY_LINKS };
  const links = normalizeDependencyLinks(network.links || EMPTY_LINKS);
  const nodes = (network.nodes || []).map((node) => ({ ...node, source: sourceId }));

  return {
    snapshot: snapshotLabel,
    sourceIds: [sourceId],
    nodes,
    links,
    network: { ...network, nodes, links },
    dependencyMetrics: snapshotData.dependencyMetrics || EMPTY_DATASET.dependencyMetrics,
    authorship: snapshotData.authorship || EMPTY_DATASET.authorship,
    classification: snapshotData.classification || EMPTY_DATASET.classification,
    evolution: snapshotData.evolution || EMPTY_DATASET.evolution,
    conformity: snapshotData.conformity || EMPTY_DATASET.conformity,
    meta: {
      node_count: nodes.length,
      link_count: countAllLinks(links),
      ...(snapshotData.meta || {}),
    },
  };
}

function sumBy(rowsArrays, keyField, valueField) {
  const sums = new Map();
  rowsArrays.flat().forEach((row) => {
    if (!row || row[keyField] == null) return;
    const key = row[keyField];
    sums.set(key, (sums.get(key) || 0) + Number(row[valueField] || 0));
  });
  return Array.from(sums.entries()).map(([key, value]) => ({ [keyField]: key, [valueField]: value }));
}

function mergeAuthorship(perSourceDatasets) {
  const sources = perSourceDatasets.map((d) => d.authorship || {});

  const top_authors = sumBy(sources.map((s) => s.top_authors || []), 'author', 'count')
    .sort((a, b) => b.count - a.count);

  const bips_per_year = sumBy(sources.map((s) => s.bips_per_year || []), 'year', 'count')
    .sort((a, b) => a.year - b.year);

  const author_contribution_histogram = sumBy(
    sources.map((s) => s.author_contribution_histogram || []),
    'bips_written',
    'authors',
  ).sort((a, b) => Number(a.bips_written) - Number(b.bips_written));

  // bip_author_count_histogram is recomputed from dataset.nodes downstream in
  // buildDashboardData (so source-tagged refs can flow to tooltips); the merged
  // copy here is kept for completeness/back-compat and matches the source shape.
  const bip_author_count_histogram = sumBy(
    sources.map((s) => s.bip_author_count_histogram || []),
    'author_count',
    'bip_count',
  ).sort((a, b) => Number(a.author_count) - Number(b.author_count));

  const totalBips = sources.reduce((sum, s) => sum + Number(s.top_10_share?.total_bips || 0), 0);
  const topShare = sources.reduce((sum, s) => sum + Number(s.top_10_share?.bips_by_top_10_authors || 0), 0);

  const collaborationNetwork = (() => {
    const nodes = [];
    const seenNodes = new Set();
    const edges = [];
    sources.forEach((s) => {
      (s.collaboration_network?.nodes || []).forEach((node) => {
        const id = String(node.id || '');
        if (!id || seenNodes.has(id)) return;
        seenNodes.add(id);
        nodes.push(node);
      });
      (s.collaboration_network?.edges || []).forEach((edge) => edges.push(edge));
    });
    return { nodes, edges };
  })();

  const centralityByAuthor = new Map();
  sources.forEach((s) => {
    (s.collaboration_centrality || []).forEach((entry) => {
      if (!entry?.author) return;
      const existing = centralityByAuthor.get(entry.author);
      if (!existing) {
        centralityByAuthor.set(entry.author, { ...entry });
      }
    });
  });

  return {
    meta: {
      author_count: top_authors.length,
      node_count: perSourceDatasets.reduce((sum, d) => sum + (d.nodes?.length || 0), 0),
    },
    top_authors,
    bips_per_year,
    author_contribution_histogram,
    bip_author_count_histogram,
    top_10_share: {
      total_bips: totalBips,
      bips_by_top_10_authors: topShare,
      percentage: totalBips > 0 ? (topShare / totalBips) * 100 : 0,
    },
    collaboration_network: collaborationNetwork,
    collaboration_centrality: Array.from(centralityByAuthor.values()),
  };
}

function mergeLinks(perSourceDatasets) {
  const merged = {
    [BODY_EXTRACTED_REGEX]: [],
    [BODY_EXTRACTED_LLM]: [],
    [PREAMBLE_EXTRACTED]: { requires: [], replaces: [], proposed_replacement: [] },
    requires: [],
    replaces: [],
    proposed_replacement: [],
  };
  perSourceDatasets.forEach((d) => {
    const links = d.links || {};
    merged[BODY_EXTRACTED_REGEX].push(...(links[BODY_EXTRACTED_REGEX] || []));
    merged[BODY_EXTRACTED_LLM].push(...(links[BODY_EXTRACTED_LLM] || []));
    const explicit = links[PREAMBLE_EXTRACTED] || {};
    merged[PREAMBLE_EXTRACTED].requires.push(...(explicit.requires || links.requires || []));
    merged[PREAMBLE_EXTRACTED].replaces.push(...(explicit.replaces || links.replaces || []));
    merged[PREAMBLE_EXTRACTED].proposed_replacement.push(...(explicit.proposed_replacement || links.proposed_replacement || []));
  });
  // Keep flat aliases in sync with the explicit-preamble bucket so legacy
  // consumers reading `links.requires` continue to work.
  merged.requires = merged[PREAMBLE_EXTRACTED].requires;
  merged.replaces = merged[PREAMBLE_EXTRACTED].replaces;
  merged.proposed_replacement = merged[PREAMBLE_EXTRACTED].proposed_replacement;
  return merged;
}

function buildMergedDataset(snapshotLabel, entries) {
  const perSourceDatasets = entries.map(([, ds]) => ds);
  const bySource = Object.fromEntries(entries);
  const sourceIds = entries.map(([id]) => id);

  if (entries.length === 1) {
    return { ...perSourceDatasets[0], bySource, sourceIds };
  }

  const nodes = perSourceDatasets.flatMap((d) => d.nodes || []);
  const links = mergeLinks(perSourceDatasets);
  const primary = perSourceDatasets[0];

  return {
    snapshot: snapshotLabel,
    sourceIds,
    bySource,
    nodes,
    links,
    network: { nodes, links },
    authorship: mergeAuthorship(perSourceDatasets),
    // Non-mergeable payloads (different schemas per source) — top-level holds
    // the primary source's data so single-source-style components keep working;
    // tabbed sections read `bySource` for per-source rendering.
    classification: primary.classification,
    evolution: primary.evolution,
    conformity: primary.conformity,
    dependencyMetrics: primary.dependencyMetrics,
    meta: {
      node_count: nodes.length,
      link_count: countAllLinks(links),
    },
  };
}

function fetchJson(url) {
  return fetch(url).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
    return res.json();
  });
}

function resolveSourcesForIds(ecosystemId, sourceIds) {
  const ecosystem = ecosystemsById[ecosystemId];
  if (!ecosystem) return { ecosystem: null, sources: [] };
  const ids = Array.isArray(sourceIds) && sourceIds.length > 0
    ? sourceIds
    : [ecosystem.defaultSourceId];
  const sources = ids
    .map((id) => [id, ecosystem.sources?.[id]])
    .filter(([, source]) => Boolean(source));
  return { ecosystem, sources };
}

// In-memory cache: "<ecosystemId>/<sourceSlug>/<snapshot>" → Promise<dataset>
const fetchCache = new Map();

function makeCacheKey(ecosystemId, sourceSlug, snapshot) {
  return `${ecosystemId}/${sourceSlug}/${snapshot}`;
}

function fetchSingleSourceDataset(ecosystemId, source, sourceId, snapshot) {
  const key = makeCacheKey(ecosystemId, source.sourceSlug, snapshot);
  if (fetchCache.has(key)) return fetchCache.get(key);

  const base = `./${source.dataPath}/${snapshot}`;
  const promise = Promise.all([
    fetchJson(`${base}/dependencies/network_data.json`),
    fetchJson(`${base}/dependencies/dependency_metrics.json`),
    fetchJson(`${base}/authorship/authorship_payload.json`),
    fetchJson(`${base}/classification/classification_payload.json`),
    fetchJson(`${base}/evolution/evolution_payload.json`),
    fetchJson(`${base}/conformity/conformity_metrics.json`),
  ]).then(([network, dependencyMetrics, authorship, classification, evolution, conformity]) =>
    ensureSingleSourceShape(snapshot, sourceId, {
      network, dependencyMetrics, authorship, classification, evolution, conformity,
    })
  ).catch((err) => {
    fetchCache.delete(key);
    throw err;
  });

  fetchCache.set(key, promise);
  return promise;
}

export function isDatasetCached(ecosystemId, snapshot, sourceIds = null) {
  const { sources } = resolveSourcesForIds(ecosystemId, sourceIds);
  if (sources.length === 0) return false;
  return sources.every(([, source]) => fetchCache.has(makeCacheKey(ecosystemId, source.sourceSlug, snapshot)));
}

export function getAvailableSnapshots(ecosystemId, sourceIds = null) {
  const { sources } = resolveSourcesForIds(ecosystemId, sourceIds);
  if (sources.length === 0) return [];
  const lists = sources.map(([, source]) => snapshotIndex[ecosystemId]?.[source.sourceSlug] || []);
  if (lists.length === 1) return lists[0];
  // Intersection across selected sources, preserving the first source's ordering.
  const others = lists.slice(1).map((list) => new Set(list));
  return lists[0].filter((snapshot) => others.every((set) => set.has(snapshot)));
}

export function fetchDatasetForSelection(ecosystemId, snapshot, sourceIds = null) {
  const { ecosystem, sources } = resolveSourcesForIds(ecosystemId, sourceIds);
  if (!ecosystem || ecosystem.status !== 'available' || sources.length === 0 || !snapshot) {
    return Promise.resolve(EMPTY_DATASET);
  }

  return Promise.all(
    sources.map(([id, source]) => fetchSingleSourceDataset(ecosystemId, source, id, snapshot)
      .then((dataset) => [id, dataset])),
  ).then((entries) => buildMergedDataset(snapshot, entries));
}
