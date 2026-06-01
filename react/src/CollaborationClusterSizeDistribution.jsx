import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

const CLUSTER_BAR_COLOR = 'var(--chart-accent-orange)';
const CLUSTER_BAR_HOVER_COLOR = 'var(--chart-accent-orange-hover)';
const GAP_TICK_KEY = '__gap__';
const MIN_COMPRESSED_GAP_LENGTH = 10;

export function CollaborationClusterSizeDistribution({ data, width = 640, height = 410 }) {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.collaboration-cluster-tooltip').remove();

    if (!Array.isArray(data) || data.length === 0) {
      return;
    }

    const sparseSeries = data
      .map((entry) => ({
        clusterSize: Number(entry.clusterSize || 0),
        clusterCount: Number(entry.clusterCount || 0),
        authorCount: Number(entry.authorCount || 0),
      }))
      .filter((entry) => entry.clusterSize > 0 && entry.clusterCount > 0)
      .sort((left, right) => left.clusterSize - right.clusterSize);

    if (sparseSeries.length === 0) {
      return;
    }

    const minClusterSize = d3.min(sparseSeries, (entry) => entry.clusterSize) || 1;
    const maxClusterSize = d3.max(sparseSeries, (entry) => entry.clusterSize) || minClusterSize;
    const countsByClusterSize = new Map(
      sparseSeries.map((entry) => [entry.clusterSize, entry.clusterCount])
    );
    const fullSeries = d3.range(minClusterSize, maxClusterSize + 1).map((clusterSize) => ({
      clusterSize,
      clusterCount: countsByClusterSize.get(clusterSize) || 0,
      authorCount: clusterSize * (countsByClusterSize.get(clusterSize) || 0),
    }));
    const zeroRuns = [];
    let zeroRunStart = null;

    fullSeries.forEach((entry, index) => {
      if (entry.clusterCount === 0) {
        if (zeroRunStart == null) {
          zeroRunStart = index;
        }
        return;
      }

      if (zeroRunStart != null) {
        zeroRuns.push({
          start: zeroRunStart,
          end: index - 1,
          length: index - zeroRunStart,
        });
        zeroRunStart = null;
      }
    });

    if (zeroRunStart != null) {
      zeroRuns.push({
        start: zeroRunStart,
        end: fullSeries.length - 1,
        length: fullSeries.length - zeroRunStart,
      });
    }

    const compressedGap = zeroRuns
      .filter((run) => run.length >= MIN_COMPRESSED_GAP_LENGTH)
      .sort((left, right) => right.length - left.length || left.start - right.start)[0];
    const series = [];

    fullSeries.forEach((entry, index) => {
      if (!compressedGap || index < compressedGap.start || index > compressedGap.end) {
        series.push({
          ...entry,
          key: String(entry.clusterSize),
          axisLabel: String(entry.clusterSize),
          isGap: false,
        });
        return;
      }

      if (index === compressedGap.start) {
        series.push({
          key: GAP_TICK_KEY,
          axisLabel: '...',
          isGap: true,
        });
      }
    });
    const seriesByKey = new Map(series.map((entry) => [entry.key, entry]));

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'collaboration-cluster-tooltip')
      .style('position', 'absolute')
      .style('background', 'var(--tooltip-bg)')
      .style('color', 'var(--tooltip-text)')
      .style('padding', '6px 10px')
      .style('border-radius', '4px')
      .style('border', '1px solid var(--tooltip-border)')
      .style('box-shadow', 'var(--tooltip-shadow)')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('opacity', 0);

    const margin = {
      top: 30,
      right: 18,
      bottom: 62,
      left: 68,
    };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const x = d3.scaleBand()
      .domain(series.map((entry) => entry.key))
      .range([0, innerWidth])
      .padding(0.14);

    const maxClusterCount = d3.max(series, (entry) => entry.clusterCount) || 0;

    const y = d3.scaleLinear()
      .domain([0, maxClusterCount > 0 ? maxClusterCount * 1.16 : 1])
      .nice()
      .range([innerHeight, 0]);

    const g = svg
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    g.append('g')
      .call(d3.axisLeft(y).ticks(6).tickFormat(d3.format('d')))
      .call((axis) => axis.selectAll('line').attr('stroke', 'var(--chart-grid)'))
      .call((axis) => axis.selectAll('text').style('font-size', '13px'));

    const xAxis = g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(
        d3.axisBottom(x)
          .tickFormat((value) => seriesByKey.get(String(value))?.axisLabel || '')
          .tickSizeOuter(0)
      );

    xAxis.selectAll('text')
      .style('font-size', '12px')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.8rem');
    xAxis.selectAll('.tick text')
      .filter((value) => String(value) === GAP_TICK_KEY)
      .style('fill', 'var(--chart-muted)')
      .style('font-weight', 700)
      .style('letter-spacing', '0.12em');

    g.selectAll('rect')
      .data(series.filter((entry) => !entry.isGap))
      .enter()
      .append('rect')
      .attr('x', (entry) => x(entry.key))
      .attr('y', (entry) => y(entry.clusterCount))
      .attr('width', x.bandwidth())
      .attr('height', (entry) => innerHeight - y(entry.clusterCount))
      .attr('rx', 6)
      .attr('fill', CLUSTER_BAR_COLOR)
      .on('mouseover', function (event, entry) {
        d3.select(this).attr('fill', CLUSTER_BAR_HOVER_COLOR);
        tooltip
          .style('opacity', 1)
          .html(
            `There ${entry.clusterCount === 1 ? 'is' : 'are'} <strong>${entry.clusterCount}</strong> ` +
            `connected component${entry.clusterCount === 1 ? '' : 's'} of size ${entry.clusterSize},<br/>` +
            `accounting for ${entry.authorCount} author${entry.authorCount === 1 ? '' : 's'} in total.`
          );
      })
      .on('mousemove', function (event) {
        tooltip
          .style('left', `${event.pageX + 10}px`)
          .style('top', `${event.pageY - 28}px`);
      })
      .on('mouseout', function (event, entry) {
        d3.select(this).attr('fill', CLUSTER_BAR_COLOR);
        tooltip.style('opacity', 0);
      });

    g.selectAll('text.bar-label')
      .data(series.filter((entry) => entry.clusterCount > 0))
      .enter()
      .append('text')
      .attr('class', 'bar-label')
      .attr('x', (entry) => (x(entry.key) || 0) + x.bandwidth() / 2)
      .attr('y', (entry) => y(entry.clusterCount) - 8)
      .attr('text-anchor', 'middle')
      .style('font-size', '12px')
      .style('font-weight', 600)
      .style('fill', 'var(--chart-text)')
      .text((entry) => entry.clusterCount);

    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 46)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .text('Authors in connected component');

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -48)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .text('Number of connected components');

    return () => {
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.collaboration-cluster-tooltip').remove();
    };
  }, [data, height, width]);

  return <svg ref={ref} role="img" aria-label="Collaboration cluster size distribution" />;
}
