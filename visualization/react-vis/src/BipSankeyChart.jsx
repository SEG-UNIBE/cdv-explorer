// BipSankeyChart.jsx
import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { sankey, sankeyLinkHorizontal } from 'd3-sankey';

export const BipSankeyChart = ({ data, width = 700, height = 500 }) => {
  const svgRef = useRef();

  useEffect(() => {
    if (!data || !data.nodes || !data.links) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove(); // clear previous render

    const margin = { top: 10, right: 10, bottom: 10, left: 10 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Create Sankey layout
    const sankeyGenerator = sankey()
      .nodeWidth(20)
      .nodePadding(10)
      .extent([[0, 0], [innerWidth, innerHeight]]);

    const { nodes, links } = sankeyGenerator({
      nodes: data.nodes.map(d => ({ ...d })),
      links: data.links.map(d => ({ ...d })),
    });

    const color = d3.scaleOrdinal(d3.schemeCategory10);

    const g = svg
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Links
    g.append('g')
      .selectAll('path')
      .data(links)
      .join('path')
      .attr('d', sankeyLinkHorizontal())
      .attr('stroke', d => color(d.source.id))
      .attr('stroke-width', d => Math.max(1, d.width))
      .attr('fill', 'none')
      .attr('opacity', 0.5);

    // Nodes
    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g');

    node.append('rect')
      .attr('x', d => d.x0)
      .attr('y', d => d.y0)
      .attr('height', d => d.y1 - d.y0)
      .attr('width', d => d.x1 - d.x0)
      .attr('fill', d => color(d.id));

    node.append('text')
      .attr('x', d => d.x0 - 6)
      .attr('y', d => (d.y1 + d.y0) / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .text(d => d.id)
      .filter(d => d.x0 < width / 2)
      .attr('x', d => d.x1 + 6)
      .attr('text-anchor', 'start');
  }, [data, width, height]);

  return <svg ref={svgRef}></svg>;
};

