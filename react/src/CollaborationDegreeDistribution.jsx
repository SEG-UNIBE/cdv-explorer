import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

const DEGREE_BAR_COLOR = 'var(--chart-accent-blue)';
const DEGREE_BAR_HOVER_COLOR = 'var(--chart-accent-blue-hover)';

export function CollaborationDegreeDistribution({ data, width = 640, height = 410 }) {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.collaboration-degree-tooltip').remove();

    if (!Array.isArray(data) || data.length === 0) {
      return;
    }

    const sparseSeries = data
      .map((entry) => ({
        degree: Number(entry.degree || 0),
        authorCount: Number(entry.authorCount || 0),
      }))
      .filter((entry) => entry.degree >= 0 && entry.authorCount > 0)
      .sort((left, right) => left.degree - right.degree);

    if (sparseSeries.length === 0) {
      return;
    }

    // Build display items: one slot per real data point + one '…' slot per gap ≥ 3
    const displayItems = [];
    let ellipsisIdx = 0;
    sparseSeries.forEach((entry, i) => {
      if (i > 0 && entry.degree - sparseSeries[i - 1].degree >= 3) {
        displayItems.push({ key: `…_${ellipsisIdx++}`, isEllipsis: true, degree: null, authorCount: 0 });
      }
      displayItems.push({ key: String(entry.degree), isEllipsis: false, degree: entry.degree, authorCount: entry.authorCount });
    });

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'collaboration-degree-tooltip')
      .style('position', 'absolute')
      .style('background', 'var(--tooltip-bg)')
      .style('color', 'var(--tooltip-text)')
      .style('padding', '6px 10px')
      .style('border-radius', '4px')
      .style('border', '1px solid var(--tooltip-border)')
      .style('box-shadow', 'var(--tooltip-shadow)')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('opacity', 0);

    const margin = { top: 30, right: 18, bottom: 58, left: 68 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleBand()
      .domain(displayItems.map((entry) => entry.key))
      .range([0, innerWidth])
      .padding(0.14);

    const maxAuthorCount = d3.max(displayItems, (entry) => entry.authorCount) || 0;

    const y = d3.scaleLinear()
      .domain([0, maxAuthorCount > 0 ? maxAuthorCount * 1.16 : 1])
      .nice()
      .range([innerHeight, 0]);

    const g = svg
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    g.append('g')
      .call(d3.axisLeft(y).ticks(6).tickFormat(d3.format('d')))
      .call((axis) => axis.selectAll('line').attr('stroke', 'var(--chart-grid)'))
      .call((axis) => axis.selectAll('text').style('font-size', '13px'));

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).tickSizeOuter(0).tickFormat((key) => (key.startsWith('…') ? '…' : key)))
      .selectAll('text')
      .style('font-size', '12px')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.8rem');

    g.selectAll('rect')
      .data(displayItems.filter((entry) => !entry.isEllipsis))
      .enter()
      .append('rect')
      .attr('x', (entry) => x(entry.key))
      .attr('y', (entry) => y(entry.authorCount))
      .attr('width', x.bandwidth())
      .attr('height', (entry) => innerHeight - y(entry.authorCount))
      .attr('rx', 5)
      .attr('fill', DEGREE_BAR_COLOR)
      .on('mouseover', function (event, entry) {
        d3.select(this).attr('fill', DEGREE_BAR_HOVER_COLOR);
        tooltip
          .style('opacity', 1)
          .html(
            `There ${entry.authorCount === 1 ? 'is' : 'are'} <strong>${entry.authorCount}</strong> ` +
            `author${entry.authorCount === 1 ? '' : 's'} with exactly ${entry.degree} ` +
            `distinct co-author${entry.degree === 1 ? '' : 's'}.`
          );
      })
      .on('mousemove', function (event) {
        tooltip
          .style('left', `${event.pageX + 10}px`)
          .style('top', `${event.pageY - 28}px`);
      })
      .on('mouseout', function () {
        d3.select(this).attr('fill', DEGREE_BAR_COLOR);
        tooltip.style('opacity', 0);
      });

    g.selectAll('text.bar-label')
      .data(displayItems.filter((entry) => !entry.isEllipsis && entry.authorCount > 0))
      .enter()
      .append('text')
      .attr('class', 'bar-label')
      .attr('x', (entry) => (x(entry.key) || 0) + x.bandwidth() / 2)
      .attr('y', (entry) => y(entry.authorCount) - 8)
      .attr('text-anchor', 'middle')
      .style('font-size', '12px')
      .style('font-weight', 600)
      .style('fill', 'var(--chart-text)')
      .text((entry) => entry.authorCount);

    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 44)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .text('Distinct co-authors per author');

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -48)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .text('Number of authors');

    return () => {
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.collaboration-degree-tooltip').remove();
    };
  }, [data, height, width]);

  return <svg ref={ref} role="img" aria-label="Collaboration degree distribution" />;
}
