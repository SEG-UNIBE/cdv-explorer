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
  [PREAMBLE_EXTRACTED]: {},
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

export function buildProposalGraphId(sourceSlug, proposalId) {
  const sourcePart = String(sourceSlug || '').trim();
  const idPart = String(proposalId ?? '').trim();
  return sourcePart ? `${sourcePart}:${idPart}` : idPart;
}

function parseProposalGraphKey(value) {
  const text = String(value ?? '').trim();
  const separatorIndex = text.indexOf(':');
  if (separatorIndex <= 0) {
    return { graphSource: null, proposalId: text };
  }
  return {
    graphSource: text.slice(0, separatorIndex),
    proposalId: text.slice(separatorIndex + 1),
  };
}

function buildSourceIdBySlug(ecosystem) {
  return Object.fromEntries(
    Object.entries(ecosystem?.sources || {}).map(([sourceId, source]) => [
      source.sourceSlug || sourceId,
      source.sourceId || sourceId,
    ])
  );
}

function sourceSlugForEntry([id, source]) {
  return source?.sourceSlug || id;
}

export function getSourceCombinationKey(sourceEntries) {
  const slugs = (sourceEntries || []).map(sourceSlugForEntry).filter(Boolean).sort();
  return slugs.length > 1 ? slugs.join('+') : null;
}

function getCombinedDataPath(ecosystemId, combinationKey) {
  return `ip_data/${ecosystemId}/_combined/${combinationKey}/03_analysis`;
}

function scopeDependencyEdge(edge, sourceId, sourceSlug = sourceId, sourceIdBySlug = {}) {
  if (!edge || edge.source == null || edge.target == null) {
    return edge;
  }

  const parsedSourceKey = parseProposalGraphKey(edge.sourceKey ?? edge.source);
  const parsedTargetKey = parseProposalGraphKey(edge.targetKey ?? edge.target);
  const sourceProposalId = String(edge.sourceProposalId ?? parsedSourceKey.proposalId);
  const targetProposalId = String(edge.targetProposalId ?? parsedTargetKey.proposalId);
  const sourceGraphSource = String(edge.sourceGraphSource ?? parsedSourceKey.graphSource ?? sourceSlug ?? sourceId ?? '');
  const targetGraphSource = String(edge.targetGraphSource ?? parsedTargetKey.graphSource ?? sourceSlug ?? sourceId ?? '');
  const sourceSourceId = String(edge.sourceSourceId ?? sourceIdBySlug[sourceGraphSource] ?? sourceId ?? '');
  const targetSourceId = String(edge.targetSourceId ?? sourceIdBySlug[targetGraphSource] ?? sourceId ?? '');

  return {
    ...edge,
    source: sourceProposalId,
    target: targetProposalId,
    sourceProposalId,
    targetProposalId,
    sourceSourceId,
    targetSourceId,
    sourceGraphSource,
    targetGraphSource,
    sourceKey: edge.sourceKey || buildProposalGraphId(sourceGraphSource, sourceProposalId),
    targetKey: edge.targetKey || buildProposalGraphId(targetGraphSource, targetProposalId),
  };
}

export function scopeDependencyLinksForSource(linksByType, sourceId, sourceSlug = sourceId, sourceIdBySlug = {}) {
  const links = normalizeDependencyLinks(linksByType || EMPTY_LINKS);
  const explicit = links[PREAMBLE_EXTRACTED] || {};

  return {
    [BODY_EXTRACTED_REGEX]: (links[BODY_EXTRACTED_REGEX] || []).map((edge) => scopeDependencyEdge(edge, sourceId, sourceSlug, sourceIdBySlug)),
    [BODY_EXTRACTED_LLM]: (links[BODY_EXTRACTED_LLM] || []).map((edge) => scopeDependencyEdge(edge, sourceId, sourceSlug, sourceIdBySlug)),
    [PREAMBLE_EXTRACTED]: Object.fromEntries(
      Object.entries(explicit).map(([relationType, edges]) => [
        relationType,
        (edges || []).map((edge) => scopeDependencyEdge(edge, sourceId, sourceSlug, sourceIdBySlug)),
      ])
    ),
  };
}

