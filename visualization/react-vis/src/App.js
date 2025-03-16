import BIPNo from "./BIPNo";
import Navbar from './Navbar'; 
import './App.scss';

function App() {
  return (
    <div className="App">
       <Navbar />
       <section class="content">
       <BIPNo />
       </section>
    </div>
  );
}

export default App;
