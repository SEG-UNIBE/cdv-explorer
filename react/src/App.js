import { useEffect, useMemo, useState } from 'react';
import Navbar from './Navbar';
import { NetworkDiagram } from './NetworkDiagram';
import { ProposalTimelineChart } from './ProposalTimelineChart';
import { TopAuthorsChart } from './TopAuthorsChart';
import { AuthorContributionHistogram } from './AuthorContributionHistogram';
import { AuthorCollaborationNetwork } from './AuthorCollaborationNetwork';
import { AuthorCentralityTable } from './AuthorCentralityTable';
import { WordCloud } from './WordCloud';
import { ProposalSankeyChart } from './ProposalSankeyChart';
import { Card } from 'primereact/card';
import { Button } from 'primereact/button';
import { Tag } from 'primereact/tag';
import { Dropdown } from 'primereact/dropdown';
import { InputText } from 'primereact/inputtext';
import { RadioButton } from 'primereact/radiobutton';
import './App.scss';
import * as d3 from 'd3';
import { ProposalKpiOverview } from './ProposalKpiOverview';
import { HashRouter as Router, Routes, Route, useNavigate, useParams, Link } from 'react-router-dom';
import { ecosystems, ecosystemsById } from './ecosystems';
import { getAvailableStichtage, getDatasetForSelection } from './data';

const COLLABORATION_LAYOUT_OPTIONS = [
  { label: 'Balanced', value: 'balanced' },
  { label: 'Clustered', value: 'clustered' },
  { label: 'Spread', value: 'spread' },
];

function cleanAuthorName(author) {
  return String(author || '').split('<')[0].trim();
}

function countDisplayedEdges(links) {
  const byType = links || {};
  return (
    (byType.explicit_references?.length || 0)
    + (byType.requires?.length || 0)
    + (byType.replaces?.length || 0)
    + (byType.superseded_by?.length || 0)
    + (byType.implicit_dependencies?.length || 0)
  );
}

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