function countAllLinks(linksByType) {
  const links = linksByType || {};
  const explicit = links[PREAMBLE_EXTRACTED] || {};
  return (
    (links[BODY_EXTRACTED_REGEX]?.length || 0)
    + (links[BODY_EXTRACTED_LLM]?.length || 0)
    + Object.values(explicit).reduce((sum, entries) => sum + (entries?.length || 0), 0)
  );
}

function ensureSingleSourceShape(snapshotLabel, sourceId, sourceSlug, snapshotData, ecosystem = null) {
  const network = snapshotData.network || { nodes: [], links: EMPTY_LINKS };
  const graphSource = sourceSlug || sourceId;
  const sourceIdBySlug = buildSourceIdBySlug(ecosystem);
  const rawLinks = { dependency_edges: network.dependency_edges || [] };
  const links = scopeDependencyLinksForSource(rawLinks, sourceId, graphSource, sourceIdBySlug);
  const nodes = (network.nodes || []).map((node) => ({
    ...node,
    source: sourceId,
    graphSource,
    graphId: buildProposalGraphId(graphSource, node?.id),
  }));

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

function ensureCombinedSourceShape(snapshotLabel, sourceEntries, combinationKey, snapshotData, ecosystem = null) {
  const sourceIds = sourceEntries.map(([id]) => id);
  const network = snapshotData.network || { nodes: [], dependency_edges: [] };
  const sourceIdBySlug = buildSourceIdBySlug(ecosystem);
  const rawLinks = { dependency_edges: network.dependency_edges || [] };
  const links = scopeDependencyLinksForSource(rawLinks, '', '', sourceIdBySlug);
  const nodes = (network.nodes || []).map((node) => {
    const parsedGraphKey = parseProposalGraphKey(node?.graph_key ?? node?.graphId ?? node?.graph_id);
    const graphSource = String(
      node?.graphSource
      || node?.source_slug
      || node?.sourceSlug
      || parsedGraphKey.graphSource
      || ''
    );
    const sourceId = sourceIdBySlug[graphSource] || graphSource;
    return {
      ...node,
      source: sourceId,
      graphSource,
      graphId: node?.graphId || node?.graph_key || buildProposalGraphId(graphSource, node?.id),
    };
  });

  return {
    snapshot: snapshotLabel,
    sourceIds,
    combinationKey,
    isMergedSelection: true,
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
      is_merged_selection: true,
      combination_key: combinationKey,
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
    [PREAMBLE_EXTRACTED]: {},
  };
  perSourceDatasets.forEach((d) => {
    const links = d.links || {};
    merged[BODY_EXTRACTED_REGEX].push(...(links[BODY_EXTRACTED_REGEX] || []));
    merged[BODY_EXTRACTED_LLM].push(...(links[BODY_EXTRACTED_LLM] || []));
    const explicit = links[PREAMBLE_EXTRACTED] || {};
    Object.entries(explicit).forEach(([relationType, entries]) => {
      if (!merged[PREAMBLE_EXTRACTED][relationType]) {
        merged[PREAMBLE_EXTRACTED][relationType] = [];
      }
      merged[PREAMBLE_EXTRACTED][relationType].push(...(entries || []));
    });
  });
  return merged;
}

function buildMergedDataset(snapshotLabel, entries, combinedDataset = null) {
  const perSourceDatasets = entries.map(([, ds]) => ds);
  const bySource = Object.fromEntries(entries);
  const sourceIds = entries.map(([id]) => id);

  if (entries.length === 1) {
    return { ...perSourceDatasets[0], bySource, sourceIds };
  }

  if (combinedDataset) {
    return {
      ...combinedDataset,
      bySource,
      sourceIds,
      isMergedSelection: true,
    };
  }

  const nodes = perSourceDatasets.flatMap((d) => d.nodes || []);
  const links = mergeLinks(perSourceDatasets);

  return {
    snapshot: snapshotLabel,
    sourceIds,
    bySource,
    nodes,
    links,
    network: { nodes, links },
    authorship: mergeAuthorship(perSourceDatasets),
    classification: {
      ...EMPTY_DATASET.classification,
      meta: { merge_status: 'not_mergeable', sourceIds },
    },
    evolution: {
      ...EMPTY_DATASET.evolution,
      meta: { merge_status: 'not_mergeable', sourceIds },
    },
    conformity: {
      ...EMPTY_DATASET.conformity,
      meta: { merge_status: 'not_mergeable', sourceIds },
    },
    dependencyMetrics: EMPTY_DATASET.dependencyMetrics,
    isMergedSelection: true,
    meta: {
      node_count: nodes.length,
      link_count: countAllLinks(links),
      is_merged_selection: true,
      dependency_metrics_status: 'unavailable_without_combined_artifact',
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

function makeCombinedCacheKey(ecosystemId, combinationKey, snapshot) {
  return `${ecosystemId}/_combined/${combinationKey}/${snapshot}`;
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
    ensureSingleSourceShape(snapshot, sourceId, source.sourceSlug || sourceId, {
      network, dependencyMetrics, authorship, classification, evolution, conformity,
    }, ecosystemsById[ecosystemId])
  ).catch((err) => {
    fetchCache.delete(key);
    throw err;
  });

  fetchCache.set(key, promise);
  return promise;
}

function fetchCombinedSourceDataset(ecosystemId, sourceEntries, snapshot) {
  const combinationKey = getSourceCombinationKey(sourceEntries);
  if (!combinationKey) return Promise.resolve(null);
  const key = makeCombinedCacheKey(ecosystemId, combinationKey, snapshot);
  if (fetchCache.has(key)) return fetchCache.get(key);

  const base = `./${getCombinedDataPath(ecosystemId, combinationKey)}/${snapshot}`;
  const promise = Promise.all([
    fetchJson(`${base}/dependencies/network_data.json`),
    fetchJson(`${base}/dependencies/dependency_metrics.json`),
    fetchJson(`${base}/authorship/authorship_payload.json`),
    fetchJson(`${base}/classification/classification_payload.json`),
    fetchJson(`${base}/evolution/evolution_payload.json`),
    fetchJson(`${base}/conformity/conformity_metrics.json`),
  ]).then(([network, dependencyMetrics, authorship, classification, evolution, conformity]) =>
    ensureCombinedSourceShape(snapshot, sourceEntries, combinationKey, {
      network, dependencyMetrics, authorship, classification, evolution, conformity,
    }, ecosystemsById[ecosystemId])
  ).catch((err) => {
    fetchCache.delete(key);
    throw err;
  });

  fetchCache.set(key, promise);
  return promise;
}

function hasCombinedSnapshot(ecosystemId, sourceEntries, snapshot) {
  const combinationKey = getSourceCombinationKey(sourceEntries);
  if (!combinationKey) return false;
  return (snapshotIndex[ecosystemId]?.[combinationKey] || []).includes(snapshot);
}

export function isDatasetCached(ecosystemId, snapshot, sourceIds = null) {
  const { sources } = resolveSourcesForIds(ecosystemId, sourceIds);
  if (sources.length === 0) return false;
  const sourceDatasetsCached = sources.every(([, source]) => (
    fetchCache.has(makeCacheKey(ecosystemId, source.sourceSlug, snapshot))
  ));
  if (!sourceDatasetsCached) return false;
  if (sources.length <= 1 || !hasCombinedSnapshot(ecosystemId, sources, snapshot)) return true;
  return fetchCache.has(makeCombinedCacheKey(ecosystemId, getSourceCombinationKey(sources), snapshot));
}

export function getAvailableSnapshots(ecosystemId, sourceIds = null) {
  const { sources } = resolveSourcesForIds(ecosystemId, sourceIds);
  if (sources.length === 0) return [];
  const combinationKey = getSourceCombinationKey(sources);
  if (combinationKey) {
    const combinedSnapshots = snapshotIndex[ecosystemId]?.[combinationKey] || [];
    if (combinedSnapshots.length > 0) return combinedSnapshots;
  }
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

  const sourceDatasetsPromise = Promise.all(
    sources.map(([id, source]) => fetchSingleSourceDataset(ecosystemId, source, id, snapshot)
      .then((dataset) => [id, dataset])),
  );

  if (sources.length > 1 && hasCombinedSnapshot(ecosystemId, sources, snapshot)) {
    return Promise.all([
      sourceDatasetsPromise,
      fetchCombinedSourceDataset(ecosystemId, sources, snapshot),
    ]).then(([entries, combinedDataset]) => buildMergedDataset(snapshot, entries, combinedDataset));
  }

  return sourceDatasetsPromise.then((entries) => buildMergedDataset(snapshot, entries));
}
