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
import { BrowserRouter as Router, Routes, Route, useNavigate, useParams, Link } from 'react-router-dom';
import { ecosystems, ecosystemsById } from './ecosystems';
import { getAvailableStichtage, getDatasetForSelection } from './data';

function buildDashboardData(dataset) {
  const proposalsPerYear = d3.rollup(
    dataset.nodes,
    (values) => values.length,
    (node) => new Date(node.created).getFullYear()
  );

  const yearData = Array.from(proposalsPerYear, ([year, count]) => ({ year, count }))
    .sort((a, b) => a.year - b.year);

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

  const sankeyNodes = new Map();
  const sankeyLinks = {};

  function ensureSankeyNode(column, label) {
    const key = `${column}:${label}`;
    if (!sankeyNodes.has(key)) {
      sankeyNodes.set(key, { key, label, column });
    }
    return key;
  }

  dataset.nodes.forEach((proposal) => {
    const layerRaw = proposal.group ?? proposal.raw?.preamble?.layer ?? "Unknown Layer";
    const statusRaw = proposal.status ?? proposal.raw?.preamble?.status ?? "Unknown Status";
    const typeRaw = proposal.type ?? proposal.raw?.preamble?.type ?? "Unknown Type";

    const layer = String(layerRaw).trim() || "Unknown Layer";
    const status = String(statusRaw).trim() || "Unknown Status";
    const type = String(typeRaw).trim() || "Unknown Type";

    if (layer.includes("Unknown") || status.includes("Unknown") || type.includes("Unknown")) {
      return;
    }

    const layerKey = ensureSankeyNode('layer', layer);
    const statusKey = ensureSankeyNode('status', status);
    const typeKey = ensureSankeyNode('type', type);

    const link1 = `${layerKey}--${statusKey}`;
    const link2 = `${statusKey}--${typeKey}`;

    sankeyLinks[link1] = (sankeyLinks[link1] || 0) + 1;
    sankeyLinks[link2] = (sankeyLinks[link2] || 0) + 1;
  });

  const nodeList = Array.from(sankeyNodes.values());
  const nodeIdMap = new Map(nodeList.map((node, index) => [node.key, index]));

  const sankeyData = {
    nodes: nodeList.map((node) => ({
      id: nodeIdMap.get(node.key),
      name: node.label,
      column: node.column
    })),
    links: Object.entries(sankeyLinks).map(([key, value]) => {
      const [sourceLabel, targetLabel] = key.split('--');
      return {
        source: nodeIdMap.get(sourceLabel),
        target: nodeIdMap.get(targetLabel),
        value
      };
    })
  };

  return { yearData, wordCloudData, sankeyData };
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
  const { yearData, wordCloudData, sankeyData } = buildDashboardData(selectedDataset);
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
          <TopAuthorsChart data={selectedDataset} />
        </Card>
        <Card className="mb-4" style={{ flex: 1 }}>
          <h2>Proposals Over Time</h2>
          <p>This timeline chart shows how many proposals entered the selected ecosystem per year.</p>
          <BipTimelineChart data={yearData} width={600} height={400} />
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
