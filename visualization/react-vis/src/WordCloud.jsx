import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import cloud from 'd3-cloud';

export const WordCloud = ({ words, width = 700, height = 400 }) => {
  const svgRef = useRef();

  useEffect(() => {
    if (!words || words.length === 0) return;

    // Clear any previous word cloud
    d3.select(svgRef.current).selectAll('*').remove();

    const maxCount = d3.max(words, d => d.count);
    const sizeScale = d3.scaleLinear()
      .domain([0, maxCount])
      .range([15, 60]); // Adjust min/max font sizes here

    const layout = cloud()
      .size([width, height])
      .words(words.map(d => ({
        text: d.word,
        size: sizeScale(d.count)
      })))
      .padding(5)
      .rotate(() => (Math.random() > 0.5 ? 0 : 90))
      .font('Impact')
      .fontSize(d => d.size)
      .on('end', draw);

    layout.start();

    function draw(words) {
      const svg = d3.select(svgRef.current)
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .append('g')
        .attr('transform', `translate(${width / 2}, ${height / 2})`);

      svg.selectAll('text')
        .data(words)
        .enter()
        .append('text')
        .style('font-family', 'Impact')
        .style('font-size', d => `${d.size}px`)
        .style('fill', () => d3.schemeCategory10[Math.floor(Math.random() * 10)])
        .attr('text-anchor', 'middle')
        .attr('transform', d => `translate(${d.x}, ${d.y}) rotate(${d.rotate})`)
        .text(d => d.text);
    }
  }, [words, width, height]);

  return <svg ref={svgRef}></svg>;
};
