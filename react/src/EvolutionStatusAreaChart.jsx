import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { getClassificationColorMap } from './classificationColors';

export function EvolutionStatusAreaChart({
  data,
  title = 'Status Evolution',
  width = 1200,
  height = 520,
}) {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    const categories = Array.isArray(data?.categories) ? data.categories : [];
    const rawRows = Array.isArray(data?.rows) ? data.rows : [];
    if (!categories.length || !rawRows.length) {
      return;
    }

    const rows = rawRows
      .map((row) => ({
        year: Number(row?.year),
        values: row?.values || {},
      }))
      .filter((row) => Number.isFinite(row.year))
      .sort((left, right) => left.year - right.year);

    if (!rows.length) {
      return;
    }

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
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

    const margin = { top: 24, right: 210, bottom: 52, left: 58 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const years = rows.map((row) => row.year);
    const colorMap = getClassificationColorMap('status', categories);

    const x = d3.scaleLinear()
      .domain(d3.extent(years))
      .range([0, innerWidth]);

    const normalizedRows = rows.map((row) => {
      const normalized = { year: row.year };
      categories.forEach((category) => {
        normalized[category] = Number(row.values?.[category] || 0);
      });
      return normalized;
    });

    const stack = d3.stack().keys(categories);
    const layers = stack(normalizedRows);
    const y = d3.scaleLinear()
      .domain([0, d3.max(normalizedRows, (row) => categories.reduce((sum, category) => sum + Number(row[category] || 0), 0)) || 0])
      .nice()
      .range([innerHeight, 0]);

    const area = d3.area()
      .x((segment) => x(segment.data.year))
      .y0((segment) => y(segment[0]))
      .y1((segment) => y(segment[1]))
      .curve(d3.curveMonotoneX);

    const root = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    root.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).tickFormat(d3.format('d')))
      .selectAll('text')
      .attr('transform', 'rotate(-45)')
      .style('text-anchor', 'end');

    root.append('g')
      .call(d3.axisLeft(y).ticks(6))
      .call((axis) => axis.selectAll('line').attr('stroke', 'var(--chart-grid)'));

    root.append('text')
      .attr('x', 0)
      .attr('y', -8)
      .style('font-size', '12px')
      .style('fill', 'var(--chart-muted)')
      .text('BIP count');

    const series = root.append('g')
      .selectAll('path.evolution-area')
      .data(layers)
      .enter()
      .append('path')
      .attr('class', 'evolution-area')
      .attr('fill', (layer) => colorMap[layer.key])
      .attr('fill-opacity', 0.88)
      .attr('stroke', (layer) => d3.color(colorMap[layer.key]).darker(0.35))
      .attr('stroke-width', 1)
      .attr('d', area);

    const totalsByCategory = Object.fromEntries(
      categories.map((category) => [
        category,
        rows.reduce((sum, row) => sum + Number(row.values?.[category] || 0), 0),
      ])
    );

    const legend = root.append('g')
      .attr('transform', `translate(${innerWidth + 20}, 0)`);

    categories.forEach((category, index) => {
      const row = legend.append('g')
        .datum(category)
        .attr('transform', `translate(0, ${index * 18})`);

      row.append('rect')
        .attr('width', 10)
        .attr('height', 10)
        .attr('rx', 2)
        .attr('fill', colorMap[category]);

      row.append('text')
        .attr('x', 16)
        .attr('y', 9)
        .style('font-size', '11px')
        .style('fill', 'var(--chart-muted)')
        .text(`${category} (${totalsByCategory[category] || 0})`);
    });

    const focusLine = root.append('line')
      .attr('y1', 0)
      .attr('y2', innerHeight)
      .attr('stroke', 'var(--chart-focus)')
      .attr('stroke-dasharray', '4 4')
      .attr('opacity', 0);

    const renderTooltipHtml = (row) => {
      const total = categories.reduce((sum, category) => sum + Number(row.values?.[category] || 0), 0);
      const lines = categories
        .map((category) => ({
          category,
          value: Number(row.values?.[category] || 0),
        }))
        .filter((entry) => entry.value > 0)
        .sort((left, right) => right.value - left.value || left.category.localeCompare(right.category))
        .map((entry) => `${entry.category}: ${entry.value}`)
        .join('<br/>');

      return (
        `<strong>${title}</strong><br/>` +
        `Year: ${row.year}<br/>` +
        `Total: ${total}<br/>` +
        `${lines}`
      );
    };

    const setTooltipPosition = (event) => {
      tooltip
        .style('left', `${event.pageX + 10}px`)
        .style('top', `${event.pageY - 28}px`);
    };

    root.append('rect')
      .attr('width', innerWidth)
      .attr('height', innerHeight)
      .attr('fill', 'transparent')
      .on('mousemove', (event) => {
        const [mouseX] = d3.pointer(event);
        const hoveredYear = Math.round(x.invert(mouseX));
        const closestRow = rows.reduce((best, row) => (
          best == null || Math.abs(row.year - hoveredYear) < Math.abs(best.year - hoveredYear) ? row : best
        ), null);

        if (!closestRow) {
          return;
        }

        focusLine
          .attr('x1', x(closestRow.year))
          .attr('x2', x(closestRow.year))
          .attr('opacity', 1);

        tooltip
          .style('opacity', 1)
          .html(renderTooltipHtml(closestRow));
        setTooltipPosition(event);
      })
      .on('mouseleave', () => {
        focusLine.attr('opacity', 0);
        tooltip.style('opacity', 0);
      });

    series
      .on('mouseenter', function (_event, layer) {
        series.attr('fill-opacity', 0.18);
        d3.select(this).attr('fill-opacity', 0.95);
        legend.selectAll('text')
          .style('font-weight', (category) => (category === layer.key ? 700 : 400));
      })
      .on('mouseleave', () => {
        series.attr('fill-opacity', 0.88);
        legend.selectAll('text').style('font-weight', 400);
      });

    legend.selectAll('g')
      .on('mouseenter', (_event, category) => {
        series.attr('fill-opacity', (layer) => (layer.key === category ? 0.95 : 0.18));
        legend.selectAll('text')
          .style('font-weight', (value) => (value === category ? 700 : 400));
      })
      .on('mouseleave', () => {
        series.attr('fill-opacity', 0.88);
        legend.selectAll('text').style('font-weight', 400);
      });

    return () => {
      svg.selectAll('*').remove();
      tooltip.remove();
    };
  }, [data, height, title, width]);

  return <svg ref={ref} role="img" aria-label={title} />;
}
