import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { renderProposalListHtml } from './bipTooltipContent';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';

const AUTHORS_BAR_COLOR = '#e45756';
const AUTHORS_BAR_HOVER_COLOR = '#b63f3e';

export const TopAuthorsChart = ({ data, width = 600, height = 400 }) => {
  const ref = useRef();
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

  useEffect(() => {
    let sortedAuthors = [];

    if (Array.isArray(data?.topAuthors) && data.topAuthors.length > 0) {
      sortedAuthors = data.topAuthors
        .map((entry) => ({
          author: entry.author,
          count: Number(entry.count || 0),
          bips: Array.isArray(entry.bips) ? entry.bips : [],
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 10);
    } else {
      const authorCounts = {};

      (data?.nodes || []).forEach((proposal) => {
        if (Array.isArray(proposal.author)) {
          proposal.author.forEach((author) => {
            const name = author.split('<')[0].trim();
            authorCounts[name] = (authorCounts[name] || 0) + 1;
          });
          return;
        }

        if (typeof proposal.author === 'string' && proposal.author.trim()) {
          const name = proposal.author.split('<')[0].trim();
          authorCounts[name] = (authorCounts[name] || 0) + 1;
        }
      });

      sortedAuthors = Object.entries(authorCounts)
        .map(([author, count]) => ({ author, count, bips: [] }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 10);
    }

    if (sortedAuthors.length === 0) {
      const svg = d3.select(ref.current);
      svg.selectAll("*").remove();
      return;
    }

    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();
    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');
    d3.select('body').selectAll('.author-tooltip').remove(); // Clean up old tooltips

    // Tooltip setup
    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'author-tooltip')
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

    let pinnedAuthor = null;

    const renderTooltipHtml = (entry) => {
      return (
        `<strong>${entry.author}</strong><br/>` +
        `Proposals: ${entry.count}<br/>` +
        renderProposalListHtml(entry.bips, snapshotLabel, { ecosystem, linkMode })
      );
    };

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const longestAuthorLabel = d3.max(sortedAuthors, (entry) => String(entry.author || '').length) || 0;
    const margin = {
      top: 20,
      right: 24,
      bottom: 32,
      left: Math.min(132, Math.max(96, (longestAuthorLabel * 7) + 8)),
    };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleLinear()
      .domain([0, d3.max(sortedAuthors, d => d.count)])
      .range([0, innerWidth]);

    const y = d3.scaleBand()
      .domain(sortedAuthors.map(d => d.author))
      .range([0, innerHeight])
      .padding(0.2);

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const resetBarStyles = () => {
      g.selectAll('rect')
        .attr('fill', AUTHORS_BAR_COLOR);
    };

    g.append("g")
      .call(d3.axisLeft(y).tickSize(0).tickPadding(10))
      .call((axis) => axis.selectAll('text').style('font-size', '13px'))
      .call((axis) => axis.select('.domain').remove());

    g.selectAll("rect")
      .data(sortedAuthors)
      .enter()
      .append("rect")
      .attr("y", d => y(d.author))
      .attr("width", d => x(d.count))
      .attr("height", y.bandwidth())
      .attr("fill", AUTHORS_BAR_COLOR)
      .on("mouseover", function (event, d) {
        if (pinnedAuthor) {
          return;
        }

        d3.select(this)
          .transition().duration(200)
          .attr("fill", AUTHORS_BAR_HOVER_COLOR);

        tooltip
          .style("opacity", 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(d));
      })
      .on("mousemove", function (event) {
        if (pinnedAuthor) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on("mouseout", function () {
        if (pinnedAuthor) {
          return;
        }

        d3.select(this)
          .transition().duration(200)
          .attr("fill", AUTHORS_BAR_COLOR);

        tooltip.style("opacity", 0);
      })
      .on('click', function (event, d) {
        event.stopPropagation();
        pinnedAuthor = d.author;
        resetBarStyles();
        d3.select(this).attr('fill', AUTHORS_BAR_HOVER_COLOR);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(d));
        setTooltipPosition(event.pageX, event.pageY);
      });

    g.selectAll("text.count")
      .data(sortedAuthors)
      .enter()
      .append("text")
      .attr("class", "count")
      .attr("x", d => x(d.count) + 5)
      .attr("y", d => y(d.author) + y.bandwidth() / 2 + 5)
      .text(d => d.count)
      .style("font-size", "13px");

    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).ticks(5))
      .style("display", "none");

    svg.on('click', () => {
      pinnedAuthor = null;
      resetBarStyles();
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
    });

    // Cleanup
    return () => {
      svg.selectAll("*").remove();
      d3.select('body').selectAll('.author-tooltip').remove();
    };

  }, [data, ecosystem, height, linkMode, snapshotLabel, width]);

  return <svg ref={ref} role="img" aria-label="Top proposal authors chart" />;
};
