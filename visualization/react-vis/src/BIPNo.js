import { useState, useEffect } from "react";
import { Dropdown } from "primereact/dropdown";
import './BIPNo.scss';


const context = require.context('../../../bips_json', false, /\.json$/); // Adjust path as needed

export default function BIPNo() {
  const [selectedBIPNo, setSelectedBIPNo] = useState(null);
  const [options, setOptions] = useState([]);
  const [bipData, setBipData] = useState(null);  // State to store loaded BIP data

  // Load the BIP file names dynamically when the component mounts
  useEffect(() => {
    const fileNames = context.keys().map((fileName) => {
      return {
        name: fileName.replace("./", "").replace(".json", ""),
        code: fileName.replace("./", "").replace(".json", ""),
      };
    });
    setOptions(fileNames);
  }, []);

  const handleSelection = (e) => {
    const selectedBIP = e.value;
    setSelectedBIPNo(selectedBIP);

    // Handle loading the selected JSON file
    import(`../../../bips_json/${selectedBIP.code}.json`)
      .then((module) => {
        setBipData(module);
      })
      .catch((error) => {
        console.error("Error loading BIP data", error);
      });
  };

  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-xl font-bold">Übersicht</h1>
      <Dropdown
        value={selectedBIPNo}
        options={options}
        onChange={handleSelection}
        optionLabel="name"
        placeholder="Select a BIPNo"
        filter
        filterBy="name"
        className="w-full md:w-40"
      />
      {/* Display the selected BIP data if available */}
      {bipData && (
        <div className="bip-content">
          <h2>BIP Data for {selectedBIPNo.name}</h2>
          <pre>{JSON.stringify(bipData, null, 2)}</pre> {/* Display the JSON data */}
        </div>
      )}
    </div>
  );
}