function buildCollaborationDerivedData(collaborationNetwork, collaborationCentrality) {
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

  const visited = new Set();
  const components = [];
  nodeIds.forEach((id) => {
    if (visited.has(id)) {
      return;
    }

    const queue = [id];
    const members = [];
    visited.add(id);

    while (queue.length > 0) {
      const current = queue.shift();
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

  const degreeRows = rawNodes
    .map((node) => {
      const author = String(node.id);
      const clusterMeta = clusterMetaByAuthor.get(author) || { clusterId: null, clusterSize: 1 };
      const centrality = centralityByAuthor.get(author) || {};

      return {
        author,
        clusterId: clusterMeta.clusterId,
        clusterSize: clusterMeta.clusterSize,
        rawDegree: Number(node.degree || 0),
        weightedDegree: Number(weightedDegreeByAuthor.get(author) || 0),
        normalizedDegree: Number(centrality.degree || 0),
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
      eigenvector: Number(eigenvectorRow.eigenvector || 0),
      weightedEigenvector: Number(eigenvectorRow.weightedEigenvector || 0),
    };
  });

  return {
    degreeRows,
    eigenvectorRows,
    metricsRows,
  };
}

function buildDashboardData(dataset) {
  const authorship = dataset.authorship || {};
  const classification = dataset.classification || {};
  const conformity = dataset.conformity || {};
  const authorBipsByAuthor = new Map();
  const bipsByYear = new Map();

  dataset.nodes.forEach((node) => {
    const bipId = node?.id != null ? String(node.id) : null;
    if (!bipId) {
      return;
    }

    const authors = Array.isArray(node.author)
      ? node.author.map(cleanAuthorName).filter(Boolean)
      : [];

    authors.forEach((author) => {
      if (!authorBipsByAuthor.has(author)) {
        authorBipsByAuthor.set(author, new Set());
      }
      authorBipsByAuthor.get(author).add(bipId);
    });

    if (node?.created) {
      const year = new Date(node.created).getFullYear();
      if (Number.isFinite(year) && year > 1900) {
        if (!bipsByYear.has(year)) {
          bipsByYear.set(year, new Set());
        }
        bipsByYear.get(year).add(bipId);
      }
    }
  });

  const yearData = (authorship.bips_per_year || []).length
    ? (authorship.bips_per_year || []).map((entry) => ({
        ...entry,
        bips: Array.from(bipsByYear.get(Number(entry.year)) || []).sort((left, right) => Number(left) - Number(right)),
      }))
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
        ([year, count]) => ({
          year,
          count,
          bips: Array.from(bipsByYear.get(Number(year)) || []).sort((left, right) => Number(left) - Number(right)),
        })
      ).sort((a, b) => a.year - b.year);

  const wordCounts = {};
  for (const node of dataset.nodes) {
    const wordList = node.word_list;
    if (!wordList) continue;

    for (const word in wordList) {
      if (Object.prototype.hasOwnProperty.call(wordList, word)) {
        wordCounts[word] = (wordCounts[word] || 0) + wordList[word];
      }
    }
  }

  const customStopwords = new Set([
    'code', 'tt', '0', '1', '2', '3', '4', '32', 'x',
    'key', 'not', 'if', 'can', 'pre', 'must', 'which', 's',
    'https', 'com', 'should', 'may', 'have', 'new', 'any', 'no',
    'using', 'use', 'only', 'used', 'all', 'we', 'they', 'when',
    'each', 'time', 'i', 'but', 'would', 'than', 'same', 'm',
    'their', 'more', 'also', 'such', 'there', 'then', 'these',
    'bit', 'bytes', 'byte', 'message', 'comments', 'data', 'value',
    'type', 'size', 'set', 'path', 'ref', 'org', 'p', 'n',
    'github', 'mediawiki', 'sub', 'script', 'public', 'one', 'number', 'keys', 'other', 'first',
    'following', 'implementation', 'string', 'case', 'node', 'private',
    'master', 'does', 'specification', 'two', 'change',
    'valid', 'where', 'after', 'return', 'e', 'g', 'without', 'standard',
    'user', 'order', 't', 'index', 'b', 'example', 'nodes', 'non', 'style',
    'format', 'bits', 'so', 'license', 'some', 'field', 'length',
    'messages', 'defined', 'being', 'uri', 'created', 'k', 'required',
    'possible', 'both', 'see', 'let', 'however', 'list', 'wiki', 'into', 'based',
    'them', 'blob', 'stack', 'sup', 'been', 'name', 'c', 'do', 'r', '5', '8', 'up', 'make', 'since', 'given', 'per', 'while'
  ]);

  const wordCloudData = Object.entries(wordCounts)
    .filter(([word]) => !customStopwords.has(word.toLowerCase()))
    .map(([word, count]) => ({ word, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 100);

  const groupedLinks = classification?.sankey_grouped?.links || [];
  const nodeLabels = Array.from(new Set(groupedLinks.flatMap((item) => [item.source, item.target])));
  const nodeIdMap = new Map(nodeLabels.map((label, index) => [label, index]));

  const sankeyData = {
    nodes: nodeLabels.map((label, index) => ({
      id: index,
      name: label,
      column: 'grouped',
    })),
    links: groupedLinks.map((link) => ({
      source: nodeIdMap.get(link.source),
      target: nodeIdMap.get(link.target),
      value: link.count,
    })),
  };

  const statusByLayerRows = Object.entries(classification.status_distribution_by_layer || {}).map(
    ([layer, statuses]) => ({
      layer,
      total: Object.values(statuses).reduce((sum, count) => sum + Number(count || 0), 0),
      topStatus: Object.entries(statuses).sort((a, b) => b[1] - a[1])[0]?.[0] || 'n/a',
    })
  );

  const conformityStatusRows = Object.entries(conformity.average_score_by_status || {}).map(
    ([status, score]) => ({ status, score })
  );

  const topAuthors = (authorship.top_authors || []).map((entry) => ({
    ...entry,
    bips: Array.from(authorBipsByAuthor.get(entry.author) || []).sort((left, right) => Number(left) - Number(right)),
  }));
  const authorContributionHistogram = authorship.author_contribution_histogram || [];
  const sharedBipsByAuthorPair = new Map();
  dataset.nodes.forEach((node) => {
    const authors = Array.isArray(node.author)
      ? node.author.map(cleanAuthorName).filter(Boolean)
      : [];
    const uniqueAuthors = Array.from(new Set(authors));

    if (!node.id || uniqueAuthors.length < 2) {
      return;
    }

    for (let i = 0; i < uniqueAuthors.length; i += 1) {
      for (let j = i + 1; j < uniqueAuthors.length; j += 1) {
        const pairKey = [uniqueAuthors[i], uniqueAuthors[j]].sort().join('|||');
        if (!sharedBipsByAuthorPair.has(pairKey)) {
          sharedBipsByAuthorPair.set(pairKey, new Set());
        }
        sharedBipsByAuthorPair.get(pairKey).add(String(node.id));
      }
    }
  });

  const rawCollaborationNetwork = authorship.collaboration_network || { nodes: [], edges: [] };
  const collaborationNetwork = {
    ...rawCollaborationNetwork,
    edges: (rawCollaborationNetwork.edges || []).map((edge) => {
      const pairKey = [edge.source, edge.target].sort().join('|||');
      const bips = Array.from(sharedBipsByAuthorPair.get(pairKey) || [])
        .sort((left, right) => Number(left) - Number(right));

      return {
        ...edge,
        bips,
      };
    }),
  };
  const collaborationCentrality = authorship.collaboration_centrality || [];
  const {
    metricsRows: collaborationMetricsRows,
  } = buildCollaborationDerivedData(collaborationNetwork, collaborationCentrality);
  const top10Share = authorship.top_10_share || {};

  return {
    yearData,
    wordCloudData,
    sankeyData,
    statusByLayerRows,
    conformityStatusRows,
    topAuthors,
    authorContributionHistogram,
    collaborationNetwork,
    collaborationCentrality,
    collaborationMetricsRows,
    top10Share,
    overallConformity: conformity.overall_average_score,
  };
}

function EcosystemLanding() {
  const navigate = useNavigate();

  return (
    <section className="content">
      <h1>Proposal Ecosystem Explorer</h1>
      <p>
        This repository is being reoriented around a reusable proposal-analysis pipeline. Start by choosing
        the ecosystem you want to inspect. Bitcoin is the first implemented adapter; additional ecosystems
        will plug into the same analysis and visualization flow over time.
      </p>

      <div className="ecosystem-grid">
        {ecosystems.map((ecosystem) => {
          const available = ecosystem.status === 'available';

          return (
            <Card
              key={ecosystem.id}
              className={`ecosystem-card${available ? '' : ' ecosystem-card--muted'}`}
            >
              <div>
                <div className="ecosystem-card-header">
                  <img className="ecosystem-logo" src={ecosystem.logo} alt={`${ecosystem.name} logo`} />
                  <h2>{ecosystem.name}</h2>
                </div>
                <p>{ecosystem.description}</p>
                <div className="ecosystem-meta">
                  <Tag
                    severity={available ? 'success' : 'secondary'}
                    value={available ? 'Available now' : 'Coming soon'}
                  />
                  <span>{ecosystem.proposalShortPlural}</span>
                </div>
              </div>
              <div className="ecosystem-actions">
                <Button
                  label={available ? `Open ${ecosystem.name}` : 'Not yet available'}
                  disabled={!available}
                  onClick={() => navigate(`/ecosystem/${ecosystem.id}`)}
                />
              </div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

function EcosystemDashboard() {
  const { ecosystemId } = useParams();
  const ecosystem = ecosystemsById[ecosystemId];
  const availableStichtage = useMemo(() => getAvailableStichtage(ecosystemId), [ecosystemId]);
  const [selectedStichtag, setSelectedStichtag] = useState(availableStichtage[0] ?? null);
  const [highlightedAuthor, setHighlightedAuthor] = useState('');
  const [collaborationLayoutMode, setCollaborationLayoutMode] = useState('balanced');

  useEffect(() => {
    setSelectedStichtag((current) => {
      if (current && availableStichtage.includes(current)) {
        return current;
      }
      return availableStichtage[0] ?? null;
    });
  }, [ecosystemId, availableStichtage]);

  if (!ecosystem) {
    return (
      <section className="content">
        <h1>Unknown Ecosystem</h1>
        <p>The selected ecosystem does not exist in this frontend configuration.</p>
        <p><Link to="/">Back to ecosystem selection</Link></p>
      </section>
    );
  }

  if (ecosystem.status !== 'available') {
    return (
      <section className="content">
        <h1>{ecosystem.name}</h1>
        <p>This ecosystem is listed intentionally, but its adapter has not been implemented yet.</p>
        <p><Link to="/">Back to ecosystem selection</Link></p>
      </section>
    );
  }

  const selectedDataset = getDatasetForSelection(ecosystemId, selectedStichtag);
  const {
    yearData,
    wordCloudData,
    sankeyData,
    statusByLayerRows,
    conformityStatusRows,
    topAuthors,
    authorContributionHistogram,
    collaborationNetwork,
    collaborationMetricsRows,
    top10Share,
    overallConformity,
  } = buildDashboardData(selectedDataset);
  const collaborationAuthorOptions = collaborationNetwork.nodes
    .map((node) => String(node.id || ''))
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right));
  const stichtagOptions = availableStichtage.map((stichtag) => ({
    label: stichtag === 'current' ? 'Current' : stichtag,
    value: stichtag,
  }));

  return (
    <section className="content">
      <div className="dashboard-toolbar">
        <div className="dashboard-toolbar__copy">
          <div className="dashboard-title-row">
            <img className="dashboard-title-logo" src={ecosystem.logo} alt={`${ecosystem.name} logo`} />
            <h1>{ecosystem.proposalPlural}</h1>
          </div>
          <p>
            {ecosystem.proposalPlural} are the first reference dataset in this repository. The broader aim is a reusable
            proposal-mining and visualization stack that can be adapted to multiple governance or standards ecosystems.
            For now, this dashboard lets you inspect the Bitcoin implementation across network structure, category flows,
            authorship, temporal activity, and text-derived themes.
          </p>
        </div>
      </div>
      <div className="dashboard-sticky-controls">
        <label htmlFor="stichtag-select" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>
          STICHTAG
        </label>
        <Dropdown
          inputId="stichtag-select"
          value={selectedStichtag}
          options={stichtagOptions}
          onChange={(event) => setSelectedStichtag(event.value)}
          placeholder="Select snapshot date"
          className="w-full"
        />
      </div>
      <Card className="mb-4">
        <h2>{ecosystem.acronym} Relationship Network</h2>
        <p>
          This graph visualizes three relationship-extraction approaches in the selected ecosystem:
          explicit dependencies (preamble), explicit references (regex), and implicit dependencies (LLM).
        </p>
        <NetworkDiagram data={selectedDataset} width={700} height={500} />
      </Card>
      <Card className="mb-4">
        <h2>Analysis Submodule Summary</h2>
        <div className="analysis-grid">
          <div className="analysis-stat">
            <h3>Relationship Network</h3>
            <p><strong>Nodes:</strong> {selectedDataset.meta?.node_count ?? selectedDataset.nodes.length}</p>
            <p>
              <strong>Edges:</strong> {countDisplayedEdges(selectedDataset.links)}
            </p>
          </div>
          <div className="analysis-stat">
            <h3>Authorship</h3>
            <p><strong>Top authors tracked:</strong> {topAuthors.length}</p>
            <p><strong>Top 10 share:</strong> {top10Share.percentage ?? 'n/a'}%</p>
          </div>
          <div className="analysis-stat">
            <h3>Classification</h3>
            <p><strong>Layer groups:</strong> {statusByLayerRows.length}</p>
            <p><strong>Sankey links:</strong> {sankeyData.links.length}</p>
          </div>
          <div className="analysis-stat">
            <h3>Conformity</h3>
            <p><strong>Average score:</strong> {overallConformity ?? 'n/a'}</p>
            <p><strong>Status buckets:</strong> {conformityStatusRows.length}</p>
          </div>
        </div>
      </Card>
      <section className="dashboard-section">
        <div className="dashboard-section__header">
          <h1>Authorship Patterns</h1>
          <p>
            These charts summarize who writes {ecosystem.proposalShortPlural}, how concentrated authorship is,
            when new {ecosystem.proposalShortPlural} appear, and which authors are most central in the observed
            collaboration graph.
          </p>
        </div>
        <div className="dashboard-grid dashboard-grid--two-up">
          <Card className="mb-4" style={{ flex: 1 }}>
            <h2>Top 10 Authors by {ecosystem.acronym} Count</h2>
            <p>
              Preamble authorship counts for the most prolific contributors in the selected snapshot.
            </p>
            <TopAuthorsChart data={{ topAuthors }} width={640} height={420} />
          </Card>
          <Card className="mb-4" style={{ flex: 1 }}>
            <h2>Authorship Tail Distribution</h2>
            <p>
              Number of authors who have written a given number of {ecosystem.proposalShortPlural}.
            </p>
            <AuthorContributionHistogram data={authorContributionHistogram} width={640} height={420} />
          </Card>
        </div>
        <Card className="mb-4">
          <h2>{ecosystem.proposalPlural} Over Time</h2>
          <p>
            Annual counts are shown as bars; the line tracks the cumulative total on a secondary axis.
          </p>
          <ProposalTimelineChart data={yearData} width={1200} height={420} />
        </Card>
        <Card className="mb-4">
          <h2>Author Collaboration Network</h2>
          <p>
            The existing collaboration graph derived from co-authorship within the selected snapshot.
          </p>
          <div className="network-finder">
            <div className="network-finder__copy">
              <strong>Find author.</strong>
              <span>Search an author to highlight and center their node in the network.</span>
            </div>
            <div className="network-finder__controls">
              <InputText
                value={highlightedAuthor}
                onChange={(event) => setHighlightedAuthor(event.target.value)}
                placeholder="Type an author name"
                list="author-collaboration-options"
              />
              <datalist id="author-collaboration-options">
                {collaborationAuthorOptions.map((author) => (
                  <option key={author} value={author} />
                ))}
              </datalist>
              <Button
                type="button"
                label="Clear"
                severity="secondary"
                text
                onClick={() => setHighlightedAuthor('')}
                disabled={!highlightedAuthor.trim()}
              />
            </div>
          </div>
          <div className="network-layout-picker">
            <div className="network-layout-picker__label">Layout</div>
            <div className="network-layout-picker__options">
              {COLLABORATION_LAYOUT_OPTIONS.map((option) => (
                <label key={option.value} className="network-layout-picker__option">
                  <RadioButton
                    inputId={`collaboration-layout-${option.value}`}
                    name="collaboration-layout"
                    value={option.value}
                    onChange={(event) => setCollaborationLayoutMode(event.value)}
                    checked={collaborationLayoutMode === option.value}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
          </div>
          <AuthorCollaborationNetwork
            data={collaborationNetwork}
            width={1200}
            height={700}
            highlightAuthor={highlightedAuthor}
            layoutMode={collaborationLayoutMode}
          />
        </Card>
        <Card className="mb-4">
          <AuthorCentralityTable
            title="Author Collaboration Metrics"
            description="All authors, sortable and filterable. Cluster IDs refer to connected components, not overlapping maximal cliques."
            rows={collaborationMetricsRows}
            defaultSortField="eigenvector"
            columns={[
              { field: 'clusterId', header: 'Cluster', format: 'integer' },
              { field: 'clusterSize', header: 'Cluster Size', format: 'integer' },
              { field: 'rawDegree', header: 'Degree', format: 'integer' },
              { field: 'weightedDegree', header: 'Weighted Degree', format: 'integer' },
              { field: 'normalizedDegree', header: 'Normalized Degree', digits: 4 },
              { field: 'eigenvector', header: 'Eigenvector Centrality', digits: 6 },
              { field: 'weightedEigenvector', header: 'Weighted Eigenvector', digits: 6 },
            ]}
          />
        </Card>
      </section>
      <h1>Proposal Category Overview</h1>
      <ProposalKpiOverview data={selectedDataset} totalLabel={`Total ${ecosystem.proposalShortPlural}`} />
      <Card className="mb-4" style={{ flex: 1 }}>
        <h2>Sankey Diagram</h2>
        <p>This Sankey diagram visualizes the flow between categories in the selected proposal ecosystem.</p>
        <ProposalSankeyChart data={sankeyData} width={1200} height={600} />
      </Card>
      <br></br>
      <Card className="mb-4">
        <h2>Word Cloud of Proposal Text</h2>
        <p>This word cloud highlights the most frequent terms across the selected proposal corpus.</p>
        <WordCloud words={wordCloudData} width={1250} height={650} />
      </Card>
      <br></br>
      <div className="chart-grid" style={{ display: 'flex', gap: '2rem', marginTop: '2rem', height: '100%' }}>
        <Card className="mb-4" style={{ flex: 1 }}>
          <h2>Classification by Layer</h2>
          <p>Top status per layer from the classification submodule output.</p>
          <table className="analysis-table">
            <thead>
              <tr>
                <th>Layer</th>
                <th>Top Status</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {statusByLayerRows.map((row) => (
                <tr key={row.layer}>
                  <td>{row.layer}</td>
                  <td>{row.topStatus}</td>
                  <td>{row.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card className="mb-4" style={{ flex: 1 }}>
          <h2>Conformity by Status</h2>
          <p>Average compliance score by proposal status from the conformity submodule output.</p>
          <table className="analysis-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Average Score</th>
              </tr>
            </thead>
            <tbody>
              {conformityStatusRows.map((row) => (
                <tr key={row.status}>
                  <td>{row.status}</td>
                  <td>{row.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </section>
  );
}

function AboutPage() {
  return (
    <section className="content" style={{ padding: '2rem' }}>
      <h1>About This Project</h1>
      <p>
        This app is evolving from a Bitcoin-focused explorer into a more general proposal-analysis frontend.
        Bitcoin is the first implemented ecosystem, but the repo is now being organized so other ecosystems
        such as Nostr NIPs or Tor proposals can be added behind the same navigation model.
      </p>
    </section>
  );
}

function App() {
  return (
    <Router>
      <div className="App">
        <Navbar />
        <Routes>
          <Route path="/" element={<EcosystemLanding />} />
          <Route path="/ecosystem/:ecosystemId" element={<EcosystemDashboard />} />
          <Route path="/about" element={<AboutPage />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
