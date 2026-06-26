import * as d3 from 'd3';
import {
  cleanAuthorName,
  collectProposalRefs,
  makeProposalRef,
  proposalRefKey,
} from './proposalRefs';

function buildDisplayAuthorshipMetricsRows(rows, topAuthorSet = new Set()) {
  return (rows || []).map((row) => ({
    ...row,
    displayAuthor: topAuthorSet.has(row.author) ? `${row.author}*` : row.author,
  }));
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
  } = {
    summary: authorship.collaboration_metrics_summary || {},
    metricsRows: buildDisplayAuthorshipMetricsRows(authorship.collaboration_metrics_rows || [], topCollaborationAuthors),
    clusterSizeDistribution: authorship.collaboration_cluster_size_distribution || [],
    degreeDistribution: authorship.collaboration_degree_distribution || [],
  };

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
