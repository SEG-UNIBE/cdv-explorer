import * as d3 from 'd3';
import { useEffect, useRef, useState } from 'react';

const data1 = {
  nodes: [{ id: "A" }, { id: "B" }],
  links: [{ source: "A", target: "B" }]
};

const data2 = {
  nodes: [{ id: "X" }, { id: "Y" }, { id: "Z" }],
  links: [{ source: "X", target: "Y" }, { source: "Y", target: "Z" }]
};

export const NetworkDiagram = ({ width, height, data }) => {
  const ref = useRef();
  const [selectedData, setSelectedData] = useState("data1");

  const getCurrentData = () => (selectedData === "data1" ? data1 : data2);

  useEffect(() => {
    const width = 928;
    const height = 600;

    

    const svg = d3.select(ref.current)
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height])
      .style("maxWidth", "100%")
      .style("height", "auto");

    svg.selectAll("*").remove(); // clear previous render

    const color = d3.scaleOrdinal(d3.schemeCategory10);
    const { nodes, links } = getCurrentData();
    //const links = data.links.map(d => ({ ...d }));
    //const nodes = data.nodes.map(d => ({ ...d }));

    // Tooltip div
    const tooltip = d3.select("body")
      .append("div")
      .style("position", "absolute")
      .style("padding", "8px 12px")
      .style("background", "#1a1a1a")
      .style("color", "#f0f0f0")
      .style("border", "1px solid #555")
      .style("border-radius", "6px")
      .style("box-shadow", "0px 2px 6px rgba(0,0,0,0.4)")
      .style("font-size", "13px")
      .style("pointer-events", "none")
      .style("opacity", 0);

    const simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(d => d.id))
      .force("charge", d3.forceManyBody())
      .force("center", d3.forceCenter(width / 2, height / 2))
      .on("tick", ticked);

    const link = svg.append("g")
      .attr("stroke", "#999")
      .attr("stroke-opacity", 0.6)
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke-width", d => Math.sqrt(d.value));

    const node = svg.append("g")
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", 5)
      .attr("fill", d => color(d.group))
      .on("mouseover", (event, d) => {
        tooltip.transition().duration(200).style("opacity", 1);
        tooltip.html(`<strong>BIP-</strong>${d.id}`);
      })
      .on("mousemove", (event) => {
        tooltip
          .style("left", `${event.pageX + 10}px`)
          .style("top", `${event.pageY - 30}px`);
      })
      .on("mouseout", () => {
        tooltip.transition().duration(200).style("opacity", 0);
      })
      .call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    node.append("title").text(d => d.id);

    function ticked() {
      link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

      node
        .attr("cx", d => d.x)
        .attr("cy", d => d.y);
    }

    function dragstarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event, d) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    return () => {
      simulation.stop();
      tooltip.remove();
    };
  }, [selectedData]);
  
  return (
    <div>
  <div className="mb-4">
    <label>
      <input
        type="radio"
        value="data1"
        checked={selectedData === "data1"}
        onChange={() => setSelectedData("data1")}
      />
      Data 1
    </label>
    <label className="ml-4">
      <input
        type="radio"
        value="data2"
        checked={selectedData === "data2"}
        onChange={() => setSelectedData("data2")}
      />
      Data 2
    </label>
  </div>
  <svg ref={ref}></svg>
  </div>
  );
};
