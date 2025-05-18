import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { sankey, sankeyLinkHorizontal } from 'd3-sankey';

export const BipSankeyChart = ({ data, width = 700, height = 500 }) => {
  const svgRef = useRef();
  const tooltipRef = useRef();

  useEffect(() => {
    if (!data || !data.nodes || !data.links) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove(); // clear previous render

    const tooltip = d3.select(tooltipRef.current);

    const margin = { top: 30, right: 10, bottom: 10, left: 140 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const sankeyGenerator = sankey()
      .nodeWidth(20)
      .nodePadding(30)
      .extent([[0, 0], [innerWidth, innerHeight]]);

    const { nodes, links } = sankeyGenerator({
      nodes: data.nodes.map(d => ({ ...d })),
      links: data.links.map(d => ({ ...d })),
    });

    const darkBlue = '#08306b';
    const mediumBlue = '#4292c6';
    const lightBlue = '#deebf7';

    const getNodeColor = d => {
      const midX = innerWidth / 2;
      if (d.x0 < midX * 0.6) return darkBlue;
      if (d.x0 > midX * 1.4) return lightBlue;
      return mediumBlue;
    };

    const nodeColorMap = {};
    nodes.forEach(d => {
      nodeColorMap[d.name] = getNodeColor(d);
    });

    const g = svg
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const defs = svg.append('defs');

    links.forEach((link, i) => {
      const gradientId = `gradient-${i}`;
      const sourceColor = nodeColorMap[link.source.name];
      const targetColor = nodeColorMap[link.target.name];

      const gradient = defs.append('linearGradient')
        .attr('id', gradientId)
        .attr('gradientUnits', 'userSpaceOnUse')
        .attr('x1', link.source.x1 + margin.left)
        .attr('x2', link.target.x0 + margin.left)
        .attr('y1', (link.source.y0 + link.source.y1) / 2 + margin.top)
        .attr('y2', (link.target.y0 + link.target.y1) / 2 + margin.top);

      gradient.append('stop')
        .attr('offset', '0%')
        .attr('stop-color', sourceColor);

      gradient.append('stop')
        .attr('offset', '100%')
        .attr('stop-color', targetColor);
    });

    // Render links with tooltip and hover effects
    g.append('g')
      .selectAll('path')
      .data(links)
      .join('path')
      .attr('d', sankeyLinkHorizontal())
      .attr('stroke', (d, i) => `url(#gradient-${i})`)
      .attr('stroke-width', d => Math.max(1, d.width))
      .attr('fill', 'none')
      .attr('opacity', 0.7)
      .on('mouseover', function (event, d) {
        d3.select(this).attr('opacity', 1).attr('stroke-width', d.width + 2);

        tooltip
          .style('visibility', 'visible')
          .html(`<strong>${d.source.name} → ${d.target.name}</strong><br/>Value: ${d.value}`);
      })
      .on('mousemove', function (event) {
        tooltip
          .style('top', `${event.pageY - 40}px`)
          .style('left', `${event.pageX + 10}px`);
      })
      .on('mouseout', function () {
        d3.select(this).attr('opacity', 0.7).attr('stroke-width', d => Math.max(1, d.width));
        tooltip.style('visibility', 'hidden');
      });

    // Render nodes
    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g');

    node.append('rect')
      .attr('x', d => d.x0)
      .attr('y', d => d.y0)
      .attr('height', d => d.y1 - d.y0)
      .attr('width', d => d.x1 - d.x0)
      .attr('fill', d => nodeColorMap[d.name]);

    // Labels with position-aware coloring
    node.append('text')
      .attr('x', d => d.x0 - 6)
      .attr('y', d => (d.y1 + d.y0) / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .text(d => d.name)
      .attr('fill', '#666')
      .filter(d => d.x0 < width / 2)
      .attr('x', d => d.x1 + 6)
      .attr('text-anchor', 'start')
      .attr('fill', d => d3.color(nodeColorMap[d.name]).darker(1).toString());

  }, [data, width, height]);

  return (
    <div style={{ position: 'relative' }}>
      <svg ref={svgRef}></svg>
      <div
        ref={tooltipRef}
        style={{
          position: 'absolute',
          padding: '6px 10px',
          background: 'white',
          border: '1px solid #ccc',
          borderRadius: '4px',
          pointerEvents: 'none',
          fontSize: '12px',
          visibility: 'hidden',
          zIndex: 10
        }}
      />
    </div>
  );
};
