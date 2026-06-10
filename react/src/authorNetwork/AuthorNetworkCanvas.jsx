import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { renderProposalListHtml } from '../bipTooltipContent';
import {
  DEFAULT_EDGE_CURVE_DIRECTION,
  DEFAULT_EDGE_CURVE_STRENGTH,
  EDGE_STROKE_WIDTH_HOVER_DELTA,
  allowGraphZoomGesture,
  buildCanonicalEdgeKey,
  buildDisplayCollaborationComponents,
  createEdgeStrokeWidthScale,
} from './authorNetworkUtils';

export function AuthorNetworkCanvas({
  data,
  width,
  height,
  highlightAuthor,
  layoutMode,
  minClusterCollaborations,
  ecosystem,
  snapshotLabel,
  linkMode,
  importedLayout,
  physicsEnabledRef,
  simulationRef,
  redrawGraphRef,
  exportPayloadRef,
  updateExportPayloadRef,
  onlyCrossSource,
}) {
  const svgRef = useRef();

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.author-network-tooltip').remove();
    exportPayloadRef.current = null;
    simulationRef.current = null;
    redrawGraphRef.current = () => {};
    updateExportPayloadRef.current = () => {};

    const rawNodes = Array.isArray(data?.nodes) ? data.nodes : [];
    const rawEdges = Array.isArray(data?.edges) ? data.edges : [];

    if (rawNodes.length === 0) {
      return;
    }

    const nodes = rawNodes.map((node) => ({ ...node }));
    const links = rawEdges.map((edge) => ({ ...edge }));
    const nodeIds = new Set(nodes.map((node) => node.id));
    const adjacency = new Map(nodes.map((node) => [node.id, new Set()]));
    const getEdgeSourceId = (edge) => (typeof edge.source === 'object' ? edge.source.id : edge.source);
    const getEdgeTargetId = (edge) => (typeof edge.target === 'object' ? edge.target.id : edge.target);

    links.forEach((edge) => {
      if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
        return;
      }
      adjacency.get(edge.source).add(edge.target);
      adjacency.get(edge.target).add(edge.source);
    });

    const components = buildDisplayCollaborationComponents(nodes, adjacency);
    const clusterMeta = components.map((members, clusterIndex) => {
      const memberIds = new Set(members);
      const edgeCount = links.filter((edge) => (
        memberIds.has(getEdgeSourceId(edge)) && memberIds.has(getEdgeTargetId(edge))
      )).length;
      return { clusterId: clusterIndex, members, clusterSize: members.length, edgeCount };
    });

    const clusterByNodeId = new Map();
    clusterMeta.forEach((cluster) => {
      cluster.members.forEach((member) => {
        clusterByNodeId.set(member, {
          clusterId: cluster.clusterId,
          clusterSize: cluster.clusterSize,
          clusterCollaborations: cluster.edgeCount,
        });
      });
    });

    nodes.forEach((node) => {
      const cluster = clusterByNodeId.get(node.id) || { clusterId: -1, clusterSize: 1, clusterCollaborations: 0 };
      node.clusterId = cluster.clusterId;
      node.clusterSize = cluster.clusterSize;
      node.clusterCollaborations = cluster.clusterCollaborations;
    });

    const collaborationThreshold = Math.max(0, Number(String(minClusterCollaborations).trim() || '0') || 0);
    const visibleClusterIds = new Set(
      clusterMeta
        .filter((cluster) => cluster.edgeCount >= collaborationThreshold)
        .map((cluster) => cluster.clusterId)
    );
    const visibleNodes = nodes.filter((node) => visibleClusterIds.has(node.clusterId));
    const visibleNodeIds = new Set(visibleNodes.map((node) => node.id));
    const visibleLinks = links.filter((edge) => (
      visibleNodeIds.has(getEdgeSourceId(edge)) && visibleNodeIds.has(getEdgeTargetId(edge))
    ));
    const visibleClusters = clusterMeta.filter((cluster) => visibleClusterIds.has(cluster.clusterId));
    const importedPositions = importedLayout?.positions || null;
    const importedEdgeCurves = importedLayout?.edgeCurves || new Map();
    const importedPositionedNodeCount = importedPositions
      ? visibleNodes.filter((node) => importedPositions[String(node.id)]).length
      : 0;

    visibleNodes.forEach((node) => {
      const coords = importedPositions?.[String(node.id)];
      if (!coords) {
        return;
      }
      node.x = coords[0];
      node.y = coords[1];
      if (!physicsEnabledRef.current) {
        node.fx = coords[0];
        node.fy = coords[1];
      }
    });

    const clusterColor = d3.scaleOrdinal()
      .domain(visibleClusters.map((cluster) => cluster.clusterId))
      .range([
        '#2a6f97', '#bc4749', '#6a994e', '#7b2cbf', '#c77dff',
        '#f4a261', '#457b9d', '#e76f51', '#8d99ae', '#2b9348',
        '#ffb703', '#577590',
      ]);

    const normalizedHighlight = highlightAuthor.trim().toLowerCase();
    const matchedNodes = normalizedHighlight
      ? visibleNodes.filter((node) => node.id.toLowerCase().includes(normalizedHighlight))
      : [];
    const matchedIds = new Set(matchedNodes.map((node) => node.id));
    const exactMatch = normalizedHighlight
      ? visibleNodes.find((node) => node.id.toLowerCase() === normalizedHighlight)
      : null;

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    if (visibleNodes.length === 0) {
      svg
        .attr('width', width)
        .attr('height', height)
        .append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', 'var(--app-text-muted)')
        .style('font-size', '14px')
        .text('No clusters match the current collaboration filter.');
      return;
    }

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'author-network-tooltip')
      .style('position', 'absolute')
      .style('padding', '8px 12px')
      .style('background', 'var(--tooltip-bg)')
      .style('color', 'var(--tooltip-text)')
      .style('border', '1px solid var(--tooltip-border)')
      .style('border-radius', '6px')
      .style('box-shadow', 'var(--tooltip-shadow)')
      .style('font-size', '13px')
      .style('pointer-events', 'none')
      .style('max-width', '360px')
      .style('line-height', '1.45')
      .style('opacity', 0);

    const renderNodeTooltip = (entry) => {
      const authoredBips = Array.isArray(entry.bips) ? entry.bips : [];
      return (
        `<strong>${entry.id}</strong><br/>` +
        `Authored proposals: ${authoredBips.length}<br/>` +
        `Collaborations: ${entry.degree}<br/>` +
        (entry.degree > 0 ? `Connected component size: ${entry.clusterSize}<br/>` : '') +
        renderProposalListHtml(authoredBips, snapshotLabel, { emptyText: 'No authored proposals available.', ecosystem, linkMode })
      );
    };

    const renderEdgeTooltip = (edge) => {
      const sharedBips = Array.isArray(edge.bips) ? edge.bips : [];
      return (
        `<strong>${getEdgeSourceId(edge)}</strong> x <strong>${getEdgeTargetId(edge)}</strong><br/>` +
        `Shared proposals: ${sharedBips.length}<br/>` +
        renderProposalListHtml(sharedBips, snapshotLabel, { emptyText: 'No shared proposals available.', ecosystem, linkMode })
      );
    };

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const getNodeFill = (entry) => (
      Number(entry.degree || 0) === 0 ? '#111111' : clusterColor(entry.clusterId)
    );
    const getDefaultEdgeCurve = (edge) => ({
      source: String(getEdgeSourceId(edge)),
      target: String(getEdgeTargetId(edge)),
      direction: DEFAULT_EDGE_CURVE_DIRECTION,
      strength: DEFAULT_EDGE_CURVE_STRENGTH,
    });
    const getResolvedEdgeCurve = (edge) => (
      importedEdgeCurves.get(buildCanonicalEdgeKey(getEdgeSourceId(edge), getEdgeTargetId(edge))) || getDefaultEdgeCurve(edge)
    );
    const getSignedEdgeCurveStrength = (edge) => {
      const curve = getResolvedEdgeCurve(edge);
      const sourceId = String(getEdgeSourceId(edge));
      const targetId = String(getEdgeTargetId(edge));
      const orientationMatches = curve.source === sourceId && curve.target === targetId ? 1 : -1;
      return curve.direction * orientationMatches * curve.strength;
    };
    const shouldShowNodeLabel = (entry) => (
      matchedIds.has(entry.id)
      || Number(entry.bips?.length || 0) >= 3
      || Number(entry.degree || 0) >= 3
    );

    let pinnedInteraction = null;

    const bipsExtent = d3.extent(visibleNodes, (node) => (node.bips?.length || 0));
    const radius = d3.scaleSqrt()
      .domain([bipsExtent[0] || 0, bipsExtent[1] || 1])
      .range([6, 25]);

    const strokeWidth = createEdgeStrokeWidthScale(visibleLinks);
    const edgeStrokeWidth = (edge) => strokeWidth(Number(edge.weight || 1));

    const clusterAnchors = new Map();
    const clusterCount = Math.max(visibleClusters.length, 1);
    const anchorRadius = Math.min(width, height) * 0.28;
    visibleClusters.forEach((cluster, clusterIndex) => {
      const angle = (Math.PI * 2 * clusterIndex) / clusterCount - Math.PI / 2;
      clusterAnchors.set(cluster.clusterId, {
        x: width / 2 + Math.cos(angle) * anchorRadius,
        y: height / 2 + Math.sin(angle) * anchorRadius,
      });
    });

    const linkForce = d3.forceLink(visibleLinks).id((node) => node.id);
    const chargeForce = d3.forceManyBody();
    const collisionForce = d3.forceCollide().radius((node) => radius(node.bips?.length || 0) + 6);
    const centerForce = d3.forceCenter(width / 2, height / 2);
    const xForce = d3.forceX(width / 2).strength(0.04);
    const yForce = d3.forceY(height / 2).strength(0.04);

    if (layoutMode === 'clustered') {
      linkForce.distance(78).strength(0.45);
      chargeForce.strength(-140);
      xForce.x((node) => clusterAnchors.get(node.clusterId)?.x ?? width / 2).strength(0.22);
      yForce.y((node) => clusterAnchors.get(node.clusterId)?.y ?? height / 2).strength(0.22);
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

    const simulation = d3.forceSimulation(visibleNodes)
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
      .filter(allowGraphZoomGesture)
      .on('zoom', (event) => {
        root.attr('transform', event.transform);
      });

    svg.call(zoomBehavior);

    let link;
    let node;
    let labels;

    const applyDefaultLinkStyles = () => {
      link
        .attr('stroke', (edge) => clusterColor(clusterByNodeId.get(getEdgeSourceId(edge))?.clusterId ?? 0))
        .attr('stroke-opacity', (edge) => {
          if (!normalizedHighlight) {
            return 0.55;
          }
          return matchedIds.has(getEdgeSourceId(edge)) || matchedIds.has(getEdgeTargetId(edge)) ? 0.95 : 0.08;
        })
        .attr('stroke-width', edgeStrokeWidth);
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
          return isSelected ? edgeStrokeWidth(edge) + EDGE_STROKE_WIDTH_HOVER_DELTA : edgeStrokeWidth(edge);
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
        .attr('stroke-width', edgeStrokeWidth);
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
      .data(visibleLinks)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke', (edge) => clusterColor(clusterByNodeId.get(getEdgeSourceId(edge))?.clusterId ?? 0))
      .attr('stroke-opacity', (edge) => {
        if (!normalizedHighlight) {
          return 0.55;
        }
        return matchedIds.has(getEdgeSourceId(edge)) || matchedIds.has(getEdgeTargetId(edge)) ? 0.95 : 0.08;
      })
      .attr('stroke-width', edgeStrokeWidth)
      .on('mouseover', function (event, edge) {
        if (pinnedInteraction) {
          return;
        }
        d3.select(this)
          .attr('stroke', '#f4a261')
          .attr('stroke-opacity', 1)
          .attr('stroke-width', edgeStrokeWidth(edge) + EDGE_STROKE_WIDTH_HOVER_DELTA);
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
          .attr('stroke-width', edgeStrokeWidth(edge));
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, edge) {
        event.stopPropagation();
        pinnedInteraction = { type: 'edge', edge, pageX: event.pageX, pageY: event.pageY };
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
      .data(visibleNodes)
      .join('circle')
      .attr('r', (entry) => (
        matchedIds.has(entry.id)
          ? radius(entry.bips?.length || 0) + 5
          : radius(entry.bips?.length || 0)
      ))
      .attr('fill', (entry) => getNodeFill(entry))
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
        pinnedInteraction = { type: 'node', id: entry.id, entry, pageX: event.pageX, pageY: event.pageY };
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
            if (physicsEnabledRef.current && !event.active) {
              simulation.alphaTarget(0.3).restart();
            }
            entry.fx = entry.x;
            entry.fy = entry.y;
          })
          .on('drag', (event, entry) => {
            entry.fx = event.x;
            entry.fy = event.y;
            entry.x = event.x;
            entry.y = event.y;
            redrawGraphRef.current();
          })
          .on('end', (event, entry) => {
            if (physicsEnabledRef.current && !event.active) {
              simulation.alphaTarget(0);
            }
            entry.fx = null;
            entry.fy = null;
            redrawGraphRef.current();
          })
      );

    svg.on('click', () => {
      clearPinnedInteraction();
    });

    labels = root.append('g')
      .selectAll('text')
      .data(visibleNodes.filter(shouldShowNodeLabel))
      .join('text')
      .text((entry) => entry.id)
      .style('font-size', '11px')
      .style('fill', 'var(--chart-text)')
      .style('font-weight', (entry) => (matchedIds.has(entry.id) ? 700 : 400))
      .style('opacity', (entry) => {
        if (!normalizedHighlight) {
          return 1;
        }
        return shouldShowNodeLabel(entry) ? 1 : 0.2;
      })
      .style('paint-order', 'stroke')
      .style('stroke', 'var(--chart-outline)')
      .style('stroke-width', 3)
      .style('stroke-linecap', 'round')
      .style('stroke-linejoin', 'round');

    const updateExportPayload = () => {
      const positions = Object.fromEntries(
        visibleNodes.map((entry) => [
          String(entry.id),
          [
            Number.isFinite(entry.x) ? entry.x : (width / 2),
            Number.isFinite(entry.y) ? entry.y : (height / 2),
          ],
        ])
      );
      const edgeCurves = visibleLinks
        .map((edge) => getResolvedEdgeCurve(edge))
        .sort((left, right) => (
          left.source.localeCompare(right.source) || left.target.localeCompare(right.target)
        ));

      exportPayloadRef.current = {
        snapshot: snapshotLabel,
        network: 'authorship_collaboration',
        layout_mode: layoutMode,
        filter: {
          min_cluster_collaborations: collaborationThreshold,
          only_cross_source: Boolean(onlyCrossSource),
        },
        meta: { width, height, node_count: visibleNodes.length, edge_count: visibleLinks.length },
        positions,
        edge_curves: edgeCurves,
        nodes: Object.entries(positions).map(([id, [xCoord, yCoord]]) => ({ id, x: xCoord, y: yCoord })),
      };
    };

    const renderGraph = () => {
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
          const curveOffset = Math.min(24, Math.max(8, distance * 0.07)) * getSignedEdgeCurveStrength(edge);
          const controlX = midpointX + (normalX * curveOffset);
          const controlY = midpointY + (normalY * curveOffset);
          return `M ${sourceX},${sourceY} Q ${controlX},${controlY} ${targetX},${targetY}`;
        });

      node
        .attr('cx', (entry) => entry.x = Math.max(24, Math.min(width - 24, entry.x ?? (width / 2))))
        .attr('cy', (entry) => entry.y = Math.max(24, Math.min(height - 24, entry.y ?? (height / 2))));

      labels
        .attr('x', (entry) => entry.x + radius(entry.bips?.length || 0) + 4)
        .attr('y', (entry) => entry.y + 3);

      updateExportPayload();
    };

    simulationRef.current = simulation;
    redrawGraphRef.current = renderGraph;
    updateExportPayloadRef.current = updateExportPayload;

    let hasFocusedHighlight = false;
    simulation.on('tick', () => {
      renderGraph();
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

    if (physicsEnabledRef.current) {
      renderGraph();
    } else {
      if (!(importedPositions && importedPositionedNodeCount === visibleNodes.length)) {
        for (let iteration = 0; iteration < 140; iteration += 1) {
          simulation.tick();
        }
      }

      visibleNodes.forEach((entry) => {
        if (!importedPositions?.[String(entry.id)]) {
          return;
        }
        entry.fx = null;
        entry.fy = null;
      });
      renderGraph();
      simulation.alphaTarget(0);
      simulation.stop();
    }

    return () => {
      exportPayloadRef.current = null;
      if (simulationRef.current === simulation) {
        simulationRef.current = null;
      }
      redrawGraphRef.current = () => {};
      updateExportPayloadRef.current = () => {};
      simulation.stop();
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.author-network-tooltip').remove();
    };
  }, [data, ecosystem, height, highlightAuthor, importedLayout, layoutMode, linkMode, minClusterCollaborations, onlyCrossSource, snapshotLabel, width, exportPayloadRef, physicsEnabledRef, redrawGraphRef, simulationRef, updateExportPayloadRef]);

  return <svg ref={svgRef} role="img" />;
}
