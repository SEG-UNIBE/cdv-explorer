import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { sankey, sankeyLinkHorizontal } from 'd3-sankey';
import { renderBipListHtml } from './bipTooltipContent';

export const ProposalSankeyChart = ({ data, width = 700, height = 500 }) => {
  const svgRef = useRef();
  const hasRenderableData = Boolean(data?.nodes?.length && data?.links?.length);

  useEffect(() => {
    if (!hasRenderableData) {
      d3.select(svgRef.current).selectAll('*').remove();
      return;
    }

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const tooltipNode = document.createElement('div');
    document.body.appendChild(tooltipNode);
    const tooltip = d3.select(tooltipNode)
      .attr('class', 'proposal-sankey-tooltip')
      .style('position', 'absolute')
      .style('padding', '6px 10px')
      .style('background', '#1a1a1a')
      .style('color', '#fff')
      .style('border', '1px solid #111827')
      .style('border-radius', '4px')
      .style('pointer-events', 'none')
      .style('font-size', '12px')
      .style('visibility', 'hidden')
      .style('opacity', 0)
      .style('line-height', '1.45')
      .style('z-index', 10);
    let pinnedLinkKey = null;

    const margin = { top: 30, right: 10, bottom: 10, left: 140 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const sankeyGenerator = sankey()
      .nodeWidth(20)
      .nodePadding(30)
      .extent([[0, 0], [innerWidth, innerHeight]]);

    let nodes = [];
    let links = [];
    try {
      ({ nodes, links } = sankeyGenerator({
        nodes: data.nodes.map((d) => ({ ...d })),
        links: data.links.map((d) => ({ ...d })),
      }));
    } catch (error) {
      console.error('Failed to render sankey data', error);
      svg.selectAll('*').remove();
      return;
    }

    const darkBlue = '#08306b';
    const mediumBlue = '#4292c6';
    const lightBlue = '#deebf7';

    const getNodeColor = (d) => {
      const midX = innerWidth / 2;
      if (d.x0 < midX * 0.6) return darkBlue;
      if (d.x0 > midX * 1.4) return lightBlue;
      return mediumBlue;
    };

    const nodeColorMap = {};
    nodes.forEach((d) => {
      nodeColorMap[d.name] = getNodeColor(d);
    });

    svg
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    svg.append('rect')
      .attr('width', width)
      .attr('height', height)
      .attr('fill', 'transparent')
      .style('cursor', 'grab');

    const viewport = svg.append('g');

    const g = viewport
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

    const linkGroup = g.append('g');

    const renderTooltipHtml = (link) => {
      return (
        `<strong>${link.source.name} → ${link.target.name}</strong><br/>` +
        `Count: ${link.value}<br/>` +
        renderBipListHtml(link.bips)
      );
    };

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 40}px`);
    };

    const resetLinkStyles = () => {
      linkGroup.selectAll('path')
        .attr('opacity', 0.7)
        .attr('stroke-width', (d) => Math.max(1, d.width));
    };

    linkGroup
      .selectAll('path')
      .data(links)
      .join('path')
      .attr('d', sankeyLinkHorizontal())
      .attr('stroke', (d, i) => `url(#gradient-${i})`)
      .attr('stroke-width', (d) => Math.max(1, d.width))
      .attr('fill', 'none')
      .attr('opacity', 0.7)
      .on('mouseover', function (event, d) {
        if (pinnedLinkKey) {
          return;
        }
        d3.select(this).attr('opacity', 1).attr('stroke-width', d.width + 2);

        tooltip
          .style('visibility', 'visible')
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(d));
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mousemove', function (event) {
        if (pinnedLinkKey) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedLinkKey) {
          return;
        }
        d3.select(this).attr('opacity', 0.7).attr('stroke-width', (d) => Math.max(1, d.width));
        tooltip.style('visibility', 'hidden').style('opacity', 0);
      })
      .on('click', function (event, d) {
        event.stopPropagation();
        pinnedLinkKey = `${d.source.name}|||${d.target.name}`;
        resetLinkStyles();
        d3.select(this)
          .attr('opacity', 1)
          .attr('stroke-width', d.width + 2);
        tooltip
          .style('visibility', 'visible')
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(d));
        setTooltipPosition(event.pageX, event.pageY);
      });

    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g');

    node.append('rect')
      .attr('x', (d) => d.x0)
      .attr('y', (d) => d.y0)
      .attr('height', (d) => d.y1 - d.y0)
      .attr('width', (d) => d.x1 - d.x0)
      .attr('fill', (d) => nodeColorMap[d.name]);

    node.append('text')
      .attr('x', (d) => d.x0 - 6)
      .attr('y', (d) => (d.y1 + d.y0) / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .text((d) => d.name)
      .attr('fill', '#666')
      .filter((d) => d.x0 < width / 2)
      .attr('x', (d) => d.x1 + 6)
      .attr('text-anchor', 'start')
      .attr('fill', (d) => d3.color(nodeColorMap[d.name]).darker(1).toString());

    const zoom = d3.zoom()
      .scaleExtent([0.7, 4])
      .on('start', () => {
        svg.style('cursor', 'grabbing');
      })
      .on('zoom', (event) => {
        viewport.attr('transform', event.transform);
      })
      .on('end', () => {
        svg.style('cursor', 'grab');
      });

    svg.call(zoom)
      .on('dblclick.zoom', null);

    svg.call(
      zoom.transform,
      d3.zoomIdentity.translate(-margin.left * 0.25, height * 0.02).scale(1)
    );

    svg.on('click', () => {
      pinnedLinkKey = null;
      resetLinkStyles();
      tooltip
        .style('visibility', 'hidden')
        .style('opacity', 0)
        .style('pointer-events', 'none');
    });

    return () => {
      svg.selectAll('*').remove();
      tooltip.remove();
    };
  }, [data, width, height, hasRenderableData]);

  return (
    <div>
      {!hasRenderableData && (
        <div style={{ padding: '1rem 0', color: '#666' }}>
          No sankey data available for the current dataset.
        </div>
      )}
      <svg ref={svgRef}></svg>
    </div>
  );
};
