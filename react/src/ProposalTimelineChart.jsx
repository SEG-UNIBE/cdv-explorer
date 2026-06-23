import * as d3 from 'd3';
import { positionTooltip } from './tooltipPosition';
import { useEffect, useRef } from 'react';
import { renderProposalListRow } from './bipTooltipContent';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { renderTooltipCardHtml } from './tooltipHtml';

const SOURCE_COLOR_FALLBACKS = ['#4c78a8', '#f58518', '#54a24b', '#b279a2', '#72b7b2'];
const TOTAL_LINE_COLOR = '#e45756';

function pickSourceColor(sourceId, sourceOrder, sources) {
  const explicit = sources?.[sourceId]?.color;
  if (explicit) return explicit;
  const index = (sourceOrder || []).indexOf(sourceId);
  return SOURCE_COLOR_FALLBACKS[(index >= 0 ? index : 0) % SOURCE_COLOR_FALLBACKS.length];
}

function sourceLabel(sourceId, sources) {
  const source = sources?.[sourceId];
  return source?.shortLabel || source?.acronym || sourceId || 'Proposals';
}

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

    // Determine the set of sources that actually contributed data, ordered by
    // the ecosystem's declared source order (so colors stay stable across renders).
    const presentSources = new Set();
    data.forEach((entry) => {
      Object.keys(entry.bySource || {}).forEach((id) => presentSources.add(id));
    });
    const sourceOrder = ecosystem?.sourceOrder || [];
    const orderedSourceIds = [
      ...sourceOrder.filter((id) => presentSources.has(id)),
      ...Array.from(presentSources).filter((id) => !sourceOrder.includes(id)),
    ];
    const hasSourceBreakdown = orderedSourceIds.length > 0;
    const isMultiSource = orderedSourceIds.length > 1;

    const series = [];
    const cumulativeBySource = Object.fromEntries(orderedSourceIds.map((id) => [id, 0]));
    let cumulativeTotal = 0;
    data.forEach((entry) => {
      const bySource = entry.bySource || {};
      const stackTotal = hasSourceBreakdown
        ? orderedSourceIds.reduce((sum, id) => sum + (bySource[id] || 0), 0)
        : Number(entry.count || 0);
      cumulativeTotal += stackTotal;
      orderedSourceIds.forEach((id) => {
        cumulativeBySource[id] += (bySource[id] || 0);
      });
      series.push({
        year: String(entry.year),
        count: stackTotal,
        cumulative: cumulativeTotal,
        cumulativeBySource: { ...cumulativeBySource },
        bySource: { ...bySource },
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

    const formatBreakdown = (bySource) => orderedSourceIds
      .filter((id) => (bySource[id] || 0) > 0)
      .map((id) => `${sourceLabel(id, ecosystem?.sources)}: ${bySource[id]}`)
      .join(', ');

    const renderTooltipHtml = (entry) => {
      const breakdown = isMultiSource ? formatBreakdown(entry.bySource) : '';
      const cumulativeBreakdown = isMultiSource ? formatBreakdown(entry.cumulativeBySource) : '';
      return renderTooltipCardHtml({
        titleHtml: `<strong>${entry.year}</strong>`,
        rows: [
          ['New Proposals', `${entry.count}${breakdown ? ` (${breakdown})` : ''}`],
          ['Cumulative', `${entry.cumulative}${cumulativeBreakdown ? ` (${cumulativeBreakdown})` : ''}`],
          renderProposalListRow(entry.bips, snapshotLabel, { ecosystem, linkMode }),
        ],
      });
    };

    const setTooltipPosition = (pageX, pageY) => {
      positionTooltip(tooltip, pageX, pageY);
    };

    const legendHeight = isMultiSource ? 18 : 0;
    const legendGap = isMultiSource ? 18 : 0;
    const margin = { top: 24 + legendHeight + legendGap, right: 60, bottom: 36, left: 56 };
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

    // Legend (multi-source only) — source swatches + dashed total line marker.
    if (isMultiSource) {
      const legend = svg.append('g')
        .attr('transform', `translate(${margin.left}, ${margin.top - legendHeight - legendGap})`);
      let cursor = 0;
      orderedSourceIds.forEach((id) => {
        const label = sourceLabel(id, ecosystem?.sources);
        const color = pickSourceColor(id, sourceOrder, ecosystem?.sources);
        legend.append('rect')
          .attr('x', cursor)
          .attr('y', 2)
          .attr('width', 10)
          .attr('height', 10)
          .attr('fill', color);
        const text = legend.append('text')
          .attr('x', cursor + 14)
          .attr('y', 11)
          .style('font-size', '11px')
          .style('fill', 'var(--chart-text)')
          .text(label);
        cursor += 14 + text.node().getComputedTextLength() + 16;
      });
      // Total line marker
      legend.append('line')
        .attr('x1', cursor)
        .attr('x2', cursor + 18)
        .attr('y1', 7)
        .attr('y2', 7)
        .attr('stroke', TOTAL_LINE_COLOR)
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '4 3');
      legend.append('text')
        .attr('x', cursor + 22)
        .attr('y', 11)
        .style('font-size', '11px')
        .style('fill', 'var(--chart-text)')
        .text('Cumulative total');
    }

    // Left axis (new proposals per year).
    g.append('g')
      .call(d3.axisLeft(yBars).ticks(6))
      .call((axis) => axis.select('.domain').attr('stroke', isMultiSource ? '#888' : '#4c78a8'))
      .call((axis) => axis.selectAll('line').attr('stroke', '#d7dee8'))
      .call((axis) => axis.selectAll('text').attr('fill', isMultiSource ? '#555' : '#4c78a8'));

    // Right axis (cumulative).
    g.append('g')
      .attr('transform', `translate(${innerWidth},0)`)
      .call(d3.axisRight(yLine).ticks(6))
      .call((axis) => axis.select('.domain').attr('stroke', TOTAL_LINE_COLOR))
      .call((axis) => axis.selectAll('text').attr('fill', TOTAL_LINE_COLOR));

    const everyOtherYear = series.filter((_, i) => i % 2 === 0).map((d) => d.year);
    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).tickValues(everyOtherYear))
      .selectAll('text')
      .style('font-size', '13px');

    // Compute stacked segments per source (always — for single source this collapses
    // to one segment per bar with the legacy color).
    const stacks = series.flatMap((entry) => {
      if (!hasSourceBreakdown) {
        return [{
          year: entry.year,
          sourceId: '',
          value: entry.count,
          y0: 0,
          y1: entry.count,
          entry,
        }];
      }
      let y0 = 0;
      return orderedSourceIds
        .map((id) => {
          const value = entry.bySource[id] || 0;
          const segment = { year: entry.year, sourceId: id, value, y0, y1: y0 + value, entry };
          y0 += value;
          return segment;
        })
        .filter((segment) => segment.value > 0);
    });

    const baseBarColor = (sourceId) => (sourceId
      ? pickSourceColor(sourceId, sourceOrder, ecosystem?.sources)
      : '#4c78a8');

    const resetBarStyles = () => {
      g.selectAll('rect.stack-segment')
        .attr('opacity', 1)
        .attr('fill', (d) => baseBarColor(d.sourceId));
    };

    const resetPointStyles = () => {
      g.selectAll('circle.timeline-point')
        .attr('r', 4);
    };

    g.selectAll('rect.stack-segment')
      .data(stacks)
      .enter()
      .append('rect')
      .attr('class', 'stack-segment')
      .attr('x', (d) => x(d.year))
      .attr('y', (d) => yBars(d.y1))
      .attr('width', x.bandwidth())
      .attr('height', (d) => yBars(d.y0) - yBars(d.y1))
      .attr('fill', (d) => baseBarColor(d.sourceId))
      .on('mouseover', function (event, d) {
        if (pinnedYear) return;
        d3.select(this).attr('opacity', 0.75);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(d.entry));
      })
      .on('mousemove', function (event) {
        if (pinnedYear) return;
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedYear) return;
        d3.select(this).attr('opacity', 1);
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, d) {
        event.stopPropagation();
        pinnedYear = d.year;
        resetBarStyles();
        resetPointStyles();
        g.selectAll('rect.stack-segment')
          .filter((seg) => seg.year === d.year)
          .attr('opacity', 0.85);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(d.entry));
        setTooltipPosition(event.pageX, event.pageY);
      });

    // Total per-year label above each bar.
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

    // Per-source cumulative lines (only meaningful when multi-source).
    if (isMultiSource) {
      orderedSourceIds.forEach((id) => {
        const line = d3.line()
          .x((d) => x(d.year) + x.bandwidth() / 2)
          .y((d) => yLine(d.cumulativeBySource[id] || 0))
          .curve(d3.curveMonotoneX);
        g.append('path')
          .datum(series)
          .attr('fill', 'none')
          .attr('stroke', pickSourceColor(id, sourceOrder, ecosystem?.sources))
          .attr('stroke-width', 2)
          .attr('opacity', 0.85)
          .attr('d', line);
      });
    }

    // Total cumulative line — dashed in multi-source, solid (single-line) in single-source.
    const totalLine = d3.line()
      .x((d) => x(d.year) + x.bandwidth() / 2)
      .y((d) => yLine(d.cumulative))
      .curve(d3.curveMonotoneX);
    g.append('path')
      .datum(series)
      .attr('fill', 'none')
      .attr('stroke', TOTAL_LINE_COLOR)
      .attr('stroke-width', 2.5)
      .attr('stroke-dasharray', isMultiSource ? '4 3' : null)
      .attr('d', totalLine);

    g.selectAll('circle.timeline-point')
      .data(series)
      .enter()
      .append('circle')
      .attr('class', 'timeline-point')
      .attr('cx', (d) => x(d.year) + x.bandwidth() / 2)
      .attr('cy', (d) => yLine(d.cumulative))
      .attr('r', 4)
      .attr('fill', TOTAL_LINE_COLOR)
      .attr('stroke', 'var(--chart-contrast)')
      .attr('stroke-width', 1.5)
      .on('mouseover', function (event, d) {
        if (pinnedYear) return;
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(d));
      })
      .on('mousemove', function (event) {
        if (pinnedYear) return;
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedYear) return;
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, d) {
        event.stopPropagation();
        pinnedYear = d.year;
        resetBarStyles();
        resetPointStyles();
        d3.select(this).attr('r', 5.5);
        g.selectAll('rect.stack-segment')
          .filter((seg) => seg.year === d.year)
          .attr('opacity', 0.85);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(d));
        setTooltipPosition(event.pageX, event.pageY);
      });

    // Axis labels (only shown in single-source mode; in multi-source the legend covers it).
    if (!isMultiSource) {
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
        .attr('fill', TOTAL_LINE_COLOR)
        .style('font-size', '12px')
        .text('Cumulative total');
    }

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
