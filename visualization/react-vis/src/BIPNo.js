import { useState } from "react";
import { Dropdown } from "primereact/dropdown";
import './BIPNo.scss';

const BIPNos = [
  { name: "Berlin", code: "BER" },
  { name: "Munich", code: "MUN" },
  { name: "Hamburg", code: "HAM" },
  { name: "Cologne", code: "COL" },
];

export default function BIPNo() {
  const [selectedBIPNo, setSelectedBIPNo] = useState(null);

  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-xl font-bold">Demographie Gemeinde</h1>
      <Dropdown
        value={selectedBIPNo}
        options={BIPNos}
        onChange={(e) => setSelectedBIPNo(e.value)}
        optionLabel="name"
        placeholder="Select a BIPNo"
        filter
        filterBy="name"
        className="w-full md:w-40"
      />
    </div>
  );
}
