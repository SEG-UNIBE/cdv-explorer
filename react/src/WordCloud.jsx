import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import cloud from 'd3-cloud';

export const WordCloud = ({ words, width = 1250, height = 750 }) => {
  const svgRef = useRef();

  useEffect(() => {
    if (!words || words.length === 0) return;

    // Clear previous word cloud
    d3.select(svgRef.current).selectAll('*').remove();
    d3.select('body').selectAll('.wordcloud-tooltip').remove(); // clean any previous tooltips

    const maxCount = d3.max(words, d => d.count);
    const sizeScale = d3.scaleLinear()
      .domain([0, maxCount])
      .range([15, 60]); // font size range

    // Assign consistent blue shades to each word
    const coloredWords = words.map(d => ({
      text: d.word,
      count: d.count,
      size: sizeScale(d.count),
      color: d3.interpolateBlues(Math.random() * 0.6 + 0.4) // avoid too-light shades
    }));

    // Layout
    const layout = cloud()
      .size([width, height])
      .words(coloredWords)
      .padding(5)
      .rotate(() => (Math.random() > 0.5 ? 0 : 90))
      .font('Impact')
      .fontSize(d => d.size)
      .on('end', draw);

    layout.start();

    function draw(words) {
      // Tooltip
      const tooltip = d3.select('body')
        .append('div')
        .attr('class', 'wordcloud-tooltip')
        .style('position', 'absolute')
        .style('background', '#1a1a1a')
        .style('color', '#fff')
        .style('padding', '6px 10px')
        .style('border-radius', '4px')
        .style('font-size', '12px')
        .style('pointer-events', 'none')
        .style('opacity', 0);

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
        .style('fill', d => d.color)
        .attr('text-anchor', 'middle')
        .attr('transform', d => `translate(${d.x}, ${d.y}) rotate(${d.rotate})`)
        .text(d => d.text)
        .on('mouseover', function (event, d) {
          d3.select(this)
            .transition().duration(200)
            .style('fill', '#003f5c')
            .style('font-size', `${d.size * 1.2}px`)
            .attr('stroke', '#fff')
            .attr('stroke-width', 1);

          tooltip
            .style('opacity', 1)
            .html(`<strong>${d.text}</strong><br/>Count: ${d.count}`);
        })
        .on('mousemove', function (event) {
          tooltip
            .style('left', `${event.pageX + 10}px`)
            .style('top', `${event.pageY - 28}px`);
        })
        .on('mouseout', function (event, d) {
          d3.select(this)
            .transition().duration(200)
            .style('fill', d.color)
            .style('font-size', `${d.size}px`)
            .attr('stroke', 'none');

          tooltip.style('opacity', 0);
        });
    }

    // Clean up
    return () => {
      d3.select(svgRef.current).selectAll('*').remove();
      d3.select('body').selectAll('.wordcloud-tooltip').remove();
    };
  }, [words, width, height]);

  return <svg ref={svgRef}></svg>;
};
