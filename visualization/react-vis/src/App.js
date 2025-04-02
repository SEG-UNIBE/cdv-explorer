import BIPNo from "./BIPNo";
import Navbar from './Navbar'; 
import  data  from './data';
import { NetworkDiagram } from './NetworkDiagram';
import './App.scss';

function App() {
  return (
    <div className="App">
       <Navbar />
       <section className="content">
       <NetworkDiagram data={data} width={400} height={400} />
       </section>
    </div>
  );
}

export default App;
