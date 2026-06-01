import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

const HISTOGRAM_BAR_COLOR = '#2f9e44';
const HISTOGRAM_BAR_HOVER_COLOR = '#2b8a3e';

export const AuthorContributionHistogram = ({ data, width = 600, height = 400 }) => {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.author-histogram-tooltip').remove();

    if (!Array.isArray(data) || data.length === 0) {
      return;
    }

    const sparseSeries = data
      .map((entry) => ({
        bipsWritten: Number(entry.bips_written || 0),
        authors: Number(entry.authors || 0),
      }))
      .filter((entry) => entry.bipsWritten > 0)
      .sort((left, right) => left.bipsWritten - right.bipsWritten);

    if (sparseSeries.length === 0) {
      return;
    }

    // Build display items: one slot per real data point + one '…' slot per gap ≥ 3
    const displayItems = [];
    let ellipsisIdx = 0;
    sparseSeries.forEach((entry, i) => {
      if (i > 0 && entry.bipsWritten - sparseSeries[i - 1].bipsWritten >= 3) {
        displayItems.push({ key: `…_${ellipsisIdx++}`, isEllipsis: true, bipsWritten: null, authors: 0 });
      }
      displayItems.push({ key: String(entry.bipsWritten), isEllipsis: false, bipsWritten: entry.bipsWritten, authors: entry.authors });
    });

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'author-histogram-tooltip')
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

    const margin = { top: 20, right: 24, bottom: 58, left: 68 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleBand()
      .domain(displayItems.map((d) => d.key))
      .range([0, innerWidth])
      .padding(0.18);

    const y = d3.scaleLinear()
      .domain([0, d3.max(displayItems, (d) => d.authors) || 0])
      .nice()
      .range([innerHeight, 0]);

    const g = svg
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    g.append('g')
      .call(d3.axisLeft(y).ticks(6))
      .call((axis) => axis.selectAll('line').attr('stroke', 'var(--chart-grid)'))
      .call((axis) => axis.selectAll('text').style('font-size', '13px'));

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).tickFormat((key) => (key.startsWith('…') ? '…' : key)))
      .selectAll('text')
      .style('font-size', '13px');

    g.selectAll('rect')
      .data(displayItems.filter((d) => !d.isEllipsis))
      .enter()
      .append('rect')
      .attr('x', (d) => x(d.key))
      .attr('y', (d) => y(d.authors))
      .attr('width', x.bandwidth())
      .attr('height', (d) => innerHeight - y(d.authors))
      .attr('rx', 4)
      .attr('fill', HISTOGRAM_BAR_COLOR)
      .on('mouseover', function (event, entry) {
        d3.select(this).attr('fill', HISTOGRAM_BAR_HOVER_COLOR);
        tooltip
          .style('opacity', 1)
          .html(
            `There ${entry.authors === 1 ? 'is' : 'are'} <strong>${entry.authors}</strong> ` +
            `author${entry.authors === 1 ? '' : 's'} that authored <strong>${entry.bipsWritten}</strong> ` +
            `BIP${entry.bipsWritten === 1 ? '' : 's'}.`
          );
      })
      .on('mousemove', function (event) {
        tooltip
          .style('left', `${event.pageX + 10}px`)
          .style('top', `${event.pageY - 28}px`);
      })
      .on('mouseout', function () {
        d3.select(this).attr('fill', HISTOGRAM_BAR_COLOR);
        tooltip.style('opacity', 0);
      });

    g.selectAll('text.bar-label')
      .data(displayItems.filter((d) => !d.isEllipsis && d.authors > 0))
      .enter()
      .append('text')
      .attr('class', 'bar-label')
      .attr('x', (d) => x(d.key) + x.bandwidth() / 2)
      .attr('y', (d) => y(d.authors) - 6)
      .attr('text-anchor', 'middle')
      .style('font-size', '12px')
      .style('fill', 'var(--chart-text)')
      .text((d) => d.authors);

    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 44)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .text('BIPs written per author');

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -48)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .text('Number of authors');

    return () => {
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.author-histogram-tooltip').remove();
    };
  }, [data, width, height]);

  return <svg ref={ref} role="img" aria-label="Author contribution histogram" />;
};
