import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import cloud from 'd3-cloud';

export const WordCloud = ({ words, width = 1250, height = 750 }) => {
  const containerRef = useRef();
  const svgRef = useRef();
  const [containerWidth, setContainerWidth] = useState(width);

  useEffect(() => {
    const element = containerRef.current;

    if (!element) {
      return undefined;
    }

    const updateWidth = () => {
      const nextWidth = element.clientWidth || width;
      setContainerWidth(nextWidth);
    };

    updateWidth();

    const observer = new ResizeObserver(updateWidth);
    observer.observe(element);

    return () => observer.disconnect();
  }, [width]);

  useEffect(() => {
    const svgElement = svgRef.current;
    const layoutWidth = Math.min(width, Math.max(containerWidth, 280));
    const layoutHeight = layoutWidth < 640
      ? Math.max(320, Math.round(layoutWidth * 0.72))
      : height;
    const isCompact = layoutWidth < 640;

    if (!words || words.length === 0) return;

    // Clear previous word cloud
    const svgRoot = d3.select(svgElement);
    svgRoot.selectAll('*').remove();
    d3.select('body').selectAll('.wordcloud-tooltip').remove(); // clean any previous tooltips

    const maxCount = d3.max(words, d => d.count);
    const sizeScale = d3.scaleLinear()
      .domain([0, maxCount])
      .range(isCompact ? [11, 34] : [15, 60]); // font size range

    // Assign consistent blue shades to each word, derived from the word text
    const coloredWords = words.map(d => {
      let hash = 0;
      for (let i = 0; i < d.word.length; i++) {
        hash = (hash * 31 + d.word.charCodeAt(i)) >>> 0;
      }
      const colorValue = (hash % 600) / 1000 + 0.4; // range [0.4, 1.0), avoids too-light shades
      return {
        text: d.word,
        count: d.count,
        size: sizeScale(d.count),
        color: d3.interpolateBlues(colorValue),
      };
    });

    // Layout
    const layout = cloud()
      .size([layoutWidth, layoutHeight])
      .words(coloredWords)
      .padding(isCompact ? 2 : 5)
      .rotate(() => (isCompact ? 0 : (Math.random() > 0.5 ? 0 : 90)))
      .font('Impact')
      .fontSize(d => d.size)
      .on('end', draw);

    layout.start();

    function draw(words) {
      // Tooltip
      const tooltip = d3.select('body')
        .append('div')
        .attr('class', 'wordcloud-tooltip')
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

      const svg = svgRoot
        .attr('width', layoutWidth)
        .attr('height', layoutHeight)
        .attr('viewBox', `0 0 ${layoutWidth} ${layoutHeight}`)
        .style('width', '100%')
        .style('height', 'auto')
        .style('display', 'block');

      svg.append('rect')
        .attr('width', layoutWidth)
        .attr('height', layoutHeight)
        .attr('fill', 'transparent')
        .style('cursor', 'grab');

      const viewport = svg.append('g');

      const cloudGroup = viewport
        .append('g')
        .attr('transform', `translate(${layoutWidth / 2}, ${layoutHeight / 2})`);

      const zoom = d3.zoom()
        .scaleExtent([0.6, 4])
        .on('start', () => {
          svg.style('cursor', 'grabbing');
        })
        .on('zoom', (event) => {
          viewport.attr('transform', event.transform);
        })
        .on('end', () => {
          svg.style('cursor', 'grab');
        });

      svg.call(zoom)
        .on('dblclick.zoom', null);

      svg.call(
        zoom.transform,
        d3.zoomIdentity
          .translate(isCompact ? layoutWidth * 0.08 : 0, isCompact ? layoutHeight * 0.04 : 0)
          .scale(1)
      );

      cloudGroup.selectAll('text')
        .data(words)
        .enter()
        .append('text')
        .style('font-family', 'Impact')
        .style('font-size', d => `${d.size}px`)
        .style('fill', d => d.color)
        .attr('text-anchor', 'middle')
        .attr('transform', d => `translate(${d.x}, ${d.y}) rotate(${d.rotate})`)
        .text(d => d.text)
        .on('mouseover', function (event, d) {
          d3.select(this)
            .transition().duration(200)
            .style('fill', 'var(--wordcloud-hover)')
            .style('font-size', `${d.size * 1.2}px`)
            .attr('stroke', 'var(--chart-contrast)')
            .attr('stroke-width', 1);

          tooltip
            .style('opacity', 1)
            .html(`<strong>${d.text}</strong><br/>Count: ${d.count}`);
        })
        .on('mousemove', function (event) {
          tooltip
            .style('left', `${event.pageX + 10}px`)
            .style('top', `${event.pageY - 28}px`);
        })
        .on('mouseout', function (event, d) {
          d3.select(this)
            .transition().duration(200)
            .style('fill', d.color)
            .style('font-size', `${d.size}px`)
            .attr('stroke', 'none');

          tooltip.style('opacity', 0);
        });
    }

    // Clean up
    return () => {
      svgRoot.selectAll('*').remove();
      d3.select('body').selectAll('.wordcloud-tooltip').remove();
    };
  }, [words, width, height, containerWidth]);

  return (
    <div ref={containerRef} style={{ width: '100%' }}>
      <svg ref={svgRef}></svg>
    </div>
  );
};
