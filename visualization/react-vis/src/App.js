import BIPNo from "./BIPNo";
import Navbar from './Navbar'; 
import data from './data';
import { NetworkDiagram } from './NetworkDiagram';
import { BipTimelineChart } from './BipTimelineChart';
import { TopAuthorsChart } from './TopAuthorsChart';
import { WordCloud } from './WordCloud';
import { BipSankeyChart }  from './BipSankeyChart';
import './App.scss';
import * as d3 from 'd3';

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
  
  const wordCloudData = Object.entries(wordCounts)
    .map(([word, count]) => ({ word, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);
    
    const sankeyNodes = new Set();
    const sankeyLinks = {};
    
    data.nodes.forEach(bip => {
      const layerRaw = bip.group ?? bip.raw?.preamble?.layer ?? "Unknown Layer";
      const statusRaw = bip.status ?? bip.raw?.preamble?.status ?? "Unknown Status";
      const typeRaw = bip.raw?.preamble?.type ?? "Unknown Type";
    
      // Clean strings (trim whitespace, fallback if still invalid)
      const layer = String(layerRaw).trim() || "Unknown Layer";
      const status = String(statusRaw).trim() || "Unknown Status";
      const type = String(typeRaw).trim() || "Unknown Type";
    
      // Debug logging
      if (layer === "Unknown Layer" || status === "Unknown Status" || type === "Unknown Type") {
        console.warn("Missing or invalid data:", { layer, status, type, bip });
      }
    
      sankeyNodes.add(layer);
      sankeyNodes.add(status);
      sankeyNodes.add(type);
    
      const link1 = `${layer}--${status}`;
      const link2 = `${status}--${type}`;
    
      sankeyLinks[link1] = (sankeyLinks[link1] || 0) + 1;
      sankeyLinks[link2] = (sankeyLinks[link2] || 0) + 1;
    });
    
    const sankeyData = {
      nodes: Array.from(sankeyNodes).map(id => ({ id })),
      links: Object.entries(sankeyLinks).map(([key, value]) => {
        const [source, target] = key.split('--');
        return { source, target, value };
      })
    };
    console.log(sankeyData)
  
  return (
    <div className="App">
      <Navbar />
      <section className="content">
        <h2>Top 10 BIP Authors</h2>
        <TopAuthorsChart data={data} />

        <h2>BIPs Over Time</h2>
        <BipTimelineChart data={yearData} width={700} height={300} />
        
        <h2 className="mt-8">BIP Dependency Network</h2>
        <NetworkDiagram data={data} width={700} height={500} />

        <h2>Word Cloud of BIP Text</h2>
        <WordCloud words={wordCloudData} width={700} height={400} />

        <h2>Sankey Diagram BIP Layer - Status - Type</h2>
        
      </section>
    </div>
  );
}

export default App;
