import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

function normalizeProposalId(value) {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }

  const match = text.match(/^(?:bip\s*[- ]*)?0*(\d+)$/i);
  return match ? String(Number(match[1])) : text;
}

function getProposalHref(id) {
  const text = String(id || '').trim();
  return text ? `https://bips.dev/${Number(text) || text}/` : '#';
}

function formatScore(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 'n/a';
  }
  return numeric.toFixed(2).replace(/\.?0+$/, '');
}

export const FormalConformitySwarmPlot = ({
  rows,
  proposalShortLabel = 'BIP',
  highlightProposal = '',
  width = 1200,
  height = 320,
}) => {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.formal-conformity-tooltip').remove();

    const data = (rows || [])
      .filter((entry) => Number.isFinite(Number(entry?.compliance_score)))
      .map((entry) => ({
        ...entry,
        id: String(entry.id),
        score: Number(entry.compliance_score),
        bip2Score: Number.isFinite(Number(entry?.bip2_score)) ? Number(entry.bip2_score) : null,
        bip3Score: Number.isFinite(Number(entry?.bip3_score)) ? Number(entry.bip3_score) : null,
      }));

    if (!data.length) {
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
      .style('background', '#1a1a1a')
      .style('color', '#fff')
      .style('padding', '8px 12px')
      .style('border-radius', '6px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('max-width', '320px')
      .style('line-height', '1.45')
      .style('opacity', 0);
    let pinnedProposalId = null;
    const highlightedProposalId = normalizeProposalId(highlightProposal);

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const margin = { top: 20, right: 24, bottom: 54, left: 24 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const centerY = innerHeight / 2;
    const radius = 8;

    const x = d3.scaleLinear()
      .domain([0, 100])
      .range([0, innerWidth]);

    const root = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    root.append('line')
      .attr('x1', 0)
      .attr('x2', innerWidth)
      .attr('y1', centerY)
      .attr('y2', centerY)
      .attr('stroke', '#d7dee8')
      .attr('stroke-width', 1.25);

    root.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).ticks(5))
      .call((axis) => axis.selectAll('line').attr('stroke', '#d7dee8'))
      .call((axis) => axis.select('.domain').attr('stroke', '#cbd5e1'));

    root.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 42)
      .attr('text-anchor', 'middle')
      .style('fill', '#475467')
      .style('font-size', '12px')
      .style('font-weight', '600')
      .text('Compliance score');

    const bees = data.map((entry) => ({
      ...entry,
      x: x(entry.score),
      y: centerY,
    }));

    const simulation = d3.forceSimulation(bees)
      .force('x', d3.forceX((entry) => x(entry.score)).strength(1))
      .force('y', d3.forceY(centerY).strength(0.07))
      .force('collide', d3.forceCollide(radius + 1.5))
      .stop();

    for (let tick = 0; tick < 220; tick += 1) {
      simulation.tick();
    }

    const color = d3.scaleLinear()
      .domain([0, 50, 100])
      .range(['#d94841', '#f59e0b', '#2f9e44']);

    const renderTooltipHtml = (entry) => (
      `<strong><a href="${getProposalHref(entry.id)}" target="_blank" rel="noreferrer">${proposalShortLabel} ${entry.id}</a></strong><br/>` +
      `Compliance score: ${formatScore(entry.score)}<br/>` +
      `Status: ${entry.status || 'Unknown'}<br/>` +
      `BIP2 score: ${entry.bip2Score == null ? 'n/a' : formatScore(entry.bip2Score)}<br/>` +
      `BIP3 score: ${entry.bip3Score == null ? 'n/a' : formatScore(entry.bip3Score)}`
    );

    const applyBaseBubbleStyles = (selection) => {
      selection
        .attr('stroke', (entry) => {
          const normalizedId = normalizeProposalId(entry.id);
          return highlightedProposalId && normalizedId === highlightedProposalId ? '#0f172a' : '#fff';
        })
        .attr('stroke-width', (entry) => {
          const normalizedId = normalizeProposalId(entry.id);
          return highlightedProposalId && normalizedId === highlightedProposalId ? 2 : 1.25;
        })
        .attr('r', (entry) => {
          const normalizedId = normalizeProposalId(entry.id);
          return highlightedProposalId && normalizedId === highlightedProposalId ? radius + 1.5 : radius;
        })
        .attr('fill-opacity', (entry) => {
          const normalizedId = normalizeProposalId(entry.id);
          if (!highlightedProposalId) {
            return 0.88;
          }
          return normalizedId === highlightedProposalId ? 0.96 : 0.22;
        });
    };

    const pinBubble = (nodeSelection, entry, pageX, pageY) => {
      pinnedProposalId = entry.id;
      applyBaseBubbleStyles(bubbles);
      nodeSelection
        .attr('fill-opacity', 0.96)
        .attr('stroke', '#0f172a')
        .attr('stroke-width', 2)
        .attr('r', radius + 1.5);
      tooltip
        .style('opacity', 1)
        .style('pointer-events', 'auto')
        .html(renderTooltipHtml(entry));
      setTooltipPosition(pageX, pageY);
    };

    const bubbles = root.append('g')
      .selectAll('circle')
      .data(bees)
      .enter()
      .append('circle')
      .attr('cx', (entry) => entry.x)
      .attr('cy', (entry) => entry.y)
      .attr('r', radius)
      .attr('fill', (entry) => color(entry.score))
      .attr('fill-opacity', 0.88)
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.25)
      .on('mouseover', function (event, entry) {
        if (pinnedProposalId) {
          return;
        }
        d3.select(this)
          .attr('fill-opacity', 0.96)
          .attr('stroke', '#0f172a')
          .attr('stroke-width', 2)
          .attr('r', radius + 1.5);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(entry));
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mousemove', function (event) {
        if (pinnedProposalId) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedProposalId) {
          return;
        }
        applyBaseBubbleStyles(bubbles);
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, entry) {
        event.stopPropagation();
        pinBubble(d3.select(this), entry, event.pageX, event.pageY);
      });

    applyBaseBubbleStyles(bubbles);

    svg.on('click', () => {
      pinnedProposalId = null;
      applyBaseBubbleStyles(bubbles);
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
    });

    return () => {
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.formal-conformity-tooltip').remove();
    };
  }, [height, highlightProposal, proposalShortLabel, rows, width]);

  return <svg ref={ref} role="img" aria-label="Formal conformity beeswarm plot" />;
};
