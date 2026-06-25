import * as d3 from 'd3';
import { positionTooltip } from './tooltipPosition';
import { useEffect, useRef } from 'react';
import { renderProposalListRow } from './bipTooltipContent';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { renderTooltipCardHtml } from './tooltipHtml';

const CHORD_DIMENSION_ORDER = ['type', 'layer', 'status'];
const CHORD_GLOBAL_ROTATION_DEGREES = 3;
const CHORD_SPACER_FACTOR = 20;
const CHORD_MIN_SPACER_COUNT = 4;
const CHORD_BOTTOM_MARGIN = 12;
const CHORD_CATEGORY_LABEL_OUTSET = -10;
const DIMENSION_BADGE_OFFSETS = {
  type: { x: 40, y: 26 },
  layer: { x: 40, y: -10 },
  status: { x: -40, y: 26 },
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalizeAngle(angle) {
  const fullTurn = Math.PI * 2;
  return ((angle % fullTurn) + fullTurn) % fullTurn;
}

function wrapChordLabel(label, maxLineLength = 10, maxLines = 2) {
  const words = String(label || '').trim().split(/\s+/).filter(Boolean);
  if (!words.length) {
    return [''];
  }

  const lines = [];
  let currentLine = words[0];

  for (let index = 1; index < words.length; index += 1) {
    const candidate = `${currentLine} ${words[index]}`;
    if (candidate.length <= maxLineLength) {
      currentLine = candidate;
      continue;
    }

    lines.push(currentLine);
    currentLine = words[index];

    if (lines.length === maxLines - 1) {
      currentLine = [currentLine, ...words.slice(index + 1)].join(' ');
      break;
    }
  }

  lines.push(currentLine);
  return lines.slice(0, maxLines);
}

export const ClassificationChordDiagram = ({ data, width = 1000, height = 700 }) => {
  const ref = useRef();
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

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

    const minDimension = Math.min(width, height);
    const framePaddingX = clamp(width * 0.02, 8, 20);
    const framePaddingTop = clamp(height * 0.05, 20, 120);
    const framePaddingBottom = clamp(height * 0.05, 110, 250);
    const contentWidth = width - framePaddingX * 2;
    const contentHeight = height - framePaddingTop - framePaddingBottom;
    const ringThickness = clamp(minDimension * 0.03, 18, 24);
    const categoryLabelOffset = clamp(minDimension * 0.02, 14, 18);
    const categoryLabelFontSize = clamp(minDimension * 0.015, 11, 13);
    const categoryLabelMaxLineLength = width <= 820 ? 10 : 12;
    const categoryLabelMaxLines = height <= 760 ? 2 : 3;
    const dimensionLabelRadius = outerRadius => outerRadius + clamp(minDimension * 0.078, 52, 64);
    const dimensionBadgeWidth = clamp(minDimension * 0.11, 76, 88);
    const dimensionBadgeHeight = clamp(minDimension * 0.04, 30, 34);
    const dimensionBadgeRadius = clamp(dimensionBadgeHeight * 0.28, 8, 10);
    const dimensionBadgeFontSize = clamp(minDimension * 0.02, 14, 16);
    const arcStrokeWidth = clamp(minDimension * 0.002, 1.1, 1.5);
    const arcHoverStrokeWidth = clamp(arcStrokeWidth + 1, 2.2, 2.6);
    const ribbonHoverStrokeWidth = clamp(minDimension * 0.0016, 1, 1.25);

    const tooltipNode = document.createElement('div');
    document.body.appendChild(tooltipNode);

    const tooltip = d3.select(tooltipNode)
      .attr('class', 'classification-chord-tooltip')
      .style('position', 'absolute')
      .style('background', 'var(--tooltip-bg)')
      .style('color', 'var(--tooltip-text)')
      .style('padding', '8px 12px')
      .style('border-radius', '6px')
      .style('border', '1px solid var(--tooltip-border)')
      .style('box-shadow', 'var(--tooltip-shadow)')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('line-height', '1.45')
      .style('opacity', 0);

    const availableDimensions = Array.from(new Set(groups.map((group) => group.dimension)));
    const orderedDimensions = CHORD_DIMENSION_ORDER.filter((dimension) => availableDimensions.includes(dimension));
    const spacerCount = Math.max(
      CHORD_MIN_SPACER_COUNT,
      Math.ceil(CHORD_SPACER_FACTOR / Math.max(orderedDimensions.length, 1))
    );
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

    const globalRotationRadians = (CHORD_GLOBAL_ROTATION_DEGREES * Math.PI) / 180;
    const chords = chord(displayMatrix);
    const outerRadius = Math.min(contentWidth * 0.42, contentHeight * 0.49);
    const innerRadius = outerRadius - ringThickness;
    const baseTranslateX = framePaddingX + (contentWidth / 2);
    const baseTranslateY = framePaddingTop + (contentHeight / 2);

    const root = svg.append('g')
      .attr('transform', `translate(${baseTranslateX}, ${baseTranslateY}) rotate(${CHORD_GLOBAL_ROTATION_DEGREES})`);

    const arc = d3.arc()
      .innerRadius(innerRadius)
      .outerRadius(outerRadius);

    const ribbon = d3.ribbon()
      .radius(innerRadius);

    const setTooltipPosition = (pageX, pageY) => {
      positionTooltip(tooltip, pageX, pageY);
    };

    const getGroupColor = (group) => colorMaps[group.dimension]?.[group.category] || '#64748b';
    const getPairKey = (sourceIndex, targetIndex) => (
      [sourceIndex, targetIndex].sort((left, right) => left - right).join('|||')
    );

    let pinnedKey = null;

    const renderGroupTooltipHtml = (groupDatum) => {
      const group = displayGroups[groupDatum.index];
      return renderTooltipCardHtml({
        titleHtml: `<strong>${group.label}</strong>`,
        rows: [['Total Pairwise Links', Math.round(groupDatum.value)]],
      });
    };

    const renderRibbonTooltipHtml = (chordDatum) => {
      const source = displayGroups[chordDatum.source.index];
      const target = displayGroups[chordDatum.target.index];
      const bips = pairBips[getPairKey(source.originalIndex, target.originalIndex)] || [];

      return renderTooltipCardHtml({
        titleHtml: `<strong>${source.label}</strong> <span class="tooltip-card__arrow">&times;</span> <strong>${target.label}</strong>`,
        rows: [
          ['Count', Math.round(chordDatum.source.value)],
          renderProposalListRow(bips, snapshotLabel, { ecosystem, linkMode }),
        ],
      });
    };

    const resetStyles = () => {
      root.selectAll('path.classification-chord-ribbon')
        .attr('opacity', 0.72)
        .attr('stroke', 'none');

      root.selectAll('path.classification-chord-arc')
        .attr('opacity', 1)
        .attr('stroke-width', arcStrokeWidth);
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
      .attr('stroke', 'var(--chart-contrast)')
      .attr('stroke-width', arcStrokeWidth)
      .on('mouseover', function (event, entry) {
        if (pinnedKey) {
          return;
        }

        d3.select(this).attr('opacity', 0.9).attr('stroke-width', arcHoverStrokeWidth);
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

        d3.select(this).attr('opacity', 1).attr('stroke-width', arcStrokeWidth);
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, entry) {
        event.stopPropagation();
        pinnedKey = `group|||${entry.index}`;
        resetStyles();
        d3.select(this).attr('opacity', 0.9).attr('stroke-width', arcHoverStrokeWidth);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderGroupTooltipHtml(entry));
        setTooltipPosition(event.pageX, event.pageY);
      });

    group.append('text')
      .each((entry) => {
        entry.angle = (entry.startAngle + entry.endAngle) / 2;
        entry.displayAngle = normalizeAngle(entry.angle + globalRotationRadians);
      })
      .attr('transform', (entry) => `
        rotate(${(entry.angle * 180 / Math.PI) - 90})
        translate(${outerRadius + categoryLabelOffset + CHORD_CATEGORY_LABEL_OUTSET})
        ${entry.displayAngle > Math.PI ? 'rotate(180)' : ''}
      `)
      .attr('text-anchor', (entry) => (entry.displayAngle > Math.PI ? 'end' : 'start'))
      .attr('dominant-baseline', 'middle')
      .style('font-size', `${categoryLabelFontSize}px`)
      .style('fill', 'var(--chart-muted)')
      .each(function (entry) {
        const text = d3.select(this);
        const lines = wrapChordLabel(
          displayGroups[entry.index].category,
          categoryLabelMaxLineLength,
          categoryLabelMaxLines
        );
        const startDy = -((lines.length - 1) * 0.55);

        text.selectAll('tspan')
          .data(lines)
          .join('tspan')
          .attr('x', 0)
          .attr('dy', (_, lineIndex) => (lineIndex === 0 ? `${startDy}em` : '1.1em'))
          .text((line) => line);
      });

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

    const dimensionLabelGroup = root.append('g')
      .selectAll('g')
      .data(dimensionHeaders)
      .join('g')
      .attr('transform', (entry) => {
        const angle = (entry.startAngle + entry.endAngle) / 2;
        const badgeOffset = {
        ...(DIMENSION_BADGE_OFFSETS[entry.dimension] || { x: 0, y: 0 }),
        ...(ecosystem?.classificationChordBadgeOffsets?.[entry.dimension] || {}),
      };
        const x = (Math.cos(angle - (Math.PI / 2)) * dimensionLabelRadius(outerRadius)) + badgeOffset.x;
        const y = (Math.sin(angle - (Math.PI / 2)) * dimensionLabelRadius(outerRadius)) + badgeOffset.y;
        return `translate(${x}, ${y}) rotate(${-CHORD_GLOBAL_ROTATION_DEGREES})`;
      });

    dimensionLabelGroup.append('rect')
      .attr('x', -(dimensionBadgeWidth / 2))
      .attr('y', -(dimensionBadgeHeight / 2))
      .attr('width', dimensionBadgeWidth)
      .attr('height', dimensionBadgeHeight)
      .attr('rx', dimensionBadgeRadius)
      .attr('fill', (entry) => dimensionBadgeColors[entry.dimension]?.fill || '#475569')
      .attr('stroke', 'var(--chart-contrast)')
      .attr('stroke-width', 1);

    dimensionLabelGroup.append('text')
      .attr('x', 0)
      .attr('y', 1)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .style('font-size', `${dimensionBadgeFontSize}px`)
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
      .attr('fill', 'var(--chart-axis)')
      .attr('stroke', 'none')
      .attr('opacity', 0.72)
      .on('mouseover', function (event, entry) {
        if (pinnedKey) {
          return;
        }

        d3.select(this).attr('opacity', 0.95).attr('stroke', 'var(--chart-focus)').attr('stroke-width', ribbonHoverStrokeWidth);
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
          .attr('stroke', 'var(--chart-focus)')
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

    const svgNode = ref.current;
    const rootNode = root.node();
    if (svgNode && rootNode) {
      const svgRect = svgNode.getBoundingClientRect();
      const rootRect = rootNode.getBoundingClientRect();

      if (svgRect.width > 0 && svgRect.height > 0 && rootRect.width > 0 && rootRect.height > 0) {
        const scaleX = width / svgRect.width;
        const scaleY = height / svgRect.height;
        const targetCenterX = framePaddingX + (contentWidth / 2);
        const targetBottomY = height - CHORD_BOTTOM_MARGIN;
        const renderedCenterX = ((rootRect.left - svgRect.left) + (rootRect.width / 2)) * scaleX;
        const renderedBottomY = ((rootRect.top - svgRect.top) + rootRect.height) * scaleY;
        const deltaX = targetCenterX - renderedCenterX;
        const deltaY = targetBottomY - renderedBottomY;

        root.attr(
          'transform',
          `translate(${baseTranslateX + deltaX}, ${baseTranslateY + deltaY}) rotate(${CHORD_GLOBAL_ROTATION_DEGREES})`
        );
      }
    }

    return () => {
      svg.selectAll('*').remove();
      tooltip.remove();
    };
  }, [data, ecosystem, height, linkMode, snapshotLabel, width]);

  return <svg ref={ref} role="img" aria-label="Classification chord diagram" />;
};
