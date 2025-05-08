import * as d3 from 'd3';
import { useEffect, useRef, useState } from 'react';
import { Dropdown } from 'primereact/dropdown';
import { RadioButton } from 'primereact/radiobutton';

export const NetworkDiagram = ({ width, height, data }) => {
  const ref = useRef();
  const [colorBy, setColorBy] = useState("group");
  const [linkType, setLinkType] = useState("references");

  const nodes = data.nodes;
  const links = data.links[linkType];

  useEffect(() => {
    const width = 1500;
    const height = 750;

    let color;
    if (colorBy === "compliance_score") {
      color = d3.scaleSequential()
    .domain([50, 100]) // or use d3.extent(nodes, d => d.compliance_score)
    .interpolator(d3.interpolateBlues);
    } else {
      const uniqueGroups = [...new Set(nodes.map(d => d[colorBy]))];

color = d3.scaleOrdinal()
  .domain(uniqueGroups)
  .range(d3.quantize(d3.interpolateBlues, uniqueGroups.length + 1).slice(1));
    }

    const svg = d3.select(ref.current)
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height])
      .style("maxWidth", "100%")
      .style("height", "auto");

    svg.selectAll("*").remove(); // clear previous render

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
      .force("x", d3.forceX(width / 2).strength(0.05))
      .force("y", d3.forceY(height / 2).strength(0.05))
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
      .attr("fill", d => color(d[colorBy] ?? 'default'))
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
        .attr("cx", d => d.x = Math.max(5, Math.min(width - 5, d.x)))
        .attr("cy", d => d.y = Math.max(5, Math.min(height - 5, d.y)));
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
  }, [colorBy,linkType, data]);
  
  return (
    <div>
      <div style={{ display: 'flex', gap: '2rem', alignItems: 'center', marginBottom: '1.5rem' }}>
  <Dropdown
    inputId="linkType"
    value={linkType}
    options={[
      { label: 'Regex Interrelations', value: 'references' },
      { label: 'LLM Interrelations', value: 'dependencies' },
      { label: 'Preamble Requires', value: 'requires' },
      { label: 'Preamble Replaces', value: 'replaces' },
      { label: 'Preamble Superseded By', value: 'superseded_by' }
    ]}
    onChange={(e) => setLinkType(e.value)}
    placeholder="Link Type"
    className="w-full md:w-14rem"
    style={{ width: '125px' }}
  />

<div className="radio-group" style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
  <div className="radio-option" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
    <RadioButton
      inputId="color-group"
      name="colorBy"
      value="group"
      onChange={(e) => setColorBy(e.value)}
      checked={colorBy === 'group'}
    />
    <label htmlFor="color-group">Color by Layer</label>
  </div>
  <div className="radio-option" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
    <RadioButton
      inputId="color-compliance"
      name="colorBy"
      value="compliance_score"
      onChange={(e) => setColorBy(e.value)}
      checked={colorBy === 'compliance_score'}
    />
    <label htmlFor="color-compliance">Color by Compliance</label>
  </div>
  </div>
</div>


  <svg ref={ref}></svg>
  </div>
  );
};
