import BIPNo from "./BIPNo";
import Navbar from './Navbar'; 
import data from './data';
import { NetworkDiagram } from './NetworkDiagram';
import { BipTimelineChart } from './BipTimelineChart';
import { TopAuthorsChart } from './TopAuthorsChart';
import { WordCloud } from './WordCloud';
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
    
  const myWords = [
      { word: "Hello" },
      { word: "Everybody" },
      { word: "How" },
      { word: "Are" },
      { word: "You" },
      { word: "Today" },
      { word: "Lovely" },
      { word: "Day" },
      { word: "Love" },
      { word: "Coding" }
    ];
  
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
      </section>
    </div>
  );
}

export default App;
