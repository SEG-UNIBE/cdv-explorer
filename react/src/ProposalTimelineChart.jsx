import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { renderBipListHtml } from './bipTooltipContent';

export const ProposalTimelineChart = ({ data, width = 600, height = 300 }) => {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.proposal-tooltip').remove();

    if (!data || data.length === 0) {
      return;
    }

    const series = [];
    let cumulative = 0;
    data.forEach((entry) => {
      cumulative += Number(entry.count || 0);
      series.push({
        year: String(entry.year),
        count: Number(entry.count || 0),
        cumulative,
        bips: Array.isArray(entry.bips) ? entry.bips : [],
      });
    });

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'proposal-tooltip')
      .style('position', 'absolute')
      .style('background', '#1a1a1a')
      .style('color', '#fff')
      .style('padding', '6px 10px')
      .style('border-radius', '4px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('max-width', '360px')
      .style('line-height', '1.45')
      .style('opacity', 0);

    let pinnedYear = null;

    const renderTooltipHtml = (entry) => {
      return (
        `<strong>${entry.year}</strong><br/>` +
        `New proposals: ${entry.count}<br/>` +
        `Cumulative proposals: ${entry.cumulative}<br/>` +
        renderBipListHtml(entry.bips)
      );
    };

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const margin = { top: 24, right: 60, bottom: 60, left: 56 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleBand()
      .domain(series.map((d) => d.year))
      .range([0, innerWidth])
      .padding(0.18);

    const yBars = d3.scaleLinear()
      .domain([0, d3.max(series, (d) => d.count) || 0])
      .nice()
      .range([innerHeight, 0]);

    const yLine = d3.scaleLinear()
      .domain([0, d3.max(series, (d) => d.cumulative) || 0])
      .nice()
      .range([innerHeight, 0]);

    const g = svg
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const resetBarStyles = () => {
      g.selectAll('rect')
        .attr('fill', '#4c78a8');
    };

    const resetPointStyles = () => {
      g.selectAll('circle.timeline-point')
        .attr('fill', '#e45756')
        .attr('r', 4);
    };

    g.append('g')
      .call(d3.axisLeft(yBars).ticks(6))
      .call((axis) => axis.select('.domain').attr('stroke', '#4c78a8'))
      .call((axis) => axis.selectAll('line').attr('stroke', '#d7dee8'))
      .call((axis) => axis.selectAll('text').attr('fill', '#4c78a8'));

    g.append('g')
      .attr('transform', `translate(${innerWidth},0)`)
      .call(d3.axisRight(yLine).ticks(6))
      .call((axis) => axis.select('.domain').attr('stroke', '#e45756'))
      .call((axis) => axis.selectAll('text').attr('fill', '#e45756'));

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
      .attr('transform', 'rotate(-45)')
      .style('text-anchor', 'end');

    g.selectAll('rect')
      .data(series)
      .enter()
      .append('rect')
      .attr('x', (d) => x(d.year))
      .attr('y', (d) => yBars(d.count))
      .attr('width', x.bandwidth())
      .attr('height', (d) => innerHeight - yBars(d.count))
      .attr('fill', '#4c78a8')
      .on('mouseover', function (event, d) {
        if (pinnedYear) {
          return;
        }

        d3.select(this)
          .transition()
          .duration(200)
          .attr('fill', '#003f5c');

        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(d));
      })
      .on('mousemove', function (event) {
        if (pinnedYear) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedYear) {
          return;
        }

        d3.select(this)
          .transition()
          .duration(200)
          .attr('fill', '#4c78a8');

        tooltip.style('opacity', 0);
      })
      .on('click', function (event, d) {
        event.stopPropagation();
        pinnedYear = d.year;
        resetBarStyles();
        resetPointStyles();
        d3.select(this).attr('fill', '#003f5c');
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(d));
        setTooltipPosition(event.pageX, event.pageY);
      });

    const line = d3.line()
      .x((d) => x(d.year) + x.bandwidth() / 2)
      .y((d) => yLine(d.cumulative))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(series)
      .attr('fill', 'none')
      .attr('stroke', '#e45756')
      .attr('stroke-width', 2.5)
      .attr('d', line);

    g.selectAll('circle.timeline-point')
      .data(series)
      .enter()
      .append('circle')
      .attr('class', 'timeline-point')
      .attr('cx', (d) => x(d.year) + x.bandwidth() / 2)
      .attr('cy', (d) => yLine(d.cumulative))
      .attr('r', 4)
      .attr('fill', '#e45756')
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .on('mouseover', function (event, d) {
        if (pinnedYear) {
          return;
        }

        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(d));
      })
      .on('mousemove', function (event) {
        if (pinnedYear) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedYear) {
          return;
        }
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, d) {
        event.stopPropagation();
        pinnedYear = d.year;
        resetBarStyles();
        resetPointStyles();
        d3.select(this)
          .attr('fill', '#b63f3e')
          .attr('r', 5.5);
        g.selectAll('rect')
          .filter((entry) => entry.year === d.year)
          .attr('fill', '#003f5c');
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(d));
        setTooltipPosition(event.pageX, event.pageY);
      });

    g.append('text')
      .attr('x', 0)
      .attr('y', -8)
      .attr('fill', '#4c78a8')
      .style('font-size', '12px')
      .text('New proposals');

    g.append('text')
      .attr('x', innerWidth)
      .attr('y', -8)
      .attr('text-anchor', 'end')
      .attr('fill', '#e45756')
      .style('font-size', '12px')
      .text('Cumulative total');

    svg.on('click', () => {
      pinnedYear = null;
      resetBarStyles();
      resetPointStyles();
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
    });

    return () => {
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.proposal-tooltip').remove();
    };
  }, [data, width, height]);

  return <svg ref={ref} role="img" aria-label="Proposal timeline chart" />;
};
