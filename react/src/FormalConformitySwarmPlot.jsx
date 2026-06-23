import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { formatProposalReference, getProposalUrl, normalizeProposalId } from './proposalLinks';
import { renderTooltipCardHtml } from './tooltipHtml';


function getStandardScore(entry, key) {
  // standard_scores is the canonical location for any ecosystem standard
  const standardScore = entry?.standard_scores?.[key];
  if (standardScore != null && Number.isFinite(Number(standardScore))) {
    return Number(standardScore);
  }
  // backward compat: direct field e.g. bip2_score, bip3_score
  const direct = entry?.[`${key}_score`];
  if (direct != null && Number.isFinite(Number(direct))) {
    return Number(direct);
  }
  return null;
}

function formatScore(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 'n/a';
  }
  return numeric.toFixed(2).replace(/\.?0+$/, '');
}

function renderChecksHtml(checks = []) {
  const failedChecks = Array.isArray(checks)
    ? checks.filter((check) => check?.passed === false)
    : [];

  if (failedChecks.length === 0) {
    return '<strong style="display:block; margin-top:0.35rem;">All checks passed</strong>';
  }

  const items = failedChecks
    .map((check) => {
      const details = String(check?.details || '').trim();
      const detailSuffix = details ? `: ${details}` : '';
      return `<li>${check?.label || check?.id || 'Unnamed check'}${detailSuffix}</li>`;
    })
    .join('');

  return `<ul style="margin:0.35rem 0 0; padding-left:1.1rem;">${items}</ul>`;
}

