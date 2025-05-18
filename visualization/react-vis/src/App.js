
import Navbar from './Navbar';
import data from './data';
import { NetworkDiagram } from './NetworkDiagram';
import { BipTimelineChart } from './BipTimelineChart';
import { TopAuthorsChart } from './TopAuthorsChart';
import { WordCloud } from './WordCloud';
import { BipSankeyChart } from './BipSankeyChart';
import { Card } from 'primereact/card';
import './App.scss';
import * as d3 from 'd3';
import { BipKpiOverview } from "./BipKpiOverview";
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';


function App() {
  const bipsPerYear = d3.rollup(
    data.nodes,
    v => v.length,
    d => new Date(d.created).getFullYear()
  );

  const yearData = Array.from(bipsPerYear, ([year, count]) => ({ year, count }))
    .sort((a, b) => a.year - b.year);

  const wordCounts = {};

  for (const node of data.nodes) {
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
    'them', 'blob', 'stack', 'sup', 'been', 'name', "c", "do", "r", "5", "8", "up", "make", "since", "given", "per", "while"
  ]);


  const wordCloudData = Object.entries(wordCounts)
    .filter(([word]) => !customStopwords.has(word.toLowerCase()))
    .map(([word, count]) => ({ word, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 100);

  const sankeyNodes = new Set();
  const sankeyLinks = {};

  // Step 1: Build sets of unique node names and track link counts
  data.nodes.forEach(bip => {
    const layerRaw = bip.group ?? bip.raw?.preamble?.layer ?? "Unknown Layer";
    const statusRaw = bip.status ?? bip.raw?.preamble?.status ?? "Unknown Status";
    const typeRaw = bip.type ?? bip.raw?.preamble?.type ?? "Unknown Type";

    // Clean strings
    const layer = String(layerRaw).trim() || "Unknown Layer";
    const status = String(statusRaw).trim() || "Unknown Status";
    const type = String(typeRaw).trim() || "Unknown Type";

    // Skip if any are unknown
    if (
      layer.includes("Unknown") ||
      status.includes("Unknown") ||
      type.includes("Unknown")
    ) {
      console.warn("Skipping node due to unknown values:", { layer, status, type, bip });
      return;
    }

    sankeyNodes.add(layer);
    sankeyNodes.add(status);
    sankeyNodes.add(type);

    const link1 = `${layer}--${status}`;
    const link2 = `${status}--${type}`;

    sankeyLinks[link1] = (sankeyLinks[link1] || 0) + 1;
    sankeyLinks[link2] = (sankeyLinks[link2] || 0) + 1;
  });

  // Step 2: Map node names to numeric IDs
  const nodeList = Array.from(sankeyNodes);
  const nodeIdMap = new Map(nodeList.map((label, index) => [label, index]));

  // Step 3: Create nodes and links using numeric IDs
  const sankeyData = {
    nodes: nodeList.map(label => ({
      id: nodeIdMap.get(label), // numeric ID
      name: label               // display name
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

  console.log('Sankey Data:', sankeyData);


  return (
    <Router>
    <div className="App">
      <Navbar />
      <Routes>
          {/* Home Page Route */}
          <Route path="/" element={
      <section className="content">
        <h1>Bitcoin Improvement Protocols and their context</h1>
        <p>Bitcoin Improvement Proposals (BIPs) are key instruments for the ongoing development of the Bitcoin network. The proposals documented here provide a valuable foundation for understanding technical progress and for assessing the potential impact of new features or changes—whether for developers, businesses, miners, or regulatory institutions. The interaction between different BIPs (e.g., in the areas of scalability, security, or privacy) makes it possible to identify complex technical dependencies and to make informed decisions in strategic and technical planning. Of course, BIPs should not be viewed in isolation; their significance and effect only fully emerge in conjunction with existing standards, ongoing developments, and the active participation of the community.
        </p>
        <Card className="mb-4">
          <h2>BIP Dependency Network</h2>
          <p>  This graph visualizes dependencies and relationships between various Bitcoin Improvement Proposals (BIPs). Nodes represent individual BIPs, and links show how proposals build on or reference each other. Use this network to explore how Bitcoin's protocol evolution is interconnected.</p>
          <NetworkDiagram data={data} width={700} height={500} />
        </Card>
        <h1>BIP Layer Overview</h1>
        <BipKpiOverview data={data} />
        <Card className="mb-4" style={{ flex: 1 }}>
          <h2>Sankey Diagram</h2>
          <p>This Sankey diagram visualizes the flow and relationships between key categories and elements within the Bitcoin Improvement Proposals (BIPs). Each link represents the connection and relative volume between sources and targets—such as proposal types, affected components, or authorship trends—providing insight into how ideas and efforts are distributed across the protocol. Use this diagram to trace the progression of contributions and understand the structural dynamics behind Bitcoin’s technical evolution.</p>

            <BipSankeyChart data={sankeyData} width={1200} height={600} />
        </Card>
        <br></br>
        <Card className="mb-4">
          <h2>Word Cloud of BIP Text</h2>
          <p>This word cloud highlights the most frequently occurring terms across the Bitcoin Improvement Proposals (BIPs). Each word’s size corresponds to how often it appears, offering a quick visual summary of key topics and recurring themes. Use this visualization to identify dominant concepts and explore the language shaping Bitcoin's protocol development.</p>
          <WordCloud words={wordCloudData} width={1250} height={650} />
        </Card>
        <br></br>
        <div className="chart-grid" style={{ display: 'flex', gap: '2rem', height: '100%' }}>
          <Card className="mb-4" style={{ flex: 1 }}>
            <h2>Top 10 BIP Authors</h2>
            <p>This bar chart showcases the ten most prolific contributors to the Bitcoin Improvement Proposals (BIPs). Each bar represents an author, with its length corresponding to the number of BIPs they’ve authored or co-authored. The visualization highlights the individuals who have played key roles in shaping Bitcoin’s technical evolution, offering insight into the community’s most active voices over time.</p>
            <TopAuthorsChart data={data} />
          </Card>
          <Card className="mb-4" style={{ flex: 1 }}>
            <h2>BIPs Over Time</h2>
            <p>This timeline chart illustrates the annual number of Bitcoin Improvement Proposals (BIPs) introduced since inception. Each bar represents a year, with its height indicating how many BIPs were proposed in that period. The visualization provides a historical perspective on development activity within the Bitcoin ecosystem, helping identify periods of innovation, debate, and protocol growth over time.</p>
            <BipTimelineChart data={yearData} width={600} height={400} />
          </Card>
        </div>

      </section>
      } />
      {/* About Page Route */}
      <Route path="/about" element={
            <section className="content" style={{ padding: '2rem' }}>
              <h1>About This Project</h1>
              <p>
                This app provides visual analytics for Bitcoin Improvement Proposals (BIPs), helping users understand dependencies,
                authorship, status distribution, and language patterns in the BIP ecosystem.
              </p>
            </section>
          } />
        </Routes>

    </div>
    </Router>
  );
}

export default App;
