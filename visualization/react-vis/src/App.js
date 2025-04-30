import BIPNo from "./BIPNo";
import Navbar from './Navbar'; 
import data from './data';
import { NetworkDiagram } from './NetworkDiagram';
import { BipTimelineChart } from './BipTimelineChart';
import { TopAuthorsChart } from './TopAuthorsChart';
import './App.scss';
import * as d3 from 'd3';

function App() {
  data.nodes.forEach(d => {
    console.log(`BIP-${d.id}: created =`, d.created);
  });
  const bipsPerYear = d3.rollup(
    data.nodes,
    v => v.length,
    d => new Date(d.created).getFullYear()
  );

  const yearData = Array.from(bipsPerYear, ([year, count]) => ({ year, count }))
    .sort((a, b) => a.year - b.year);
  
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
      </section>
    </div>
  );
}

export default App;
