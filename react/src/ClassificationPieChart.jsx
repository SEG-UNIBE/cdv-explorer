import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { renderBipListHtml } from './bipTooltipContent';
import { getClassificationColorMap } from './classificationColors';

export const ClassificationPieChart = ({ dimension, colorDomain, data, width = 360, height = 320 }) => {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    if (!Array.isArray(data) || data.length === 0) {
      return;
    }

    const chartData = data.filter((entry) => Number(entry.value || 0) > 0);
    if (chartData.length === 0) {
      return;
    }

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltipNode = document.createElement('div');
    document.body.appendChild(tooltipNode);

    const tooltip = d3.select(tooltipNode)
      .attr('class', 'classification-pie-tooltip')
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

    let pinnedCategory = null;

    const renderTooltipHtml = (entry) => {
      return (
        `<strong>${entry.id}</strong><br/>` +
        `Count: ${entry.value}<br/>` +
        `Share: ${((entry.value / total) * 100).toFixed(1)}%<br/>` +
        renderBipListHtml(entry.bips)
      );
    };

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const total = d3.sum(chartData, (entry) => Number(entry.value || 0));
    const radius = Math.min(width * 0.4, height * 0.48);
    const colorMap = getClassificationColorMap(
      dimension,
      Array.isArray(colorDomain) && colorDomain.length
        ? colorDomain
        : chartData.map((entry) => entry.id)
    );
    const color = d3.scaleOrdinal()
      .domain(chartData.map((entry) => entry.id))
      .range(chartData.map((entry) => colorMap[entry.id]));

    const pie = d3.pie()
      .sort(null)
      .value((entry) => Number(entry.value || 0));

    const arc = d3.arc()
      .innerRadius(radius * 0.38)
      .outerRadius(radius);

    const resetSliceStyles = () => {
      g.selectAll('path')
        .attr('opacity', 1)
        .attr('stroke', '#fff')
        .attr('stroke-width', 1.5);
    };

    const g = svg.append('g')
      .attr('transform', `translate(${width * 0.5}, ${height * 0.5})`);

    g.selectAll('path')
      .data(pie(chartData))
      .enter()
      .append('path')
      .attr('d', arc)
      .attr('fill', (entry) => color(entry.data.id))
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .on('mouseover', function (event, entry) {
        if (pinnedCategory) {
          return;
        }

        d3.select(this).attr('opacity', 0.85);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderTooltipHtml(entry.data));
      })
      .on('mousemove', function (event) {
        if (pinnedCategory) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedCategory) {
          return;
        }
        d3.select(this).attr('opacity', 1);
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, entry) {
        event.stopPropagation();
        pinnedCategory = entry.data.id;
        resetSliceStyles();
        d3.select(this)
          .attr('opacity', 0.9)
          .attr('stroke', '#0f172a')
          .attr('stroke-width', 2.5);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderTooltipHtml(entry.data));
        setTooltipPosition(event.pageX, event.pageY);
      });

    svg.on('click', () => {
      pinnedCategory = null;
      resetSliceStyles();
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
    });

    return () => {
      svg.selectAll('*').remove();
      tooltip.remove();
    };
  }, [data, dimension, colorDomain, width, height]);

  return <svg ref={ref} role="img" aria-label="Classification distribution pie chart" />;
};
