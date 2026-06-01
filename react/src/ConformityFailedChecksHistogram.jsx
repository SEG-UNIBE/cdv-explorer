import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { renderProposalListHtml } from './bipTooltipContent';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';

function truncateTextToWidth(text, maxWidth, measurer) {
  const value = String(text || '');
  measurer.text(value);

  if (measurer.node().getComputedTextLength() <= maxWidth) {
    return value;
  }

  let truncated = value;
  while (truncated.length > 1) {
    truncated = truncated.slice(0, -1);
    measurer.text(`${truncated}…`);
    if (measurer.node().getComputedTextLength() <= maxWidth) {
      return `${truncated}…`;
    }
  }

  return '';
}

export const ConformityFailedChecksHistogram = ({
  data,
  proposalShortLabel = 'BIP',
  width = 620,
  height = 360,
  barColor = '#e45756',
  barHoverColor = '#b63f3e',
  ariaLabel = 'Failed conformity checks histogram',
}) => {
  const ref = useRef();
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    const series = Array.isArray(data) ? data.filter((entry) => Number(entry?.count) > 0) : [];

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    if (!series.length) {
      svg.append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .style('font-size', '14px')
        .style('fill', 'var(--app-text-muted)')
        .text('No failed checks in the selected snapshot.');
      return;
    }

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'conformity-failed-checks-tooltip')
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
    let pinnedCheckId = null;

    const margin = { top: 16, right: 24, bottom: 36, left: 56 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleLinear()
      .domain([0, d3.max(series, (entry) => entry.count) || 0])
      .nice()
      .range([0, innerWidth]);

    const y = d3.scaleBand()
      .domain(series.map((entry) => entry.label))
      .range([0, innerHeight])
      .padding(0.22);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    g.append('g')
      .call(d3.axisLeft(y).tickSize(0).tickFormat(() => ''))
      .call((axis) => axis.select('.domain').remove());

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(d3.format('d')))
      .call((axis) => axis.selectAll('line').attr('stroke', 'var(--chart-grid)'))
      .call((axis) => axis.selectAll('text')
        .style('font-size', '12px')
        .style('fill', 'var(--chart-text)'))
      .call((axis) => axis.select('.domain').attr('stroke', 'var(--chart-grid)'));

    g.append('g')
      .call(d3.axisTop(x).ticks(5).tickSize(-innerHeight).tickFormat(''))
      .call((axis) => axis.select('.domain').remove())
      .call((axis) => axis.selectAll('line').attr('stroke', 'var(--chart-grid)').attr('stroke-opacity', 0.45));

    const labelMeasurer = svg.append('text')
      .style('font-size', '11px')
      .style('font-weight', '600')
      .style('visibility', 'hidden')
      .style('pointer-events', 'none');

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const renderTooltipHtml = (entry) => (
      `<strong>${entry.label}</strong><br/>` +
      `Failed in ${entry.count} ${proposalShortLabel}${entry.count === 1 ? '' : 's'}<br/>` +
      renderProposalListHtml(entry.proposals, snapshotLabel, { ecosystem, label: 'Affected:', linkMode })
    );

    const resetBarStyles = () => {
      g.selectAll('rect')
        .attr('fill', (entry) => (pinnedCheckId === entry.id ? barHoverColor : barColor));
    };

    g.selectAll('rect')
      .data(series)
      .enter()
      .append('rect')
      .attr('x', 0)
      .attr('y', (entry) => y(entry.label))
      .attr('width', (entry) => x(entry.count))
      .attr('height', y.bandwidth())
      .attr('rx', 5)
      .attr('fill', barColor)
      .on('mouseover', function onMouseOver(event, entry) {
        if (pinnedCheckId) {
          return;
        }
        d3.select(this).attr('fill', barHoverColor);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(entry));
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mousemove', function onMouseMove(event) {
        if (pinnedCheckId) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function onMouseOut() {
        if (pinnedCheckId) {
          return;
        }
        d3.select(this).attr('fill', barColor);
        tooltip.style('opacity', 0);
      })
      .on('click', function onClick(event, entry) {
        event.stopPropagation();
        pinnedCheckId = entry.id;
        resetBarStyles();
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(entry));
        setTooltipPosition(event.pageX, event.pageY);
      });

    const clipGroup = g.append('defs');
    clipGroup.selectAll('clipPath')
      .data(series)
      .enter()
      .append('clipPath')
      .attr('id', (entry) => `failed-check-label-${ariaLabel.replace(/\s+/g, '-').toLowerCase()}-${entry.id}`)
      .append('rect')
      .attr('x', 8)
      .attr('y', (entry) => y(entry.label) + 2)
      .attr('width', (entry) => Math.max(0, x(entry.count) - 16))
      .attr('height', Math.max(0, y.bandwidth() - 4));

    g.selectAll('text.label')
      .data(series)
      .enter()
      .append('text')
      .attr('class', 'label')
      .attr('x', 10)
      .attr('y', (entry) => (y(entry.label) || 0) + (y.bandwidth() / 2))
      .attr('dominant-baseline', 'middle')
      .attr('clip-path', (entry) => `url(#failed-check-label-${ariaLabel.replace(/\s+/g, '-').toLowerCase()}-${entry.id})`)
      .style('font-size', '11px')
      .style('font-weight', '600')
      .style('fill', '#ffffff')
      .style('pointer-events', 'none')
      .style('user-select', 'none')
      .text((entry) => truncateTextToWidth(entry.label, Math.max(0, x(entry.count) - 20), labelMeasurer));

    g.selectAll('text.value')
      .data(series)
      .enter()
      .append('text')
      .attr('class', 'value')
      .attr('x', -10)
      .attr('y', (entry) => (y(entry.label) || 0) + (y.bandwidth() / 2))
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'middle')
      .style('font-size', '12px')
      .style('font-weight', '600')
      .style('fill', 'var(--chart-text)')
      .style('pointer-events', 'none')
      .style('user-select', 'none')
      .text((entry) => entry.count);

    svg.on('click', () => {
      pinnedCheckId = null;
      resetBarStyles();
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
    });

    return () => {
      svg.selectAll('*').remove();
      labelMeasurer.remove();
      tooltip.remove();
    };
  }, [ariaLabel, barColor, barHoverColor, data, ecosystem, height, linkMode, proposalShortLabel, snapshotLabel, width]);

  return <svg ref={ref} role="img" aria-label={ariaLabel} />;
};
