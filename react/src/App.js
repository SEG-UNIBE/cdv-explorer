import { useEffect, useState } from 'react';
import Navbar from './Navbar';
import { NetworkDiagram } from './NetworkDiagram';
import { BipTimelineChart } from './BipTimelineChart';
import { TopAuthorsChart } from './TopAuthorsChart';
import { WordCloud } from './WordCloud';
import { BipSankeyChart } from './BipSankeyChart';
import { Card } from 'primereact/card';
import { Button } from 'primereact/button';
import { Tag } from 'primereact/tag';
import { Dropdown } from 'primereact/dropdown';
import './App.scss';
import * as d3 from 'd3';
import { BipKpiOverview } from "./BipKpiOverview";
import { HashRouter as Router, Routes, Route, useNavigate, useParams, Link } from 'react-router-dom';
import { ecosystems, ecosystemsById } from './ecosystems';
import { getAvailableStichtage, getDatasetForSelection } from './data';

function buildDashboardData(dataset) {
  const authorship = dataset.authorship || {};
  const classification = dataset.classification || {};
  const conformity = dataset.conformity || {};

  const yearData = (authorship.bips_per_year || []).length
    ? (authorship.bips_per_year || [])
    : Array.from(
        d3.rollup(
          dataset.nodes,
          (values) => values.length,
          (node) => new Date(node.created).getFullYear()
        ),
        ([year, count]) => ({ year, count })
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

  const topAuthors = authorship.top_authors || [];
  const top10Share = authorship.top_10_share || {};

  return {
    yearData,
    wordCloudData,
    sankeyData,
    statusByLayerRows,
    conformityStatusRows,
    topAuthors,
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
  const availableStichtage = getAvailableStichtage(ecosystemId);
  const [selectedStichtag, setSelectedStichtag] = useState(availableStichtage[0] ?? null);

  useEffect(() => {
    setSelectedStichtag(availableStichtage[0] ?? null);
  }, [ecosystemId]);

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
    top10Share,
    overallConformity,
  } = buildDashboardData(selectedDataset);
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
        <div className="dashboard-toolbar__controls">
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
      </div>
      <Card className="mb-4">
        <h2>{ecosystem.acronym} Dependency Network</h2>
        <p>This graph visualizes dependencies and relationships between proposals in the selected ecosystem.</p>
        <NetworkDiagram data={selectedDataset} width={700} height={500} />
      </Card>
      <Card className="mb-4">
        <h2>Analysis Submodule Summary</h2>
        <div className="analysis-grid">
          <div className="analysis-stat">
            <h3>Dependencies</h3>
            <p><strong>Nodes:</strong> {selectedDataset.meta?.node_count ?? selectedDataset.nodes.length}</p>
            <p>
              <strong>Edges:</strong> {
                Object.values(selectedDataset.links || {}).reduce((sum, items) => sum + (items?.length || 0), 0)
              }
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
      <h1>Proposal Category Overview</h1>
      <BipKpiOverview data={selectedDataset} totalLabel={`Total ${ecosystem.proposalShortPlural}`} />
      <Card className="mb-4" style={{ flex: 1 }}>
        <h2>Sankey Diagram</h2>
        <p>This Sankey diagram visualizes the flow between categories in the selected proposal ecosystem.</p>
        <BipSankeyChart data={sankeyData} width={1200} height={600} />
      </Card>
      <br></br>
      <Card className="mb-4">
        <h2>Word Cloud of Proposal Text</h2>
        <p>This word cloud highlights the most frequent terms across the selected proposal corpus.</p>
        <WordCloud words={wordCloudData} width={1250} height={650} />
      </Card>
      <br></br>
      <div className="chart-grid" style={{ display: 'flex', gap: '2rem', height: '100%' }}>
        <Card className="mb-4" style={{ flex: 1 }}>
          <h2>Top 10 Proposal Authors</h2>
          <p>This chart shows the most prolific contributors in the selected ecosystem, based on proposal authorship counts.</p>
          <TopAuthorsChart data={{ topAuthors }} />
        </Card>
        <Card className="mb-4" style={{ flex: 1 }}>
          <h2>Proposals Over Time</h2>
          <p>This timeline chart shows how many proposals entered the selected ecosystem per year.</p>
          <BipTimelineChart data={yearData} width={600} height={400} />
        </Card>
      </div>
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
        such as Ethereum EIPs or Tor proposals can be added behind the same navigation model.
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