export const FormalConformitySwarmPlot = ({
  rows,
  highlightProposal = '',
  standardKey = null,
  width = 1200,
  height = 520,
}) => {
  const ref = useRef();
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    const baseRows = (rows || []).map((entry) => ({
      ...entry,
      id: String(entry.id),
    }));

    const activePanelDefinitions = standardKey
      ? [{ key: standardKey, label: `${standardKey.toUpperCase()} conformity` }]
      : [];

    const panels = activePanelDefinitions
      .map((panel) => ({
        ...panel,
        rows: baseRows
          .map((entry) => ({ ...entry, score: getStandardScore(entry, panel.key) }))
          .filter((entry) => entry.score !== null),
      }))
      .filter((panel) => panel.rows.length > 0);

    if (!panels.length) {
      return;
    }

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'formal-conformity-tooltip')
      .style('position', 'absolute')
      .style('background', 'var(--tooltip-bg)')
      .style('color', 'var(--tooltip-text)')
      .style('padding', '8px 12px')
      .style('border-radius', '6px')
      .style('border', '1px solid var(--tooltip-border)')
      .style('box-shadow', 'var(--tooltip-shadow)')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('max-width', '320px')
      .style('max-height', '360px')
      .style('overflow-y', 'auto')
      .style('line-height', '1.45')
      .style('opacity', 0);

    const highlightedProposalId = normalizeProposalId(highlightProposal, ecosystem);
    let pinnedBubbleKey = null;
    const showPanelLabel = panels.length > 1;
    const axisTickValues = [0, 20, 40, 60, 80, 100];
    const radius = 7;
    const panelGap = 54;
    const margin = { top: 20, right: 24, bottom: 54, left: 24 };
    const innerWidth = width - margin.left - margin.right;
    const availableHeight = height - margin.top - margin.bottom - (panelGap * (panels.length - 1));
    const panelHeight = availableHeight / panels.length;
    const x = d3.scaleLinear()
      .domain([0, 110])
      .range([0, innerWidth]);

    const color = d3.scaleLinear()
      .domain([0, 50, 100])
      .range(['#d94841', '#f59e0b', '#2f9e44']);

    const root = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const applyBaseBubbleStyles = () => {
      root.selectAll('circle.formal-conformity-bubble')
        .attr('stroke', function (entry) {
          const normalizedId = normalizeProposalId(entry.id, ecosystem);
          const bubbleKey = `${entry.panelKey}:${entry.id}`;
          if (pinnedBubbleKey && pinnedBubbleKey === bubbleKey) {
            return 'var(--chart-focus)';
          }
          return highlightedProposalId && normalizedId === highlightedProposalId ? 'var(--chart-focus)' : 'var(--chart-contrast)';
        })
        .attr('stroke-width', function (entry) {
          const normalizedId = normalizeProposalId(entry.id, ecosystem);
          const bubbleKey = `${entry.panelKey}:${entry.id}`;
          if (pinnedBubbleKey && pinnedBubbleKey === bubbleKey) {
            return 2;
          }
          return highlightedProposalId && normalizedId === highlightedProposalId ? 2 : 1.25;
        })
        .attr('r', function (entry) {
          const normalizedId = normalizeProposalId(entry.id, ecosystem);
          const bubbleKey = `${entry.panelKey}:${entry.id}`;
          if (pinnedBubbleKey && pinnedBubbleKey === bubbleKey) {
            return radius + 1.5;
          }
          return highlightedProposalId && normalizedId === highlightedProposalId ? radius + 1.5 : radius;
        })
        .attr('fill-opacity', function (entry) {
          const normalizedId = normalizeProposalId(entry.id, ecosystem);
          const bubbleKey = `${entry.panelKey}:${entry.id}`;
          if (pinnedBubbleKey) {
            return pinnedBubbleKey === bubbleKey ? 0.96 : 0.18;
          }
          if (!highlightedProposalId) {
            return 0.88;
          }
          return normalizedId === highlightedProposalId ? 0.96 : 0.22;
        });
    };

    panels.forEach((panel, panelIndex) => {
      const panelRoot = root.append('g')
        .attr('transform', `translate(0, ${(panelHeight + panelGap) * panelIndex})`);
      const baselineY = panelHeight / 2;

      if (showPanelLabel) {
        panelRoot.append('text')
          .attr('x', 0)
          .attr('y', -4)
          .style('fill', 'var(--chart-text)')
          .style('font-size', '14px')
          .style('font-weight', '400')
          .text(panel.label);
      }

      panelRoot.append('line')
        .attr('x1', 0)
        .attr('x2', innerWidth)
        .attr('y1', baselineY)
        .attr('y2', baselineY)
        .attr('stroke', 'var(--chart-grid)')
        .attr('stroke-width', 1.25);

      const bees = panel.rows.map((entry) => ({
        ...entry,
        panelKey: panel.key,
        panelLabel: panel.label,
        x: x(entry.score),
        y: baselineY,
      }));

      const simulation = d3.forceSimulation(bees)
        .force('x', d3.forceX((entry) => x(entry.score)).strength(1))
        .force('y', d3.forceY(baselineY).strength(0.07))
        .force('collide', d3.forceCollide(radius + 1.25))
        .stop();

      for (let tick = 0; tick < 220; tick += 1) {
        simulation.tick();
      }

      const renderTooltipHtml = (entry) => (
        (() => {
          const complianceDetails = entry?.formal_compliance || {};
          const panelCompliance = complianceDetails?.[panel.key] || {};
          const checks = panelCompliance.checks || [];
          return renderTooltipCardHtml({
            titleHtml: `<strong><a href="${getProposalUrl(entry.id, snapshotLabel, { linkMode }, ecosystem)}" target="_blank" rel="noreferrer">${formatProposalReference(entry.id, ecosystem)}</a></strong>`,
            rows: [
              [entry.panelLabel, formatScore(entry.score)],
              ['Status', entry.status || 'Unknown'],
              ['Passed', panelCompliance.passed_checks ?? 0],
              ['Failed', panelCompliance.failed_checks ?? 0],
              ['Skipped', panelCompliance.skipped_checks ?? 0],
            ],
            bodyHtml: (
              panelCompliance.failed_checks
                ? '<strong class="tooltip-card__section-label">Failed checks</strong>'
                : ''
            ) + renderChecksHtml(checks),
          });
        })()
      );

      panelRoot.append('g')
        .selectAll('circle')
        .data(bees)
        .enter()
        .append('circle')
        .attr('class', 'formal-conformity-bubble')
        .attr('cx', (entry) => entry.x)
        .attr('cy', (entry) => entry.y)
        .attr('r', radius)
        .attr('fill', (entry) => color(entry.score))
        .attr('fill-opacity', 0.88)
        .attr('stroke', 'var(--chart-contrast)')
        .attr('stroke-width', 1.25)
        .on('mouseover', function (event, entry) {
          if (pinnedBubbleKey) {
            return;
          }

          d3.select(this)
            .attr('fill-opacity', 0.96)
            .attr('stroke', 'var(--chart-focus)')
            .attr('stroke-width', 2)
            .attr('r', radius + 1.5);

          tooltip
            .style('opacity', 1)
            .style('pointer-events', 'none')
            .html(renderTooltipHtml(entry));
          setTooltipPosition(event.pageX, event.pageY);
        })
        .on('mousemove', function (event) {
          if (pinnedBubbleKey) {
            return;
          }
          setTooltipPosition(event.pageX, event.pageY);
        })
        .on('mouseout', function () {
          if (pinnedBubbleKey) {
            return;
          }
          applyBaseBubbleStyles();
          tooltip.style('opacity', 0);
        })
        .on('click', function (event, entry) {
          event.stopPropagation();
          pinnedBubbleKey = `${entry.panelKey}:${entry.id}`;
          applyBaseBubbleStyles();
          tooltip
            .style('opacity', 1)
            .style('pointer-events', 'auto')
            .html(renderTooltipHtml(entry));
          setTooltipPosition(event.pageX, event.pageY);
        });

      if (panelIndex === panels.length - 1) {
        panelRoot.append('g')
          .attr('transform', `translate(0,${panelHeight})`)
          .call(d3.axisBottom(x).tickValues(axisTickValues))
          .call((axis) => axis.selectAll('line').attr('stroke', 'var(--chart-grid)'))
          .call((axis) => axis.select('.domain').attr('stroke', 'var(--chart-axis)'));

        panelRoot.append('text')
          .attr('x', innerWidth / 2)
          .attr('y', panelHeight + 42)
          .attr('text-anchor', 'middle')
          .style('fill', 'var(--chart-muted)')
          .style('font-size', '12px')
          .style('font-weight', '600')
          .text('Conformity score');
      }

      simulation.stop();
    });

    applyBaseBubbleStyles();

    svg.on('click', () => {
      pinnedBubbleKey = null;
      applyBaseBubbleStyles();
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
    });

    return () => {
      svg.selectAll('*').remove();
      tooltip.remove();
    };
  }, [ecosystem, height, highlightProposal, linkMode, rows, snapshotLabel, standardKey, width]);

  return <svg ref={ref} role="img" aria-label="Formal conformity beeswarm plot" />;
};
