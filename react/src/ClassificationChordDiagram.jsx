import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { renderBipListHtml } from './bipTooltipContent';

export const ClassificationChordDiagram = ({ data, width = 1200, height = 760 }) => {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();

    const groups = Array.isArray(data?.groups) ? data.groups : [];
    const matrix = Array.isArray(data?.matrix) ? data.matrix : [];
    const pairBips = data?.pairBips || {};

    if (!groups.length || !matrix.length) {
      return;
    }

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const framePadding = 60;
    const contentWidth = width - framePadding * 2;
    const contentHeight = height - framePadding * 2;

    const tooltipNode = document.createElement('div');
    document.body.appendChild(tooltipNode);

    const tooltip = d3.select(tooltipNode)
      .attr('class', 'classification-chord-tooltip')
      .style('position', 'absolute')
      .style('background', '#1a1a1a')
      .style('color', '#fff')
      .style('padding', '8px 12px')
      .style('border-radius', '6px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('line-height', '1.45')
      .style('opacity', 0);

    const orderedDimensions = Array.from(new Set(groups.map((group) => group.dimension)));
    const spacerCount = Math.max(4, Math.ceil(15 / Math.max(orderedDimensions.length, 1)));
    const dimensionInterpolators = {
      layer: d3.interpolateBlues,
      status: d3.interpolateOranges,
      type: d3.interpolateGreens,
    };
    const dimensionBadgeColors = {
      layer: {
        fill: d3.interpolateBlues(0.75),
        text: '#eff6ff',
      },
      status: {
        fill: d3.interpolateOranges(0.72),
        text: '#fff7ed',
      },
      type: {
        fill: d3.interpolateGreens(0.72),
        text: '#f0fdf4',
      },
    };
    const colorMaps = Object.fromEntries(
      orderedDimensions.map((dimension) => [
        dimension,
        (() => {
          const categories = groups
            .filter((group) => group.dimension === dimension)
            .map((group) => group.category);
          const uniqueCategories = Array.from(new Set(categories));
          const interpolate = dimensionInterpolators[dimension] || d3.interpolateBlues;
          const shades = uniqueCategories.length === 1
            ? [interpolate(0.68)]
            : uniqueCategories.map((_, index) => (
              interpolate(0.42 + (0.46 * index) / Math.max(uniqueCategories.length - 1, 1))
            ));

          return Object.fromEntries(
            uniqueCategories.map((category, index) => [category, shades[index]])
          );
        })(),
      ])
    );

    const displayGroups = [];
    const displayIndexByGroupIndex = new Map();
    let spacerIndex = 0;

    orderedDimensions.forEach((dimension, dimensionIndex) => {
      groups
        .map((group, index) => ({ ...group, originalIndex: index }))
        .filter((group) => group.dimension === dimension)
        .forEach((group) => {
          displayIndexByGroupIndex.set(group.originalIndex, displayGroups.length);
          displayGroups.push({
            ...group,
            spacer: false,
          });
        });

      for (let gap = 0; gap < spacerCount; gap += 1) {
        displayGroups.push({
          id: `spacer-${spacerIndex}`,
          label: '',
          dimension,
          category: '',
          spacer: true,
        });
        spacerIndex += 1;
      }
    });

    const displayMatrix = Array.from(
      { length: displayGroups.length },
      () => Array(displayGroups.length).fill(0)
    );

    matrix.forEach((row, rowIndex) => {
      row.forEach((value, columnIndex) => {
        const mappedRow = displayIndexByGroupIndex.get(rowIndex);
        const mappedColumn = displayIndexByGroupIndex.get(columnIndex);
        if (mappedRow == null || mappedColumn == null) {
          return;
        }
        displayMatrix[mappedRow][mappedColumn] = value;
      });
    });

    const chord = d3.chord()
      .padAngle(0.016)
      .sortSubgroups(d3.descending)
      .sortChords(d3.descending);

    const chords = chord(displayMatrix);
    const outerRadius = Math.min(contentWidth, contentHeight) * 0.37;
    const innerRadius = outerRadius - 24;

    const root = svg.append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    const arc = d3.arc()
      .innerRadius(innerRadius)
      .outerRadius(outerRadius);

    const ribbon = d3.ribbon()
      .radius(innerRadius);

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const getGroupColor = (group) => colorMaps[group.dimension]?.[group.category] || '#64748b';
    const getPairKey = (sourceIndex, targetIndex) => (
      [sourceIndex, targetIndex].sort((left, right) => left - right).join('|||')
    );

    let pinnedKey = null;

    const renderGroupTooltipHtml = (groupDatum) => {
      const group = displayGroups[groupDatum.index];
      return (
        `<strong>${group.label}</strong><br/>` +
        `Total pairwise links: ${Math.round(groupDatum.value)}`
      );
    };

    const renderRibbonTooltipHtml = (chordDatum) => {
      const source = displayGroups[chordDatum.source.index];
      const target = displayGroups[chordDatum.target.index];
      const bips = pairBips[getPairKey(source.originalIndex, target.originalIndex)] || [];

      return (
        `<strong>${source.label}</strong> × <strong>${target.label}</strong><br/>` +
        `Count: ${Math.round(chordDatum.source.value)}<br/>` +
        renderBipListHtml(bips)
      );
    };

    const resetStyles = () => {
      root.selectAll('path.classification-chord-ribbon')
        .attr('opacity', 0.72)
        .attr('stroke', 'none');

      root.selectAll('path.classification-chord-arc')
        .attr('opacity', 1)
        .attr('stroke-width', 1.5);
    };

    const visibleGroups = chords.groups.filter((entry) => !displayGroups[entry.index].spacer);

    const group = root.append('g')
      .selectAll('g')
      .data(visibleGroups)
      .join('g');

    group.append('path')
      .attr('class', 'classification-chord-arc')
      .attr('d', arc)
      .attr('fill', (entry) => getGroupColor(displayGroups[entry.index]))
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .on('mouseover', function (event, entry) {
        if (pinnedKey) {
          return;
        }

        d3.select(this).attr('opacity', 0.9).attr('stroke-width', 2.5);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderGroupTooltipHtml(entry));
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mousemove', function (event) {
        if (pinnedKey) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedKey) {
          return;
        }

        d3.select(this).attr('opacity', 1).attr('stroke-width', 1.5);
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, entry) {
        event.stopPropagation();
        pinnedKey = `group|||${entry.index}`;
        resetStyles();
        d3.select(this).attr('opacity', 0.9).attr('stroke-width', 2.5);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderGroupTooltipHtml(entry));
        setTooltipPosition(event.pageX, event.pageY);
      });

    group.append('text')
      .each((entry) => {
        entry.angle = (entry.startAngle + entry.endAngle) / 2;
      })
      .attr('dy', '0.35em')
      .attr('transform', (entry) => `
        rotate(${(entry.angle * 180 / Math.PI) - 90})
        translate(${outerRadius + 16})
        ${entry.angle > Math.PI ? 'rotate(180)' : ''}
      `)
      .attr('text-anchor', (entry) => (entry.angle > Math.PI ? 'end' : 'start'))
      .style('font-size', '12px')
      .style('fill', '#475569')
      .text((entry) => displayGroups[entry.index].category);

    const dimensionHeaders = orderedDimensions.map((dimension) => {
      const dimensionGroups = visibleGroups.filter(
        (entry) => displayGroups[entry.index].dimension === dimension
      );
      const label = dimension.charAt(0).toUpperCase() + dimension.slice(1);

      return {
        dimension,
        label,
        startAngle: d3.min(dimensionGroups, (entry) => entry.startAngle) ?? 0,
        endAngle: d3.max(dimensionGroups, (entry) => entry.endAngle) ?? 0,
      };
    });

    const dimensionLabelRadius = outerRadius + 62;
    const dimensionLabelGroup = root.append('g')
      .selectAll('g')
      .data(dimensionHeaders)
      .join('g')
      .attr('transform', (entry) => {
        const angle = (entry.startAngle + entry.endAngle) / 2;
        const degrees = (angle * 180 / Math.PI) - 90;
        const flip = angle > Math.PI ? 'rotate(180)' : '';
        return `rotate(${degrees}) translate(${dimensionLabelRadius}) ${flip}`;
      });

    dimensionLabelGroup.append('rect')
      .attr('x', (entry) => {
        const angle = (entry.startAngle + entry.endAngle) / 2;
        return angle > Math.PI ? -84 : 0;
      })
      .attr('y', -16)
      .attr('width', 84)
      .attr('height', 32)
      .attr('rx', 9)
      .attr('fill', (entry) => dimensionBadgeColors[entry.dimension]?.fill || '#475569')
      .attr('stroke', 'rgba(255,255,255,0.75)')
      .attr('stroke-width', 1);

    dimensionLabelGroup.append('text')
      .attr('x', (entry) => {
        const angle = (entry.startAngle + entry.endAngle) / 2;
        return angle > Math.PI ? -42 : 42;
      })
      .attr('y', 1)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .style('font-size', '16px')
      .style('font-weight', 600)
      .style('fill', (entry) => dimensionBadgeColors[entry.dimension]?.text || '#ffffff')
      .text((entry) => entry.label);

    root.append('g')
      .attr('fill-opacity', 0.9)
      .selectAll('path')
      .data(chords.filter((entry) => {
        const source = displayGroups[entry.source.index];
        const target = displayGroups[entry.target.index];
        return !source.spacer && !target.spacer;
      }))
      .join('path')
      .attr('class', 'classification-chord-ribbon')
      .attr('d', ribbon)
      .attr('fill', '#cbd5e1')
      .attr('stroke', 'none')
      .attr('opacity', 0.72)
      .on('mouseover', function (event, entry) {
        if (pinnedKey) {
          return;
        }

        d3.select(this).attr('opacity', 0.95).attr('stroke', '#0f172a').attr('stroke-width', 1.25);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderRibbonTooltipHtml(entry));
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mousemove', function (event) {
        if (pinnedKey) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedKey) {
          return;
        }

        d3.select(this).attr('opacity', 0.72).attr('stroke', 'none');
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, entry) {
        event.stopPropagation();
        pinnedKey = `ribbon|||${getPairKey(entry.source.index, entry.target.index)}`;
        resetStyles();
        d3.select(this)
          .attr('opacity', 0.95)
          .attr('stroke', '#0f172a')
          .attr('stroke-width', 1.25);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderRibbonTooltipHtml(entry));
        setTooltipPosition(event.pageX, event.pageY);
      });

    svg.on('click', () => {
      pinnedKey = null;
      resetStyles();
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
    });

    return () => {
      svg.selectAll('*').remove();
      tooltip.remove();
    };
  }, [data, width, height]);

  return <svg ref={ref} role="img" aria-label="Classification chord diagram" />;
};
