import * as d3 from 'd3';
import { useEffect, useRef, useState } from 'react';
import { renderProposalListHtml } from './bipTooltipContent';
import { getClassificationColorMap } from './classificationColors';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';

const BIP2_STATUS_ORDER = [
  'Draft',
  'Active',
  'Proposed',
  'Deferred',
  'Rejected',
  'Withdrawn',
  'Final',
  'Replaced',
  'Obsolete',
];

const BIP3_STATUS_ORDER = [
  'Draft',
  'Complete',
  'Deployed',
  'Closed',
];

export function EvolutionStatusStackedBarChart({
  data,
  title = 'Status Evolution',
  mode = 'absolute',
  width = 1200,
  height = 340,
}) {
  const ref = useRef();
  const [containerWidth, setContainerWidth] = useState(width);
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

  useEffect(() => {
    const svgNode = ref.current;
    const container = svgNode?.parentElement;
    if (!container) {
      return undefined;
    }

    const updateWidth = () => {
      const nextWidth = Math.max(720, Math.floor(container.clientWidth || width));
      setContainerWidth((currentWidth) => (currentWidth === nextWidth ? currentWidth : nextWidth));
    };

    updateWidth();

    const observer = new ResizeObserver(updateWidth);
    observer.observe(container);

    return () => {
      observer.disconnect();
    };
  }, [width]);

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    const segmentDefinitions = Array.isArray(data?.segmentDefinitions) && data.segmentDefinitions.length
      ? data.segmentDefinitions
      : (Array.isArray(data?.categories) ? data.categories : []).map((category) => ({
        key: category,
        status: category,
        standard: null,
        label: category,
      }));
    const categories = segmentDefinitions.map((segment) => segment.key);
    const segmentByKey = new Map(segmentDefinitions.map((segment) => [segment.key, segment]));
    const rawRows = Array.isArray(data?.rows) ? data.rows : [];
    const formatPeriodDisplayLabel = (row) => {
      const baseLabel = String(row?.periodLabel || '');
      if (!baseLabel) {
        return '';
      }
      if (String(row?.periodKey || '').endsWith('-pre-bip3')) {
        return `${baseLabel}a`;
      }
      if (String(row?.periodKey || '').endsWith('-post-bip3')) {
        return `${baseLabel}b`;
      }
      return baseLabel;
    };
    const formatMilestoneLabel = (label) => {
      if (String(label || '').trim() === 'BIP3 Activation') {
        return 'BIP-3 activation';
      }
      return String(label || '');
    };
    if (!categories.length || !rawRows.length) {
      return;
    }

    const rows = rawRows
      .map((row, index) => ({
        periodKey: String(row?.period_key || row?.period || row?.year || ''),
        periodLabel: String(row?.period || row?.year || ''),
        periodStart: String(row?.period_start || ''),
        periodEnd: String(row?.period_end || ''),
        periodKind: String(row?.period_kind || 'quarter'),
        milestoneLabel: String(row?.milestone_label || ''),
        values: row?.values || {},
        bips: row?.bips || {},
        index,
      }))
      .map((row) => ({
        ...row,
        displayLabel: formatPeriodDisplayLabel(row),
      }))
      .filter((row) => row.periodKey);

    rows.sort((left, right) => {
      if (left.periodEnd && right.periodEnd && left.periodEnd !== right.periodEnd) {
        return left.periodEnd.localeCompare(right.periodEnd);
      }
      return left.index - right.index;
    });

    if (!rows.length) {
      return;
    }

    svg
      .attr('viewBox', `0 0 ${containerWidth} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltipNode = document.createElement('div');
    document.body.appendChild(tooltipNode);

    const tooltip = d3.select(tooltipNode)
      .attr('class', 'classification-timeline-tooltip')
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
    let pinnedSegmentKey = null;
    let hoveredLegendKey = null;

    const margin = { top: 24, right: 140, bottom: 52, left: 50 };
    const innerWidth = containerWidth - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const periods = rows.map((row) => row.periodKey);
    const xDomain = [];
    const gapKeyByPeriod = new Map();
    rows.forEach((row, index) => {
      xDomain.push(row.periodKey);
      if (row.periodKind === 'milestone' && index < rows.length - 1) {
        const gapKey = `${row.periodKey}__gap`;
        xDomain.push(gapKey);
        gapKeyByPeriod.set(row.periodKey, gapKey);
      }
    });
    const colorMap = getClassificationColorMap(
      'status',
      Array.from(new Set(segmentDefinitions.map((segment) => segment.status)))
    );
    const chartId = String(title).toLowerCase().replace(/[^a-z0-9]+/g, '-');

    const normalizedRows = rows.map((row) => {
      const total = categories.reduce((sum, category) => sum + Number(row.values?.[category] || 0), 0);
      const normalized = {
        period: row.periodLabel,
        periodDisplay: row.displayLabel,
        periodKey: row.periodKey,
        periodStart: row.periodStart,
        periodEnd: row.periodEnd,
        periodKind: row.periodKind,
        milestoneLabel: row.milestoneLabel,
        bips: row.bips,
      };
      categories.forEach((category) => {
        const rawValue = Number(row.values?.[category] || 0);
        normalized[category] = mode === 'relative' && total > 0 ? rawValue / total : rawValue;
        normalized[`${category}__raw`] = rawValue;
        normalized[`${category}__share`] = total > 0 ? rawValue / total : 0;
      });
      normalized.__total = total;
      return normalized;
    });
    const totalsBySegment = Object.fromEntries(
      categories.map((category) => [
        category,
        rows.reduce((sum, row) => sum + Number(row.values?.[category] || 0), 0),
      ])
    );
    const visibleSegments = segmentDefinitions.filter((segment) => (totalsBySegment[segment.key] || 0) > 0);
    const orderLegendSegments = (segments, preferredStatusOrder) => {
      const statusRank = new Map(preferredStatusOrder.map((status, index) => [status, index]));
      return [...segments].sort((left, right) => {
        const leftRank = statusRank.has(left.status) ? statusRank.get(left.status) : Number.MAX_SAFE_INTEGER;
        const rightRank = statusRank.has(right.status) ? statusRank.get(right.status) : Number.MAX_SAFE_INTEGER;

        if (leftRank !== rightRank) {
          return leftRank - rightRank;
        }

        if (left.status !== right.status) {
          return left.status.localeCompare(right.status);
        }

        return left.key.localeCompare(right.key);
      });
    };
    const hasExplicitStandards = visibleSegments.some((segment) => segment.standard === 'bip2' || segment.standard === 'bip3');
    const bip2LegendSegments = hasExplicitStandards
      ? orderLegendSegments(
        visibleSegments.filter((segment) => segment.standard === 'bip2'),
        BIP2_STATUS_ORDER,
      )
      : orderLegendSegments(
        visibleSegments.filter((segment) => BIP2_STATUS_ORDER.includes(segment.status)),
        BIP2_STATUS_ORDER,
      );
    const bip3LegendSegments = hasExplicitStandards
      ? orderLegendSegments(
        visibleSegments.filter((segment) => segment.standard === 'bip3'),
        BIP3_STATUS_ORDER,
      )
      : orderLegendSegments(
        visibleSegments.filter((segment) => BIP3_STATUS_ORDER.includes(segment.status)),
        BIP3_STATUS_ORDER,
      );
    const rowByPeriod = new Map(rows.map((row) => [row.periodKey, row]));

    const x = d3.scaleBand()
      .domain(xDomain)
      .range([0, innerWidth])
      .padding(0.18);

    const stack = d3.stack().keys(categories);
    const layers = stack(normalizedRows);
    const y = d3.scaleLinear()
      .domain([0, d3.max(normalizedRows, (row) => categories.reduce((sum, category) => sum + Number(row[category] || 0), 0)) || 0])
      .nice()
      .range([innerHeight, 0]);

    const tickValues = periods.filter((period, index) => {
      const row = rowByPeriod.get(period);
      if (index === 0 || index === periods.length - 1) {
        return true;
      }
      if (row?.periodKind === 'milestone' || row?.periodKind === 'milestone_remainder') {
        return true;
      }
      if (periods.length > 40) {
        return period.endsWith('Q1');
      }
      return index % 2 === 0;
    });

    const root = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    root.append('g')
      .call(
        d3.axisLeft(y)
          .ticks(5)
          .tickFormat(mode === 'relative' ? (value) => `${Math.round(Number(value) * 100)}%` : undefined)
      )
      .call((axis) => axis.selectAll('line').attr('stroke', 'var(--chart-grid)'));

    root.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(
        d3.axisBottom(x)
          .tickValues(tickValues)
          .tickFormat((value) => rowByPeriod.get(String(value))?.displayLabel || String(value))
      )
      .selectAll('text')
      .attr('transform', 'rotate(-45)')
      .style('text-anchor', 'end');

    rows
      .filter((row) => row.periodKind === 'milestone')
      .forEach((row) => {
        const rowIndex = rows.findIndex((candidate) => candidate.periodKey === row.periodKey);
        const nextRow = rowIndex >= 0 ? rows[rowIndex + 1] : null;
        const currentX = x(row.periodKey);
        const gapKey = gapKeyByPeriod.get(row.periodKey);
        const gapX = gapKey ? x(gapKey) : undefined;
        const nextX = nextRow ? x(nextRow.periodKey) : undefined;

        if (currentX === undefined) {
          return;
        }

        const boundaryX = gapX !== undefined
          ? gapX + (x.bandwidth() / 2)
          : (nextX === undefined
            ? currentX + (x.bandwidth() / 2)
            : ((currentX + x.bandwidth()) + nextX) / 2);

        root.append('line')
          .attr('x1', boundaryX)
          .attr('x2', boundaryX)
          .attr('y1', 0)
          .attr('y2', innerHeight)
          .attr('stroke', 'var(--chart-focus)')
          .attr('stroke-dasharray', '4 4')
          .attr('stroke-width', 1)
          .attr('opacity', 0.75);

        if (row.milestoneLabel) {
          root.append('text')
            .attr('x', Math.max(0, boundaryX - 6))
            .attr('y', -8)
            .attr('text-anchor', 'end')
            .style('font-size', '11px')
            .style('font-style', 'italic')
            .style('font-weight', '400')
            .style('fill', 'var(--chart-text)')
            .text(formatMilestoneLabel(row.milestoneLabel));
        }
      });

    const legend = root.append('g')
      .attr('transform', `translate(${innerWidth + 20}, 0)`);

    let legendOffsetY = 0;

    const appendLegendSection = (titleText, segments) => {
      if (!segments.length) {
        return;
      }

      legend.append('text')
        .attr('x', 0)
        .attr('y', legendOffsetY + 10)
        .style('font-size', '13px')
        .style('font-weight', '600')
        .style('fill', 'var(--chart-text)')
        .text(titleText);

      legendOffsetY += 18;

      segments.forEach((segment) => {
        const row = legend.append('g')
          .attr('transform', `translate(0, ${legendOffsetY})`);
        row.append('rect')
          .attr('width', 12)
          .attr('height', 12)
          .attr('rx', 2)
          .attr('fill', colorMap[segment.status])
          .attr('stroke', d3.color(colorMap[segment.status]).darker(0.35))
          .attr('stroke-width', 0.7);

        row.append('text')
          .attr('x', 20)
          .attr('y', 10)
          .style('font-size', '13px')
          .style('fill', 'var(--chart-muted)')
          .text(segment.status);

        row
          .style('cursor', 'pointer')
          .on('mouseenter', () => {
            hoveredLegendKey = segment.key;
            applyBaseBarStyles();
          })
          .on('mouseleave', () => {
            hoveredLegendKey = null;
            applyBaseBarStyles();
          });

        legendOffsetY += 18;
      });

      legendOffsetY += 8;
    };

    appendLegendSection('BIP2', [...bip2LegendSegments].reverse());
    appendLegendSection('BIP3', [...bip3LegendSegments].reverse());

    const renderTooltipHtml = (segment) => {
      const bipList = Array.isArray(segment.data?.bips?.[segment.key])
        ? segment.data.bips[segment.key]
        : [];
      const dateRange = segment.data.periodStart && segment.data.periodEnd
        ? `Range: ${segment.data.periodStart} to ${segment.data.periodEnd}<br/>`
        : '';

      return (
        `<strong>${title}</strong><br/>` +
        `Period: ${segment.data.periodDisplay || segment.data.period}<br/>` +
        dateRange +
        `${segmentByKey.get(segment.key)?.standard ? `Standard: ${String(segmentByKey.get(segment.key)?.standard).toUpperCase()}<br/>` : ''}` +
        `Status: ${segmentByKey.get(segment.key)?.status || segment.key}<br/>` +
        `Count: ${segment.data[`${segment.key}__raw`]}<br/>` +
        `Share: ${Math.round((Number(segment.data[`${segment.key}__share`] || 0)) * 100)}%<br/>` +
        renderProposalListHtml(bipList, snapshotLabel, { ecosystem, linkMode })
      );
    };

    const applyBaseBarStyles = () => {
      root.selectAll('rect.evolution-bar-segment')
        .attr('opacity', (segment) => {
          const segmentKey = `${segment.data.periodKey}|||${segment.key}`;
          if (pinnedSegmentKey) {
            return pinnedSegmentKey !== segmentKey ? 0.22 : 1;
          }
          if (hoveredLegendKey) {
            return hoveredLegendKey !== segment.key ? 0.22 : 1;
          }
          return 1;
        })
        .attr('stroke', (segment) => (
          pinnedSegmentKey === `${segment.data.periodKey}|||${segment.key}` ? 'var(--chart-focus)' : 'none'
        ))
        .attr('stroke-width', (segment) => (
          pinnedSegmentKey === `${segment.data.periodKey}|||${segment.key}` ? 1.5 : 0
        ));
    };

    root.selectAll('g.evolution-bar-layer')
      .data(layers)
      .enter()
      .append('g')
      .attr('class', 'evolution-bar-layer')
      .attr('fill', (layer) => colorMap[segmentByKey.get(layer.key)?.status || layer.key])
      .selectAll('rect')
      .data((layer) => layer.map((segment) => ({ ...segment, key: layer.key })))
      .enter()
      .append('rect')
      .attr('class', 'evolution-bar-segment')
      .attr('x', (segment) => x(segment.data.periodKey))
      .attr('y', (segment) => y(segment[1]))
      .attr('width', x.bandwidth())
      .attr('height', (segment) => Math.max(0, y(segment[0]) - y(segment[1])))
      .on('mouseenter', function (event, segment) {
        if (pinnedSegmentKey) {
          return;
        }
        d3.select(this)
          .attr('stroke', 'var(--chart-focus)')
          .attr('stroke-width', 1.5);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(segment))
          .style('left', `${event.pageX + 10}px`)
          .style('top', `${event.pageY - 28}px`);
      })
      .on('mousemove', function (event) {
        if (pinnedSegmentKey) {
          return;
        }
        tooltip
          .style('left', `${event.pageX + 10}px`)
          .style('top', `${event.pageY - 28}px`);
      })
      .on('mouseleave', function () {
        if (pinnedSegmentKey) {
          return;
        }
        d3.select(this)
          .attr('stroke', 'none')
          .attr('stroke-width', 0);
        tooltip
          .style('opacity', 0)
          .style('pointer-events', 'none');
      })
      .on('click', function (event, segment) {
        event.stopPropagation();
        pinnedSegmentKey = `${segment.data.periodKey}|||${segment.key}`;
        applyBaseBarStyles();
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(segment))
          .style('left', `${event.pageX + 10}px`)
          .style('top', `${event.pageY - 28}px`);
      });

    applyBaseBarStyles();

    const clearPinnedState = () => {
      pinnedSegmentKey = null;
      hoveredLegendKey = null;
      applyBaseBarStyles();
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
    };

    svg.on('click', clearPinnedState);
    d3.select(document).on(`click.${chartId}`, clearPinnedState);

    return () => {
      d3.select(document).on(`click.${chartId}`, null);
      svg.selectAll('*').remove();
      tooltip.remove();
    };
  }, [containerWidth, data, ecosystem, height, linkMode, mode, snapshotLabel, title]);

  return <svg ref={ref} role="img" aria-label={`${title} stacked bar chart`} />;
}
