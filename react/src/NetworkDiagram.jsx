import * as d3 from 'd3';
import { useEffect, useRef, useState } from 'react';
import { Dropdown } from 'primereact/dropdown';
import { RadioButton } from 'primereact/radiobutton';

export const NetworkDiagram = ({ width, height, data }) => {
  const ref = useRef();
  const legendRef = useRef();
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
        .domain([50, 100])
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

    svg.selectAll("*").remove();

    // Define arrowhead marker
    svg.append("defs").append("marker")
      .attr("id", "arrowhead")
      .attr("viewBox", "-0 -5 10 10")
      .attr("refX", 15)
      .attr("refY", 0)
      .attr("orient", "auto")
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("xoverflow", "visible")
      .append("svg:path")
      .attr("d", "M 0,-5 L 10,0 L 0,5")
      .attr("fill", "#999")
      .style("stroke", "none");

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
      .attr("stroke-width", d => Math.sqrt(d.value))
      .attr("marker-end", "url(#arrowhead)")
      .attr("class", "link");

    const node = svg.append("g")
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", 10)
      .attr("fill", d => color(d[colorBy] ?? 'default'))
      .attr("class", "node")
      .on("mouseover", (event, d) => {
        tooltip.transition().duration(200).style("opacity", 1);
        tooltip.html(`
          <div><strong>BIP-${d.id}</strong> </div>
          <div><strong>Compliance Score:</strong> ${d.compliance_score ?? 'N/A'}</div>
          <div><strong>Layer:</strong> ${d.group ?? 'N/A'}</div>
        `);
        

        // Highlight node
        d3.select(event.currentTarget)
          .attr("stroke", "#003f5c")
          .attr("stroke-width", 3);

        // Highlight connected links
        link
          .filter(l => l.source.id === d.id || l.target.id === d.id)
          .attr("stroke", "#003f5c")
          .attr("stroke-opacity", 1)
          .attr("stroke-width", 3);
      })
      .on("click", (event, d) => {
        const url = `https://github.com/bitcoin/bips/blob/master/bip-${String(d.id).padStart(4, '0')}.mediawiki`;
        window.open(url, '_blank');
      })
      .on("mousemove", (event) => {
        tooltip
          .style("left", `${event.pageX + 10}px`)
          .style("top", `${event.pageY - 30}px`);
      })
      .on("mouseout", (event, d) => {
        tooltip.transition().duration(200).style("opacity", 0);

        d3.select(event.currentTarget)
          .attr("stroke", "#fff")
          .attr("stroke-width", 1.5);

        link
          .attr("stroke", "#999")
          .attr("stroke-opacity", 0.6)
          .attr("stroke-width", 1);
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

    d3.select(legendRef.current).selectAll("*").remove();

    if (colorBy === "group") {
      let entries = color.domain();
entries = entries.filter(group => group !== 'default'); // remove 'default'
entries = entries.slice(1); // remove the first item

      const blockSize = 18;
      const padding = 5;
    
      const svgLegend = d3.select(legendRef.current)
        .append("svg")
        .attr("width", 200)
        .attr("height", entries.length * (blockSize + padding));
    
      entries.forEach((group, i) => {
        // Color box
        svgLegend.append("rect")
          .attr("x", 0)
          .attr("y", i * (blockSize + padding))
          .attr("width", blockSize)
          .attr("height", blockSize)
          .style("fill", color(group));
    
        // Text label
        svgLegend.append("text")
          .attr("x", blockSize + 8)
          .attr("y", i * (blockSize + padding) + blockSize / 1.5)
          .text(group)
          .style("font-size", "13px")
          .style("alignment-baseline", "middle");
      });
    }
    

    if (colorBy === "compliance_score") {
      const values = d3.range(0, 1.01, 0.1);
      const size = 20;
      const spacing = 2;

      const scale = d3.scaleSequential()
        .domain([0, 1])
        .interpolator(d3.interpolateBlues);

      const svgLegend = d3.select(legendRef.current)
        .append("svg")
        .attr("width", values.length * (size + spacing))
        .attr("height", 70);

      svgLegend.append("text")
        .attr("x", 0)
        .attr("y", 14)
        .text("Compliance Score")
        .style("font-family", "sans-serif")
        .style("font-size", "14px");

      svgLegend.selectAll("rect")
        .data(values)
        .enter()
        .append("rect")
        .attr("x", (d, i) => i * (size + spacing))
        .attr("y", 20)
        .attr("width", size)
        .attr("height", size)
        .style("fill", d => scale(d));

      svgLegend.append("text")
        .attr("x", 0)
        .attr("y", 60)
        .text("50")
        .style("font-size", "12px");

      svgLegend.append("text")
        .attr("x", (values.length - 1) * (size + spacing))
        .attr("y", 60)
        .attr("text-anchor", "end")
        .text("100")
        .style("font-size", "12px");
    }

    return () => {
      simulation.stop();
      tooltip.remove();
    };

  }, [colorBy, linkType, data]);

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
          <div ref={legendRef} style={{ marginTop: '1rem' }}></div>
        </div>
      </div>

      <svg ref={ref}></svg>
      <div ref={legendRef} style={{ marginTop: '1rem' }}></div>
    </div>
  );
};
