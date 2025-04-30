// TopAuthorsChart.jsx
import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

export const TopAuthorsChart = ({ data, width = 700, height = 400 }) => {
  const ref = useRef();

  useEffect(() => {
    const authorCounts = {};

    data.nodes.forEach(bip => {
      if (Array.isArray(bip.author)) {
        bip.author.forEach(author => {
          const name = author.split('<')[0].trim(); // strip email
          authorCounts[name] = (authorCounts[name] || 0) + 1;
        });
      }
    });

    const sortedAuthors = Object.entries(authorCounts)
      .map(([author, count]) => ({ author, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();

    const margin = { top: 20, right: 20, bottom: 80, left: 100 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleLinear()
      .domain([0, d3.max(sortedAuthors, d => d.count)])
      .range([0, innerWidth]);

    const y = d3.scaleBand()
      .domain(sortedAuthors.map(d => d.author))
      .range([0, innerHeight])
      .padding(0.2);

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    g.append("g")
      .call(d3.axisLeft(y));

    g.selectAll("rect")
      .data(sortedAuthors)
      .enter()
      .append("rect")
      .attr("y", d => y(d.author))
      .attr("width", d => x(d.count))
      .attr("height", y.bandwidth())
      .attr("fill", "#69b3a2");

    g.selectAll("text.count")
      .data(sortedAuthors)
      .enter()
      .append("text")
      .attr("class", "count")
      .attr("x", d => x(d.count) + 5)
      .attr("y", d => y(d.author) + y.bandwidth() / 2 + 5)
      .text(d => d.count)
      .style("font-size", "12px");

    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).ticks(5))
      .style("display", "none"); // optional, hidden x-axis

  }, [data]);

  return <svg ref={ref} />;
};
