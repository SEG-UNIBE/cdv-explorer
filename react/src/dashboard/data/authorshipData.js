import * as d3 from 'd3';
import {
  cleanAuthorName,
  collectProposalRefs,
  makeProposalRef,
  proposalRefKey,
} from './proposalRefs';

function computeWeightedEigenvectorCentrality(nodeIds, adjacency, maxIterations = 1000, tolerance = 1e-6) {
  const authorIds = Array.from(new Set((nodeIds || []).map((id) => String(id))));
  const nodeCount = authorIds.length;

  if (nodeCount === 0) {
    return new Map();
  }

  const values = new Map(authorIds.map((id) => [id, 1 / Math.sqrt(nodeCount)]));

  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    const nextValues = new Map(authorIds.map((id) => [id, 0]));

    authorIds.forEach((id) => {
      const neighbors = adjacency.get(id) || [];
      neighbors.forEach(({ id: neighborId, weight }) => {
        nextValues.set(id, nextValues.get(id) + Number(weight || 0) * (values.get(neighborId) || 0));
      });
    });

    const norm = Math.sqrt(
      Array.from(nextValues.values()).reduce((sum, value) => sum + value ** 2, 0)
    );

    if (norm === 0) {
      return new Map(authorIds.map((id) => [id, 0]));
    }

    let delta = 0;
    authorIds.forEach((id) => {
      const normalizedValue = nextValues.get(id) / norm;
      delta += Math.abs(normalizedValue - (values.get(id) || 0));
      values.set(id, normalizedValue);
    });

    if (delta < nodeCount * tolerance) {
      break;
    }
  }

  return values;
}

function computeWeightedPageRank(nodeIds, adjacency, damping = 0.85, maxIterations = 1000, tolerance = 1e-6) {
  const authorIds = Array.from(new Set((nodeIds || []).map((id) => String(id))));
  const nodeCount = authorIds.length;

  if (nodeCount === 0) {
    return new Map();
  }

  const ranks = new Map(authorIds.map((id) => [id, 1 / nodeCount]));
  const outgoingWeightByAuthor = new Map(
    authorIds.map((id) => [
      id,
      (adjacency.get(id) || []).reduce((sum, neighbor) => sum + Number(neighbor.weight || 0), 0),
    ])
  );

  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    const danglingMass = authorIds.reduce((sum, id) => (
      (outgoingWeightByAuthor.get(id) || 0) === 0 ? sum + (ranks.get(id) || 0) : sum
    ), 0);
    const baseScore = ((1 - damping) + (damping * danglingMass)) / nodeCount;
    const nextRanks = new Map(authorIds.map((id) => [id, baseScore]));

    authorIds.forEach((id) => {
      const neighbors = adjacency.get(id) || [];
      const totalOutgoingWeight = outgoingWeightByAuthor.get(id) || 0;

      if (totalOutgoingWeight === 0) {
        return;
      }

      neighbors.forEach(({ id: neighborId, weight }) => {
        const contribution = damping * (ranks.get(id) || 0) * (Number(weight || 0) / totalOutgoingWeight);
        nextRanks.set(neighborId, (nextRanks.get(neighborId) || 0) + contribution);
      });
    });

    let delta = 0;
    authorIds.forEach((id) => {
      delta += Math.abs((nextRanks.get(id) || 0) - (ranks.get(id) || 0));
      ranks.set(id, nextRanks.get(id) || 0);
    });

    if (delta < tolerance) {
      break;
    }
  }

  return ranks;
}

function buildTrueCollaborationComponents(nodeIds, adjacency) {
  const visited = new Set();
  const components = [];

  nodeIds.forEach((id) => {
    if (visited.has(id)) {
      return;
    }

    const queue = [id];
    let head = 0;
    const members = [];
    visited.add(id);

    while (head < queue.length) {
      const current = queue[head++];
      members.push(current);

      (adjacency.get(current) || []).forEach(({ id: neighborId }) => {
        if (visited.has(neighborId)) {
          return;
        }
        visited.add(neighborId);
        queue.push(neighborId);
      });
    }

    components.push(members);
  });

  components.sort((left, right) => right.length - left.length);

  return components;
}

function buildDisplayCollaborationComponents(nodeIds, adjacency) {
  const isolatedIds = [];
  const components = [];

  buildTrueCollaborationComponents(nodeIds, adjacency).forEach((members) => {
    if (members.length === 1) {
      isolatedIds.push(members[0]);
      return;
    }

    components.push(members);
  });

  if (isolatedIds.length > 0) {
    components.push(isolatedIds.sort((left, right) => left.localeCompare(right)));
  }

  return components;
}

