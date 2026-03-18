import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { renderBipListHtml } from './bipTooltipContent';

export const AuthorCollaborationNetwork = ({
  data,
  width = 1200,
  height = 700,
  highlightAuthor = '',
  layoutMode = 'balanced',
}) => {
  const ref = useRef();

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.author-network-tooltip').remove();

    const rawNodes = Array.isArray(data?.nodes) ? data.nodes : [];
    const rawEdges = Array.isArray(data?.edges) ? data.edges : [];

    if (rawNodes.length === 0 || rawEdges.length === 0) {
      return;
    }

    const nodes = rawNodes.map((node) => ({ ...node }));
    const links = rawEdges.map((edge) => ({ ...edge }));
    const nodeIds = new Set(nodes.map((node) => node.id));
    const adjacency = new Map(nodes.map((node) => [node.id, new Set()]));

    links.forEach((edge) => {
      if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
        return;
      }
      adjacency.get(edge.source).add(edge.target);
      adjacency.get(edge.target).add(edge.source);
    });

    const components = [];
    const visited = new Set();
    nodes.forEach((node) => {
      if (visited.has(node.id)) {
        return;
      }

      const queue = [node.id];
      const members = [];
      visited.add(node.id);

      while (queue.length > 0) {
        const current = queue.shift();
        members.push(current);

        adjacency.get(current).forEach((neighbor) => {
          if (visited.has(neighbor)) {
            return;
          }
          visited.add(neighbor);
          queue.push(neighbor);
        });
      }

      components.push(members);
    });

    components.sort((left, right) => right.length - left.length);

    const clusterByNodeId = new Map();
    components.forEach((members, clusterIndex) => {
      members.forEach((member) => {
        clusterByNodeId.set(member, {
          clusterId: clusterIndex,
          clusterSize: members.length,
        });
      });
    });

    nodes.forEach((node) => {
      const cluster = clusterByNodeId.get(node.id) || { clusterId: -1, clusterSize: 1 };
      node.clusterId = cluster.clusterId;
      node.clusterSize = cluster.clusterSize;
    });

    const clusterColor = d3.scaleOrdinal()
      .domain(components.map((_, index) => index))
      .range([
        '#2a6f97',
        '#bc4749',
        '#6a994e',
        '#7b2cbf',
        '#c77dff',
        '#f4a261',
        '#457b9d',
        '#e76f51',
        '#8d99ae',
        '#2b9348',
        '#ffb703',
        '#577590',
      ]);

    const normalizedHighlight = highlightAuthor.trim().toLowerCase();
    const matchedNodes = normalizedHighlight
      ? nodes.filter((node) => node.id.toLowerCase().includes(normalizedHighlight))
      : [];
    const matchedIds = new Set(matchedNodes.map((node) => node.id));
    const exactMatch = normalizedHighlight
      ? nodes.find((node) => node.id.toLowerCase() === normalizedHighlight)
      : null;
    const getEdgeSourceId = (edge) => (typeof edge.source === 'object' ? edge.source.id : edge.source);
    const getEdgeTargetId = (edge) => (typeof edge.target === 'object' ? edge.target.id : edge.target);

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'author-network-tooltip')
      .style('position', 'absolute')
      .style('padding', '8px 12px')
      .style('background', '#1a1a1a')
      .style('color', '#f0f0f0')
      .style('border', '1px solid #555')
      .style('border-radius', '6px')
      .style('box-shadow', '0px 2px 6px rgba(0,0,0,0.4)')
      .style('font-size', '13px')
      .style('pointer-events', 'none')
      .style('max-width', '360px')
      .style('line-height', '1.45')
      .style('opacity', 0);

    const renderNodeTooltip = (entry) => {
      const authoredBips = Array.isArray(entry.bips) ? entry.bips : [];
      return (
        `<strong>${entry.id}</strong><br/>` +
        `Collaborators: ${entry.degree}<br/>` +
        `Cluster size: ${entry.clusterSize}<br/>` +
        `Authored BIPs: ${authoredBips.length}<br/>` +
        renderBipListHtml(authoredBips, { emptyText: 'No authored BIPs available.' })
      );
    };

    const renderEdgeTooltip = (edge) => {
      const sharedBips = Array.isArray(edge.bips) ? edge.bips : [];
      return (
        `<strong>${getEdgeSourceId(edge)}</strong> x <strong>${getEdgeTargetId(edge)}</strong><br/>` +
        `Shared BIPs: ${sharedBips.length}<br/>` +
        renderBipListHtml(sharedBips, { emptyText: 'No shared BIPs available.' })
      );
    };

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    let pinnedInteraction = null;

    const degreeExtent = d3.extent(nodes, (node) => Number(node.degree || 0));
    const radius = d3.scaleSqrt()
      .domain([degreeExtent[0] || 0, degreeExtent[1] || 1])
      .range([6, 18]);

    const weightExtent = d3.extent(links, (link) => Number(link.weight || 1));
    const strokeWidth = d3.scaleLinear()
      .domain([weightExtent[0] || 1, weightExtent[1] || 1])
      .range([1.2, 5]);

    const clusterAnchors = new Map();
    const clusterCount = Math.max(components.length, 1);
    const anchorRadius = Math.min(width, height) * 0.28;
    components.forEach((members, clusterIndex) => {
      const angle = (Math.PI * 2 * clusterIndex) / clusterCount - Math.PI / 2;
      clusterAnchors.set(clusterIndex, {
        x: width / 2 + Math.cos(angle) * anchorRadius,
        y: height / 2 + Math.sin(angle) * anchorRadius,
      });
    });

    const linkForce = d3.forceLink(links).id((node) => node.id);
    const chargeForce = d3.forceManyBody();
    const collisionForce = d3.forceCollide().radius((node) => radius(Number(node.degree || 0)) + 6);
    const centerForce = d3.forceCenter(width / 2, height / 2);
    const xForce = d3.forceX(width / 2).strength(0.04);
    const yForce = d3.forceY(height / 2).strength(0.04);

    if (layoutMode === 'clustered') {
      linkForce.distance(78).strength(0.45);
      chargeForce.strength(-140);
      xForce
        .x((node) => clusterAnchors.get(node.clusterId)?.x ?? width / 2)
        .strength(0.22);
      yForce
        .y((node) => clusterAnchors.get(node.clusterId)?.y ?? height / 2)
        .strength(0.22);
    } else if (layoutMode === 'spread') {
      linkForce.distance(145).strength(0.28);
      chargeForce.strength(-320);
      xForce.x(width / 2).strength(0.03);
      yForce.y(height / 2).strength(0.03);
    } else {
      linkForce.distance(92).strength(0.35);
      chargeForce.strength(-180);
      xForce.x(width / 2).strength(0.05);
      yForce.y(height / 2).strength(0.05);
    }

    const simulation = d3.forceSimulation(nodes)
      .force('link', linkForce)
      .force('charge', chargeForce)
      .force('center', centerForce)
      .force('x', xForce)
      .force('y', yForce)
      .force('collision', collisionForce);

    const root = svg
      .attr('width', width)
      .attr('height', height)
      .append('g');

    const zoomBehavior = d3.zoom()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        root.attr('transform', event.transform);
      });

    svg.call(zoomBehavior);

    let link;
    let node;

    const applyDefaultLinkStyles = () => {
      link
        .attr('stroke', (edge) => clusterColor(clusterByNodeId.get(getEdgeSourceId(edge))?.clusterId ?? 0))
        .attr('stroke-opacity', (edge) => {
          if (!normalizedHighlight) {
            return 0.55;
          }
          return matchedIds.has(getEdgeSourceId(edge)) || matchedIds.has(getEdgeTargetId(edge)) ? 0.95 : 0.08;
        })
        .attr('stroke-width', (edge) => strokeWidth(Number(edge.weight || 1)));
    };

    const applyDefaultNodeStyles = () => {
      node
        .attr('stroke', (entry) => (matchedIds.has(entry.id) ? '#f4a261' : '#fff'))
        .attr('stroke-width', (entry) => (matchedIds.has(entry.id) ? 3 : 1.5));
    };

    const applyPinnedEdgeStyles = (pinnedEdge) => {
      link
        .attr('stroke-opacity', (edge) => {
          const isSelected = getEdgeSourceId(edge) === getEdgeSourceId(pinnedEdge)
            && getEdgeTargetId(edge) === getEdgeTargetId(pinnedEdge);
          return isSelected ? 1 : 0.08;
        })
        .attr('stroke', (edge) => {
          const isSelected = getEdgeSourceId(edge) === getEdgeSourceId(pinnedEdge)
            && getEdgeTargetId(edge) === getEdgeTargetId(pinnedEdge);
          return isSelected ? '#f4a261' : clusterColor(clusterByNodeId.get(getEdgeSourceId(edge))?.clusterId ?? 0);
        })
        .attr('stroke-width', (edge) => {
          const isSelected = getEdgeSourceId(edge) === getEdgeSourceId(pinnedEdge)
            && getEdgeTargetId(edge) === getEdgeTargetId(pinnedEdge);
          return isSelected ? strokeWidth(Number(edge.weight || 1)) + 1.5 : strokeWidth(Number(edge.weight || 1));
        });
    };

    const applyPinnedNodeStyles = (entry) => {
      node
        .attr('stroke', (candidate) => (candidate.id === entry.id ? '#f4a261' : (matchedIds.has(candidate.id) ? '#f4a261' : '#fff')))
        .attr('stroke-width', (candidate) => (candidate.id === entry.id ? 3.5 : (matchedIds.has(candidate.id) ? 3 : 1.5)));

      link
        .attr('stroke-opacity', (edge) => (
          getEdgeSourceId(edge) === entry.id || getEdgeTargetId(edge) === entry.id ? 0.95 : 0.12
        ))
        .attr('stroke', (edge) => (
          getEdgeSourceId(edge) === entry.id || getEdgeTargetId(edge) === entry.id
            ? '#f4a261'
            : clusterColor(clusterByNodeId.get(getEdgeSourceId(edge))?.clusterId ?? 0)
        ))
        .attr('stroke-width', (edge) => strokeWidth(Number(edge.weight || 1)));
    };

    const clearPinnedInteraction = () => {
      pinnedInteraction = null;
      tooltip
        .style('opacity', 0)
        .style('pointer-events', 'none');
      applyDefaultNodeStyles();
      applyDefaultLinkStyles();
    };

    link = root.append('g')
      .attr('stroke', '#90a4ae')
      .attr('stroke-opacity', 0.55)
      .selectAll('path')
      .data(links)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke', (edge) => clusterColor(clusterByNodeId.get(getEdgeSourceId(edge))?.clusterId ?? 0))
      .attr('stroke-opacity', (edge) => {
        if (!normalizedHighlight) {
          return 0.55;
        }
        return matchedIds.has(getEdgeSourceId(edge)) || matchedIds.has(getEdgeTargetId(edge)) ? 0.95 : 0.08;
      })
      .attr('stroke-width', (edge) => strokeWidth(Number(edge.weight || 1)))
      .on('mouseover', function (event, edge) {
        if (pinnedInteraction) {
          return;
        }

        d3.select(this)
          .attr('stroke', '#f4a261')
          .attr('stroke-opacity', 1)
          .attr('stroke-width', strokeWidth(Number(edge.weight || 1)) + 1.5);

        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderEdgeTooltip(edge));
      })
      .on('mousemove', function (event) {
        if (pinnedInteraction) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function (event, edge) {
        if (pinnedInteraction) {
          return;
        }

        d3.select(this)
          .attr('stroke', clusterColor(clusterByNodeId.get(getEdgeSourceId(edge))?.clusterId ?? 0))
          .attr('stroke-opacity', () => {
            if (!normalizedHighlight) {
              return 0.55;
            }
            return matchedIds.has(getEdgeSourceId(edge)) || matchedIds.has(getEdgeTargetId(edge)) ? 0.95 : 0.08;
          })
          .attr('stroke-width', strokeWidth(Number(edge.weight || 1)));

        tooltip.style('opacity', 0);
      })
      .on('click', function (event, edge) {
        event.stopPropagation();
        pinnedInteraction = {
          type: 'edge',
          edge,
          pageX: event.pageX,
          pageY: event.pageY,
        };
        applyDefaultNodeStyles();
        applyDefaultLinkStyles();
        applyPinnedEdgeStyles(edge);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderEdgeTooltip(edge));
        setTooltipPosition(event.pageX, event.pageY);
      });

    node = root.append('g')
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', (entry) => (
        matchedIds.has(entry.id)
          ? radius(Number(entry.degree || 0)) + 5
          : radius(Number(entry.degree || 0))
      ))
      .attr('fill', (entry) => clusterColor(entry.clusterId))
      .attr('fill-opacity', (entry) => {
        if (!normalizedHighlight) {
          return 0.92;
        }
        return matchedIds.has(entry.id) ? 1 : 0.2;
      })
      .attr('stroke', (entry) => (matchedIds.has(entry.id) ? '#f4a261' : '#fff'))
      .attr('stroke-width', (entry) => (matchedIds.has(entry.id) ? 3 : 1.5))
      .on('mouseover', function (event, entry) {
        if (pinnedInteraction) {
          return;
        }

        d3.select(this)
          .attr('stroke', '#f4a261')
          .attr('stroke-width', 3);

        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderNodeTooltip(entry));

        link
          .attr('stroke-opacity', (edge) => (
            getEdgeSourceId(edge) === entry.id || getEdgeTargetId(edge) === entry.id ? 0.95 : 0.12
          ))
          .attr('stroke', (edge) => (
            getEdgeSourceId(edge) === entry.id || getEdgeTargetId(edge) === entry.id
              ? '#f4a261'
              : clusterColor(clusterByNodeId.get(getEdgeSourceId(edge))?.clusterId ?? 0)
          ));
      })
      .on('mousemove', function (event) {
        if (pinnedInteraction) {
          return;
        }
        setTooltipPosition(event.pageX, event.pageY);
      })
      .on('mouseout', function () {
        if (pinnedInteraction) {
          return;
        }

        d3.select(this)
          .attr('stroke', (entry) => (matchedIds.has(entry.id) ? '#f4a261' : '#fff'))
          .attr('stroke-width', (entry) => (matchedIds.has(entry.id) ? 3 : 1.5));

        tooltip.style('opacity', 0);
        applyDefaultLinkStyles();
      })
      .on('click', function (event, entry) {
        event.stopPropagation();
        pinnedInteraction = {
          type: 'node',
          id: entry.id,
          entry,
          pageX: event.pageX,
          pageY: event.pageY,
        };
        applyDefaultNodeStyles();
        applyDefaultLinkStyles();
        applyPinnedNodeStyles(entry);
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'auto')
          .html(renderNodeTooltip(entry));
        setTooltipPosition(event.pageX, event.pageY);
      })
      .call(
        d3.drag()
          .on('start', (event, entry) => {
            if (!event.active) {
              simulation.alphaTarget(0.3).restart();
            }
            entry.fx = entry.x;
            entry.fy = entry.y;
          })
          .on('drag', (event, entry) => {
            entry.fx = event.x;
            entry.fy = event.y;
          })
          .on('end', (event, entry) => {
            if (!event.active) {
              simulation.alphaTarget(0);
            }
            entry.fx = null;
            entry.fy = null;
          })
      );

    svg.on('click', () => {
      clearPinnedInteraction();
    });

    const labels = root.append('g')
      .selectAll('text')
      .data(nodes.filter((entry) => Number(entry.degree || 0) >= 3 || matchedIds.has(entry.id)))
      .join('text')
      .text((entry) => entry.id)
      .style('font-size', '11px')
      .style('fill', '#1f2933')
      .style('font-weight', (entry) => (matchedIds.has(entry.id) ? 700 : 400))
      .style('opacity', (entry) => {
        if (!normalizedHighlight) {
          return 1;
        }
        return matchedIds.has(entry.id) || Number(entry.degree || 0) >= 3 ? 1 : 0.2;
      })
      .style('paint-order', 'stroke')
      .style('stroke', '#ffffff')
      .style('stroke-width', 3)
      .style('stroke-linecap', 'round')
      .style('stroke-linejoin', 'round');

    let hasFocusedHighlight = false;
    simulation.on('tick', () => {
      link
        .attr('d', (edge) => {
          const sourceX = edge.source.x;
          const sourceY = edge.source.y;
          const targetX = edge.target.x;
          const targetY = edge.target.y;
          const dx = targetX - sourceX;
          const dy = targetY - sourceY;
          const distance = Math.sqrt((dx * dx) + (dy * dy)) || 1;
          const midpointX = (sourceX + targetX) / 2;
          const midpointY = (sourceY + targetY) / 2;
          const normalX = -dy / distance;
          const normalY = dx / distance;
          const curveOffset = Math.min(24, Math.max(8, distance * 0.07));
          const controlX = midpointX + (normalX * curveOffset);
          const controlY = midpointY + (normalY * curveOffset);
          return `M ${sourceX},${sourceY} Q ${controlX},${controlY} ${targetX},${targetY}`;
        });

      node
        .attr('cx', (entry) => entry.x = Math.max(24, Math.min(width - 24, entry.x)))
        .attr('cy', (entry) => entry.y = Math.max(24, Math.min(height - 24, entry.y)));

      labels
        .attr('x', (entry) => entry.x + radius(Number(entry.degree || 0)) + 4)
        .attr('y', (entry) => entry.y + 3);

      if (
        exactMatch
        && !hasFocusedHighlight
        && Number.isFinite(exactMatch.x)
        && Number.isFinite(exactMatch.y)
      ) {
        const scale = 1.8;
        const transform = d3.zoomIdentity
          .translate(width / 2, height / 2)
          .scale(scale)
          .translate(-exactMatch.x, -exactMatch.y);
        svg
          .transition()
          .duration(500)
          .call(zoomBehavior.transform, transform);
        hasFocusedHighlight = true;
      }
    });

    return () => {
      simulation.stop();
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.author-network-tooltip').remove();
    };
  }, [data, width, height, highlightAuthor, layoutMode]);

  return <svg ref={ref} role="img"  />;
};
