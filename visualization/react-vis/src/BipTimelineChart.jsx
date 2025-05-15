import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

export const BipTimelineChart = ({ data, width = 600, height = 300 }) => {
  const ref = useRef();

  useEffect(() => {
    if (!data || data.length === 0) return;

    // Clear previous chart and tooltips
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();
    d3.select('body').selectAll('.bip-tooltip').remove();

    // Tooltip setup
    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'bip-tooltip')
      .style('position', 'absolute')
      .style('background', '#1a1a1a')
      .style('color', '#fff')
      .style('padding', '6px 10px')
      .style('border-radius', '4px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('opacity', 0);

    const margin = { top: 20, right: 20, bottom: 40, left: 50 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleBand()
      .domain(data.map(d => d.year))
      .range([0, innerWidth])
      .padding(0.1);

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.count)])
      .nice()
      .range([innerHeight, 0]);

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    g.append("g").call(d3.axisLeft(y));

    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .attr("transform", "rotate(-45)")
      .style("text-anchor", "end");

    g.selectAll("rect")
      .data(data)
      .enter()
      .append("rect")
      .attr("x", d => x(d.year))
      .attr("y", d => y(d.count))
      .attr("width", x.bandwidth())
      .attr("height", d => innerHeight - y(d.count))
      .attr("fill", "#4c78a8")
      .on("mouseover", function (event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr("fill", "#003f5c");

        tooltip
          .style("opacity", 1)
          .html(`<strong>${d.year}</strong><br/>Total BIPs: ${d.count}`);
      })
      .on("mousemove", function (event) {
        tooltip
          .style("left", `${event.pageX + 10}px`)
          .style("top", `${event.pageY - 28}px`);
      })
      .on("mouseout", function () {
        d3.select(this)
          .transition()
          .duration(200)
          .attr("fill", "#4c78a8");

        tooltip.style("opacity", 0);
      });

    // Cleanup
    return () => {
      svg.selectAll("*").remove();
      d3.select('body').selectAll('.bip-tooltip').remove();
    };
  }, [data]);

  return <svg ref={ref}></svg>;
};