function buildCollaborationDerivedData(collaborationNetwork, collaborationCentrality, topAuthorSet = new Set()) {
  const rawNodes = collaborationNetwork?.nodes || [];
  const rawEdges = collaborationNetwork?.edges || [];
  const nodeIds = rawNodes.map((node) => String(node.id)).filter(Boolean);
  const adjacency = new Map(nodeIds.map((id) => [id, []]));
  const weightedDegreeByAuthor = new Map(nodeIds.map((id) => [id, 0]));

  rawEdges.forEach((edge) => {
    const source = String(edge.source);
    const target = String(edge.target);
    const weight = Number(edge.weight || 1);

    if (!adjacency.has(source)) {
      adjacency.set(source, []);
      weightedDegreeByAuthor.set(source, 0);
    }
    if (!adjacency.has(target)) {
      adjacency.set(target, []);
      weightedDegreeByAuthor.set(target, 0);
    }

    adjacency.get(source).push({ id: target, weight });
    adjacency.get(target).push({ id: source, weight });
    weightedDegreeByAuthor.set(source, (weightedDegreeByAuthor.get(source) || 0) + weight);
    weightedDegreeByAuthor.set(target, (weightedDegreeByAuthor.get(target) || 0) + weight);
  });

  const trueComponents = buildTrueCollaborationComponents(nodeIds, adjacency);
  const components = buildDisplayCollaborationComponents(nodeIds, adjacency);
  const clusterSizeDistribution = Array.from(
    trueComponents.reduce((counts, members) => {
      counts.set(members.length, (counts.get(members.length) || 0) + 1);
      return counts;
    }, new Map())
  )
    .map(([clusterSize, clusterCount]) => ({
      clusterSize: Number(clusterSize),
      clusterCount: Number(clusterCount),
      authorCount: Number(clusterSize) * Number(clusterCount),
    }))
    .sort((left, right) => left.clusterSize - right.clusterSize);

  const clusterMetaByAuthor = new Map();
  components.forEach((members, index) => {
    members.forEach((author) => {
      clusterMetaByAuthor.set(author, {
        clusterId: index + 1,
        clusterSize: members.length,
      });
    });
  });

  const centralityByAuthor = new Map(
    (collaborationCentrality || []).map((entry) => [String(entry.author), entry])
  );
  const weightedEigenvectorByAuthor = computeWeightedEigenvectorCentrality(nodeIds, adjacency);
  const pageRankByAuthor = computeWeightedPageRank(nodeIds, adjacency);

  const degreeRows = rawNodes
    .map((node) => {
      const author = String(node.id);
      const clusterMeta = clusterMetaByAuthor.get(author) || { clusterId: null, clusterSize: 1 };
      const centrality = centralityByAuthor.get(author) || {};

      return {
        author,
        clusterId: clusterMeta.clusterId,
        clusterSize: clusterMeta.clusterSize,
        rawDegree: Number((adjacency.get(author) || []).length),
        weightedDegree: Number(weightedDegreeByAuthor.get(author) || 0),
        betweenness: Number(centrality.betweenness || 0),
        normalizedDegree: Number(centrality.degree || 0),
        pagerank: Number(pageRankByAuthor.get(author) || 0),
      };
    })
    .sort((left, right) => {
      if (right.rawDegree !== left.rawDegree) {
        return right.rawDegree - left.rawDegree;
      }
      return left.author.localeCompare(right.author);
    });

  const eigenvectorRows = nodeIds
    .map((author) => {
      const clusterMeta = clusterMetaByAuthor.get(author) || { clusterId: null, clusterSize: 1 };
      const centrality = centralityByAuthor.get(author) || {};

      return {
        author,
        clusterId: clusterMeta.clusterId,
        clusterSize: clusterMeta.clusterSize,
        eigenvector: Number(centrality.eigenvector || 0),
        weightedEigenvector: Number(weightedEigenvectorByAuthor.get(author) || 0),
      };
    })
    .sort((left, right) => {
      if (right.eigenvector !== left.eigenvector) {
        return right.eigenvector - left.eigenvector;
      }
      return left.author.localeCompare(right.author);
    });

  const eigenvectorByAuthor = new Map(
    eigenvectorRows.map((row) => [row.author, row])
  );
  const metricsRows = degreeRows.map((row) => {
    const eigenvectorRow = eigenvectorByAuthor.get(row.author) || {};

    return {
      ...row,
      displayAuthor: topAuthorSet.has(row.author) ? `${row.author}*` : row.author,
      eigenvector: Number(eigenvectorRow.eigenvector || 0),
      weightedEigenvector: Number(eigenvectorRow.weightedEigenvector || 0),
    };
  });
  const degreeDistribution = Array.from(
    degreeRows.reduce((counts, row) => {
      const degree = Number(row.rawDegree || 0);
      counts.set(degree, (counts.get(degree) || 0) + 1);
      return counts;
    }, new Map())
  )
    .map(([degree, authorCount]) => ({
      degree: Number(degree),
      authorCount: Number(authorCount),
    }))
    .sort((left, right) => left.degree - right.degree);
  const nodeCount = nodeIds.length;
  const edgeCount = rawEdges.length;
  const isolatedAuthorCount = degreeRows.filter((row) => Number(row.rawDegree || 0) === 0).length;
  const clusterCount = components.length;
  const density = nodeCount > 1 ? edgeCount / ((nodeCount * (nodeCount - 1)) / 2) : 0;
  const largestClusterSize = trueComponents[0]?.length || 0;
  const trueClusterCount = trueComponents.length;
  const soloClusterCount = clusterSizeDistribution.find((entry) => entry.clusterSize === 1)?.clusterCount || 0;
  const pairClusterCount = clusterSizeDistribution.find((entry) => entry.clusterSize === 2)?.clusterCount || 0;
  const singleCoauthorCount = degreeDistribution.find((entry) => entry.degree === 1)?.authorCount || 0;
  const lowDegreeAuthorCount = degreeDistribution
    .filter((entry) => entry.degree <= 1)
    .reduce((sum, entry) => sum + entry.authorCount, 0);
  const averageDegree = nodeCount > 0
    ? degreeRows.reduce((sum, row) => sum + Number(row.rawDegree || 0), 0) / nodeCount
    : 0;
  const maxDegree = degreeDistribution[degreeDistribution.length - 1]?.degree || 0;

  return {
    summary: {
      nodeCount,
      edgeCount,
      isolatedAuthorCount,
      clusterCount,
      density,
      trueClusterCount,
      soloClusterCount,
      pairClusterCount,
      largestClusterSize,
      singleCoauthorCount,
      lowDegreeAuthorCount,
      averageDegree,
      maxDegree,
    },
    metricsRows,
    clusterSizeDistribution,
    degreeDistribution,
  };
}

