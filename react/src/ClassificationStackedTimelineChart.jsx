import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { renderBipListHtml } from './bipTooltipContent';
import { getClassificationColorMap } from './classificationColors';

export const ClassificationStackedTimelineChart = ({
  categoryDomains,
  dimensions,
  selectedDimensions,
  timelineData,
  width = 1200,
  height = 560,
}) => {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    const activeDimensions = (selectedDimensions || []).filter(
      (field) => timelineData?.[field]?.rows?.length
    );

    if (activeDimensions.length === 0) {
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
      .style('background', '#1a1a1a')
      .style('color', '#fff')
      .style('padding', '6px 10px')
      .style('border-radius', '4px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('max-width', '360px')
      .style('line-height', '1.45')
      .style('opacity', 0);

    let pinnedSegmentKey = null;

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const margin = { top: 20, right: 20, bottom: 52, left: 58 };
    const panelGap = 42;
    const innerWidth = width - margin.left - margin.right;
    const panelHeight = (height - margin.top - margin.bottom - panelGap * (activeDimensions.length - 1))
      / activeDimensions.length;

    const allYears = Array.from(
      new Set(
        activeDimensions.flatMap((field) => timelineData[field].rows.map((row) => row.year))
      )
    ).sort((left, right) => Number(left) - Number(right));

    const x = d3.scaleBand()
      .domain(allYears)
      .range([0, innerWidth])
      .padding(0.18);

    const root = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    activeDimensions.forEach((field, panelIndex) => {
      const config = dimensions.find((dimension) => dimension.field === field);
      const panel = root.append('g')
        .attr('transform', `translate(0, ${(panelHeight + panelGap) * panelIndex})`);
      const { categories, rows } = timelineData[field];
      const colorDomain = Array.isArray(categoryDomains?.[field]) && categoryDomains[field].length
        ? categoryDomains[field]
        : categories;
      const orderedCategories = [
        ...colorDomain.filter((category) => categories.includes(category)),
        ...categories.filter((category) => !colorDomain.includes(category)),
      ];
      const colorMap = getClassificationColorMap(field, colorDomain);
      const totalCount = rows.reduce(
        (sum, row) => sum + orderedCategories.reduce((rowSum, category) => rowSum + Number(row?.values?.[category] || 0), 0),
        0
      );
      const totalByCategory = Object.fromEntries(
        orderedCategories.map((category) => [
          category,
          rows.reduce((sum, row) => sum + Number(row?.values?.[category] || 0), 0),
        ])
      );
      const rowMap = new Map(rows.map((row) => [row.year, row]));
      const normalizedRows = allYears.map((year) => {
        const sourceRow = rowMap.get(year) || {};
        const values = sourceRow.values || {};
        const bips = sourceRow.bips || {};
        const row = { year };
        orderedCategories.forEach((category) => {
          row[category] = values[category] || 0;
        });
        row.bips = bips;
        return row;
      });

      const stack = d3.stack().keys(orderedCategories);
      const layers = stack(normalizedRows);
      const y = d3.scaleLinear()
        .domain([
          0,
          d3.max(normalizedRows, (row) => orderedCategories.reduce((sum, category) => sum + Number(row[category] || 0), 0)) || 0,
        ])
        .nice()
        .range([panelHeight, 0]);
      const color = d3.scaleOrdinal()
        .domain(orderedCategories)
        .range(orderedCategories.map((category) => colorMap[category]));

      panel.append('g')
        .call(d3.axisLeft(y).ticks(4))
        .call((axis) => axis.selectAll('line').attr('stroke', '#d7dee8'));

      const renderTooltipHtml = (segment) => {
        const bipList = Array.isArray(segment.data?.bips?.[segment.key])
          ? segment.data.bips[segment.key]
          : [];

        return (
          `<strong>${config?.label || field}</strong><br/>` +
          `Year: ${segment.data.year}<br/>` +
          `Category: ${segment.key}<br/>` +
          `Count: ${segment.data[segment.key]}<br/>` +
          renderBipListHtml(bipList)
        );
      };

      const resetBarStyles = () => {
        panel.selectAll('rect.classification-segment')
          .attr('opacity', 1)
          .attr('stroke', 'none')
          .attr('stroke-width', 0);
      };

      panel.selectAll('g.layer')
        .data(layers)
        .enter()
        .append('g')
        .attr('fill', (layer) => color(layer.key))
        .selectAll('rect')
        .data((layer) => layer.map((segment) => ({ ...segment, key: layer.key })))
        .enter()
        .append('rect')
        .attr('class', 'classification-segment')
        .attr('x', (segment) => x(segment.data.year))
        .attr('y', (segment) => y(segment[1]))
        .attr('width', x.bandwidth())
        .attr('height', (segment) => Math.max(0, y(segment[0]) - y(segment[1])))
        .on('mouseover', function (event, segment) {
          if (pinnedSegmentKey) {
            return;
          }
          d3.select(this).attr('opacity', 0.85);
          tooltip
            .style('opacity', 1)
            .style('pointer-events', 'none')
            .html(renderTooltipHtml(segment));
        })
        .on('mousemove', function (event) {
          if (pinnedSegmentKey) {
            return;
          }
          setTooltipPosition(event.pageX, event.pageY);
        })
        .on('mouseout', function () {
          if (pinnedSegmentKey) {
            return;
          }
          d3.select(this).attr('opacity', 1);
          tooltip.style('opacity', 0);
        })
        .on('click', function (event, segment) {
          event.stopPropagation();
          pinnedSegmentKey = `${field}|||${segment.data.year}|||${segment.key}`;
          resetBarStyles();
          d3.select(this)
            .attr('opacity', 0.92)
            .attr('stroke', '#0f172a')
            .attr('stroke-width', 2);
          tooltip
            .style('opacity', 1)
            .style('pointer-events', 'auto')
            .html(renderTooltipHtml(segment));
          setTooltipPosition(event.pageX, event.pageY);
        });

      const legend = panel.append('g')
        .attr('transform', `translate(${innerWidth - 180}, 0)`);

      orderedCategories.slice(0, 6).forEach((category, index) => {
        const row = legend.append('g')
          .attr('transform', `translate(0, ${index * 18})`);

        row.append('rect')
          .attr('width', 10)
          .attr('height', 10)
          .attr('rx', 2)
          .attr('fill', color(category));

        row.append('text')
          .attr('x', 16)
          .attr('y', 9)
          .style('font-size', '11px')
          .style('fill', '#475569')
          .text(
            `${category} (${totalByCategory[category] || 0}, ${Math.round(((totalByCategory[category] || 0) / (totalCount || 1)) * 100)}%)`
          );
      });

      if (panelIndex === activeDimensions.length - 1) {
        panel.append('g')
          .attr('transform', `translate(0,${panelHeight})`)
          .call(d3.axisBottom(x))
          .selectAll('text')
          .attr('transform', 'rotate(-45)')
          .style('text-anchor', 'end');
      }
    });

    svg.on('click', () => {
      pinnedSegmentKey = null;
      root.selectAll('rect.classification-segment')
        .attr('opacity', 1)
        .attr('stroke', 'none')
        .attr('stroke-width', 0);
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
    });

    return () => {
      svg.selectAll('*').remove();
      tooltip.remove();
    };
  }, [categoryDomains, dimensions, selectedDimensions, timelineData, width, height]);

  return <svg ref={ref} role="img" aria-label="Classification stacked timeline chart" />;
};
