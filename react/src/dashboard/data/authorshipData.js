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
  // The payload carries the identity alias map the pipeline applied, so local
  // per-node recomputations (proposal refs, histograms, shared-proposal edges,
  // git-contributor tiles) resolve to the same canonical names as the
  // server-computed metrics.
  const authorAliases = authorship?.meta?.author_aliases || {};
  const canonicalName = (name) => {
    const cleaned = cleanAuthorName(name);
    return authorAliases[cleaned] || cleaned;
  };
  const nodeAuthors = (node) => (Array.isArray(node?.author) ? node.author : [])
    .map(canonicalName)
    .filter(Boolean);
  // node.contributors = every non-bot committer in the proposal file's full
  // git history (mined in the preprocess stage), as raw git author names.
  const nodeContributors = (node) => Array.from(new Set(
    (Array.isArray(node?.contributors) ? node.contributors : [])
      .map(canonicalName)
      .filter(Boolean)
  ));

  const authorBipsByAuthor = new Map();
  const bipsByYear = new Map();

  dataset.nodes.forEach((node) => {
    if (node?.id == null) {
      return;
    }
    const ref = makeProposalRef(node);
    const refKey = proposalRefKey(ref);

    const authors = nodeAuthors(node);

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
    const uniqueAuthors = Array.from(new Set(nodeAuthors(node)));

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
      new Set(nodeAuthors(node)).forEach((author) => {
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
      const n = new Set(nodeAuthors(node)).size;
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

  // Git-contributor tiles: all numbers come precomputed from the payload's
  // `contributors` block (pipeline-side, same artifact the paper consumes);
  // the client only joins proposal refs from node.contributors for tooltips —
  // the same decoration pattern as topAuthors above.
  const contributorsPayload = authorship.contributors || null;
  const {
    topContributors,
    contributorContributionHistogram,
    contributorsPerProposalHistogram,
    contributorCoverage,
  } = (() => {
    if (!contributorsPayload) {
      return {
        topContributors: [],
        contributorContributionHistogram: [],
        contributorsPerProposalHistogram: [],
        contributorCoverage: null,
      };
    }

    const bipsByContributor = new Map();
    const bipsByContributorCount = new Map();
    dataset.nodes.forEach((node) => {
      if (node?.id == null) return;
      const contributors = nodeContributors(node);
      if (contributors.length === 0) return;
      const ref = makeProposalRef(node);
      const refKey = proposalRefKey(ref);
      contributors.forEach((name) => {
        if (!bipsByContributor.has(name)) bipsByContributor.set(name, new Map());
        bipsByContributor.get(name).set(refKey, ref);
      });
      if (!bipsByContributorCount.has(contributors.length)) {
        bipsByContributorCount.set(contributors.length, new Map());
      }
      bipsByContributorCount.get(contributors.length).set(refKey, ref);
    });

    const coverage = contributorsPayload.coverage || {};
    return {
      topContributors: (contributorsPayload.top_contributors || [])
        .slice(0, 10)
        .map((entry) => ({
          ...entry,
          bips: collectProposalRefs(bipsByContributor.get(entry.author)),
        })),
      contributorContributionHistogram: contributorsPayload.contribution_histogram || [],
      contributorsPerProposalHistogram: (contributorsPayload.per_proposal_histogram || [])
        .map((entry) => ({
          authorCount: entry.author_count,
          bipCount: entry.bip_count,
          bips: collectProposalRefs(bipsByContributorCount.get(entry.author_count)),
        })),
      contributorCoverage: {
        contributorCount: coverage.contributor_count ?? 0,
        declaredAuthorCount: coverage.declared_author_count ?? 0,
        contributorsAlsoDeclared: coverage.contributors_also_declared ?? 0,
        contributorsNeverDeclared: coverage.contributors_never_declared ?? 0,
        proposalsWithGitData: coverage.proposals_with_git_data ?? 0,
        proposalsWithUncredited: coverage.proposals_with_uncredited ?? 0,
      },
    };
  })();

  return {
    yearData,
    topAuthors,
    authorContributionHistogram,
    bipAuthorCountHistogram,
    topContributors,
    contributorContributionHistogram,
    contributorsPerProposalHistogram,
    contributorCoverage,
    collaborationNetwork,
    collaborationMetricsSummary,
    collaborationMetricsRows,
    collaborationClusterSizeDistribution,
    collaborationDegreeDistribution,
  };
}