function computeBySource(refs) {
  return (refs || []).reduce((acc, ref) => {
    const key = ref?.source || '';
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

export function buildAuthorshipDashboardData(dataset, authorship = {}) {
  const authorBipsByAuthor = new Map();
  const bipsByYear = new Map();

  dataset.nodes.forEach((node) => {
    if (node?.id == null) {
      return;
    }
    const ref = makeProposalRef(node);
    const refKey = proposalRefKey(ref);

    const authors = Array.isArray(node.author)
      ? node.author.map(cleanAuthorName).filter(Boolean)
      : [];

    authors.forEach((author) => {
      if (!authorBipsByAuthor.has(author)) {
        authorBipsByAuthor.set(author, new Map());
      }
      authorBipsByAuthor.get(author).set(refKey, ref);
    });

    if (node?.created) {
      const year = new Date(node.created).getFullYear();
      if (Number.isFinite(year) && year > 1900) {
        if (!bipsByYear.has(year)) {
          bipsByYear.set(year, new Map());
        }
        bipsByYear.get(year).set(refKey, ref);
      }
    }
  });

  const yearData = ((authorship.bips_per_year || []).length
    ? (authorship.bips_per_year || []).map((entry) => {
      const refs = collectProposalRefs(bipsByYear.get(Number(entry.year)));
      return { ...entry, bips: refs, bySource: computeBySource(refs) };
    })
    : Array.from(
      d3.rollup(
        dataset.nodes.filter((node) => {
          if (!node?.created) {
            return false;
          }
          const year = new Date(node.created).getFullYear();
          return Number.isFinite(year) && year > 1900;
        }),
        (values) => values.length,
        (node) => new Date(node.created).getFullYear()
      ),
      ([year, count]) => {
        const refs = collectProposalRefs(bipsByYear.get(Number(year)));
        return { year, count, bips: refs, bySource: computeBySource(refs) };
      }
    ).sort((a, b) => a.year - b.year));

  const topAuthors = (authorship.top_authors || []).map((entry) => ({
    ...entry,
    bips: collectProposalRefs(authorBipsByAuthor.get(entry.author)),
  }));
  const topCollaborationAuthors = new Set(
    Array.from(authorBipsByAuthor.entries())
      .sort((left, right) => {
        const bipCountDifference = right[1].size - left[1].size;
        if (bipCountDifference !== 0) {
          return bipCountDifference;
        }
        return left[0].localeCompare(right[0]);
      })
      .slice(0, 10)
      .map(([author]) => author)
  );

  const sharedBipsByAuthorPair = new Map();
  dataset.nodes.forEach((node) => {
    const authors = Array.isArray(node.author)
      ? node.author.map(cleanAuthorName).filter(Boolean)
      : [];
    const uniqueAuthors = Array.from(new Set(authors));

    if (!node.id || uniqueAuthors.length < 2) {
      return;
    }
    const ref = makeProposalRef(node);
    const refKey = proposalRefKey(ref);

    for (let i = 0; i < uniqueAuthors.length; i += 1) {
      for (let j = i + 1; j < uniqueAuthors.length; j += 1) {
        const pairKey = [uniqueAuthors[i], uniqueAuthors[j]].sort().join('|||');
        if (!sharedBipsByAuthorPair.has(pairKey)) {
          sharedBipsByAuthorPair.set(pairKey, new Map());
        }
        sharedBipsByAuthorPair.get(pairKey).set(refKey, ref);
      }
    }
  });

  const rawCollaborationNetwork = authorship.collaboration_network || { nodes: [], edges: [] };
  const rawCollaborationNodeIds = new Set(
    (rawCollaborationNetwork.nodes || []).map((node) => String(node.id)).filter(Boolean)
  );
  const collaborationNetwork = {
    ...rawCollaborationNetwork,
    nodes: [
      ...(rawCollaborationNetwork.nodes || []).map((node) => ({
        ...node,
        bips: collectProposalRefs(authorBipsByAuthor.get(node.id)),
      })),
      ...Array.from(authorBipsByAuthor.entries())
        .filter(([author]) => !rawCollaborationNodeIds.has(author))
        .map(([author, bipMap]) => ({
          id: author,
          degree: 0,
          bips: collectProposalRefs(bipMap),
        })),
    ],
    edges: (rawCollaborationNetwork.edges || []).map((edge) => {
      const pairKey = [edge.source, edge.target].sort().join('|||');
      const bips = collectProposalRefs(sharedBipsByAuthorPair.get(pairKey));

      return {
        ...edge,
        bips,
      };
    }),
  };

  const {
    summary: collaborationMetricsSummary,
    metricsRows: collaborationMetricsRows,
    clusterSizeDistribution: collaborationClusterSizeDistribution,
    degreeDistribution: collaborationDegreeDistribution,
  } = buildCollaborationDerivedData(
    collaborationNetwork,
    authorship.collaboration_centrality || [],
    topCollaborationAuthors,
  );

  const authorContributionHistogram = (() => {
    const proposalsPerAuthor = new Map();
    dataset.nodes.forEach((node) => {
      const authors = Array.isArray(node.author)
        ? node.author.map(cleanAuthorName).filter(Boolean)
        : [];
      new Set(authors).forEach((author) => {
        proposalsPerAuthor.set(author, (proposalsPerAuthor.get(author) || 0) + 1);
      });
    });
    const histogram = new Map();
    proposalsPerAuthor.forEach((count) => {
      histogram.set(count, (histogram.get(count) || 0) + 1);
    });
    return Array.from(histogram.entries())
      .map(([bipsWritten, authors]) => ({ bips_written: bipsWritten, authors }))
      .sort((a, b) => a.bips_written - b.bips_written);
  })();

  const bipAuthorCountHistogram = (() => {
    const bipsByAuthorCount = new Map();
    dataset.nodes.forEach((node) => {
      if (node?.id == null) return;
      const authors = Array.isArray(node.author)
        ? node.author.map(cleanAuthorName).filter(Boolean)
        : [];
      const n = authors.length;
      if (!bipsByAuthorCount.has(n)) bipsByAuthorCount.set(n, new Map());
      const ref = makeProposalRef(node);
      bipsByAuthorCount.get(n).set(proposalRefKey(ref), ref);
    });
    return Array.from(bipsByAuthorCount.entries())
      .map(([authorCount, refMap]) => {
        const bips = collectProposalRefs(refMap);
        return { authorCount, bipCount: bips.length, bips };
      })
      .sort((a, b) => a.authorCount - b.authorCount);
  })();

  return {
    yearData,
    topAuthors,
    authorContributionHistogram,
    bipAuthorCountHistogram,
    collaborationNetwork,
    collaborationMetricsSummary,
    collaborationMetricsRows,
    collaborationClusterSizeDistribution,
    collaborationDegreeDistribution,
  };
}
