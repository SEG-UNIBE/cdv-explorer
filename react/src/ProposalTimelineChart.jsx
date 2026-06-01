import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { renderProposalListHtml } from './bipTooltipContent';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';

export const ProposalTimelineChart = ({ data, width = 600, height = 300 }) => {
  const ref = useRef();
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

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
      .style('background', 'var(--tooltip-bg)')
      .style('color', 'var(--tooltip-text)')
      .style('padding', '6px 10px')
      .style('border-radius', '4px')
      .style('border', '1px solid var(--tooltip-border)')
      .style('box-shadow', 'var(--tooltip-shadow)')
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
        renderProposalListHtml(entry.bips, snapshotLabel, { ecosystem, linkMode })
      );
    };

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const margin = { top: 24, right: 60, bottom: 36, left: 56 };
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

    const everyOtherYear = series.filter((_, i) => i % 2 === 0).map((d) => d.year);
    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).tickValues(everyOtherYear))
      .selectAll('text')
      .style('font-size', '13px');

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

    g.selectAll('text.bar-label')
      .data(series.filter((d) => d.count > 0))
      .enter()
      .append('text')
      .attr('class', 'bar-label')
      .attr('x', (d) => x(d.year) + x.bandwidth() / 2)
      .attr('y', (d) => yBars(d.count) - 4)
      .attr('text-anchor', 'middle')
      .style('font-size', '11px')
      .style('fill', 'var(--chart-text)')
      .style('pointer-events', 'none')
      .text((d) => d.count);

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
      .attr('stroke', 'var(--chart-contrast)')
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
  }, [data, ecosystem, height, linkMode, snapshotLabel, width]);

  return <svg ref={ref} role="img" aria-label="Proposal timeline chart" />;
};
