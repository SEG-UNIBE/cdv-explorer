import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

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

    const minBipsWritten = d3.min(sparseSeries, (entry) => entry.bipsWritten) || 1;
    const maxBipsWritten = d3.max(sparseSeries, (entry) => entry.bipsWritten) || minBipsWritten;
    const authorsByBipsWritten = new Map(
      sparseSeries.map((entry) => [entry.bipsWritten, entry.authors])
    );
    const series = d3.range(minBipsWritten, maxBipsWritten + 1).map((bipsWritten) => ({
      bipsWritten,
      authors: authorsByBipsWritten.get(bipsWritten) || 0,
    }));

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'author-histogram-tooltip')
      .style('position', 'absolute')
      .style('background', '#1a1a1a')
      .style('color', '#fff')
      .style('padding', '6px 10px')
      .style('border-radius', '4px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('opacity', 0);

    const margin = { top: 20, right: 20, bottom: 56, left: 56 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleLinear()
      .domain([minBipsWritten - 0.5, maxBipsWritten + 0.5])
      .range([0, innerWidth]);

    const barWidth = Math.max(6, innerWidth / series.length - 6);

    const y = d3.scaleLinear()
      .domain([0, d3.max(series, (entry) => entry.authors) || 0])
      .nice()
      .range([innerHeight, 0]);

    const g = svg
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    g.append('g')
      .call(d3.axisLeft(y).ticks(6))
      .call((axis) => axis.selectAll('line').attr('stroke', '#d7dee8'));

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).ticks(series.length).tickFormat(d3.format('d')))
      .selectAll('text')
      .style('font-size', '11px');

    g.selectAll('rect')
      .data(series)
      .enter()
      .append('rect')
      .attr('x', (entry) => x(entry.bipsWritten) - barWidth / 2)
      .attr('y', (entry) => y(entry.authors))
      .attr('width', barWidth)
      .attr('height', (entry) => innerHeight - y(entry.authors))
      .attr('rx', 4)
      .attr('fill', '#84a98c')
      .on('mouseover', function (event, entry) {
        d3.select(this).attr('fill', '#52796f');
        tooltip
          .style('opacity', 1)
          .html(
            `<strong>${entry.bipsWritten}</strong> BIPs written<br/>` +
            `${entry.authors} author${entry.authors === 1 ? '' : 's'}`
          );
      })
      .on('mousemove', function (event) {
        tooltip
          .style('left', `${event.pageX + 10}px`)
          .style('top', `${event.pageY - 28}px`);
      })
      .on('mouseout', function () {
        d3.select(this).attr('fill', '#84a98c');
        tooltip.style('opacity', 0);
      });

    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 44)
      .attr('text-anchor', 'middle')
      .style('font-size', '12px')
      .text('BIPs written per author');

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -40)
      .attr('text-anchor', 'middle')
      .style('font-size', '12px')
      .text('Number of authors');

    return () => {
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.author-histogram-tooltip').remove();
    };
  }, [data, width, height]);

  return <svg ref={ref} role="img" aria-label="Author contribution histogram" />;
};
