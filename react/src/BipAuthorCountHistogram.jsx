import * as d3 from 'd3';
import { positionTooltip } from './tooltipPosition';
import { useEffect, useRef } from 'react';
import { renderProposalListRow } from './bipTooltipContent';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { renderTooltipCardHtml } from './tooltipHtml';

const BAR_COLOR = '#7048e8';
const BAR_HOVER_COLOR = '#5f3dc4';

export const BipAuthorCountHistogram = ({ data, width = 600, height = 400 }) => {
  const ref = useRef();
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    if (!Array.isArray(data) || data.length === 0) return;

    const sparseSeries = data
      .map((e) => ({ authorCount: Number(e.authorCount || 0), bipCount: Number(e.bipCount || 0), bips: e.bips || [] }))
      .filter((e) => e.authorCount > 0)
      .sort((a, b) => a.authorCount - b.authorCount);

    if (sparseSeries.length === 0) return;

    // Build display items: one slot per real data point + one '…' slot per gap ≥ 3
    const displayItems = [];
    let ellipsisIdx = 0;
    sparseSeries.forEach((entry, i) => {
      if (i > 0 && entry.authorCount - sparseSeries[i - 1].authorCount >= 3) {
        displayItems.push({ key: `…_${ellipsisIdx++}`, isEllipsis: true, authorCount: null, bipCount: 0 });
      }
      displayItems.push({ key: String(entry.authorCount), isEllipsis: false, authorCount: entry.authorCount, bipCount: entry.bipCount, bips: entry.bips });
    });

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'bip-author-count-tooltip')
      .style('position', 'absolute')
      .style('background', 'var(--tooltip-bg)')
      .style('color', 'var(--tooltip-text)')
      .style('padding', '8px 12px')
      .style('border-radius', '6px')
      .style('border', '1px solid var(--tooltip-border)')
      .style('box-shadow', 'var(--tooltip-shadow)')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('max-width', '360px')
      .style('line-height', '1.45')
      .style('opacity', 0);
    let pinnedAuthorCount = null;

    const margin = { top: 20, right: 24, bottom: 58, left: 68 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleBand()
      .domain(displayItems.map((d) => d.key))
      .range([0, innerWidth])
      .padding(0.18);

    const y = d3.scaleLinear()
      .domain([0, d3.max(displayItems, (d) => d.bipCount) || 0])
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
      .call((axis) => axis.selectAll('text').style('font-size', '13px'));

    const setTooltipPosition = (pageX, pageY) => {
      positionTooltip(tooltip, pageX, pageY);
    };

    const renderTooltipHtml = (e) => {
      const authorLabel = e.authorCount === 1 ? 'single authors' : e.authorCount === 2 ? 'two authors' : e.authorCount === 3 ? 'three authors' : `${e.authorCount} authors`;
      return renderTooltipCardHtml({
        titleHtml: `<strong>${e.bipCount}</strong> proposal${e.bipCount === 1 ? '' : 's'}`,
        rows: [
          ['Author Count', authorLabel],
          renderProposalListRow(e.bips, snapshotLabel, { ecosystem, linkMode }),
        ],
      });
    };

    svg.on('click', () => {
      pinnedAuthorCount = null;
      g.selectAll('rect').attr('fill', BAR_COLOR);
      tooltip.style('opacity', 0).style('pointer-events', 'none');
    });

    g.selectAll('rect')
      .data(displayItems.filter((d) => !d.isEllipsis))
      .enter()
      .append('rect')
      .attr('x', (d) => x(d.key))
      .attr('y', (d) => y(d.bipCount))
      .attr('width', x.bandwidth())
      .attr('height', (d) => innerHeight - y(d.bipCount))
      .attr('rx', 4)
      .attr('fill', BAR_COLOR)
      .on('mouseover', function (event, e) {
        if (pinnedAuthorCount != null) return;
        d3.select(this).attr('fill', BAR_HOVER_COLOR);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(e));
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mousemove', function (event) {
        if (pinnedAuthorCount != null) return;
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedAuthorCount != null) return;
        d3.select(this).attr('fill', BAR_COLOR);
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, e) {
        event.stopPropagation();
        pinnedAuthorCount = e.authorCount;
        g.selectAll('rect').attr('fill', (d) => (d.authorCount === pinnedAuthorCount ? BAR_HOVER_COLOR : BAR_COLOR));
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(e));
        setTooltipPosition(event.pageX, event.pageY);
      });

    g.selectAll('text.bar-label')
      .data(displayItems.filter((d) => !d.isEllipsis && d.bipCount > 0))
      .enter()
      .append('text')
      .attr('class', 'bar-label')
      .attr('x', (d) => x(d.key) + x.bandwidth() / 2)
      .attr('y', (d) => y(d.bipCount) - 6)
      .attr('text-anchor', 'middle')
      .style('font-size', '12px')
      .style('fill', 'var(--chart-text)')
      .text((d) => d.bipCount);

    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 44)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .text('Number of authors per proposal');

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -48)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .text('Number of proposals');

    return () => {
      svg.selectAll('*').remove();
      tooltip.remove();
    };
  }, [data, ecosystem, width, height, snapshotLabel, linkMode]);

  return <svg ref={ref} role="img" aria-label="Authors per proposal histogram" />;
};
