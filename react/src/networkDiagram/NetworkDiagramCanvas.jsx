import * as d3 from 'd3';
import { useEffect, useRef } from 'react';
import { buildProposalRefKeySet, nodeRefKey } from '../dashboard/dashboardData';
import { formatProposalReference, getProposalUrl, normalizeProposalId } from '../proposalLinks';
import { getClassificationColorMap } from '../classificationColors';
import {
  ACTIVE_LINK_WIDTH,
  DEFAULT_EDGE_COLORS,
  DEFAULT_LINK_WIDTH,
  DIFFERENTIAL_EDGE_COLORS,
  PINNED_LINK_WIDTH,
  PREAMBLE_EXTRACTED,
  allowGraphZoomGesture,
  edgeGraphSourceId,
  edgeGraphTargetId,
  edgeSourceProposalId,
  edgeSourceSourceId,
  edgeTargetProposalId,
  edgeTargetSourceId,
  formatRelationTypeLabel,
  getLinkTypeLabel,
  getPreambleRelationDasharray,
  getPreambleRelationStroke,
  getPreambleRelationTypes,
  nodeGraphId,
  normalizeCategory,
  getSourceScopedEcosystem,
} from './networkDiagramUtils';

export function NetworkDiagramCanvas({
  width,
  height,
  nodes,
  links,
  proposalFilterIds,
  includeConnections,
  includeThresholdConnections,
  minRelations,
  highlightProposal,
  ecosystem,
  snapshotLabel,
  linkMode,
  colorBy,
  linkType,
  baselineType,
  layoutMode,
  isDifferentialMode,
  onlyCrossSource,
  importedLayout,
  physicsEnabledRef,
  simulationRef,
  redrawGraphRef,
  exportPayloadRef,
  updateExportPayloadRef,
  legendRef,
}) {
  const svgRef = useRef();

  useEffect(() => {
    const sanitizePatternToken = (value) => String(value || '')
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'unknown';

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.dependency-network-tooltip').remove();
    exportPayloadRef.current = null;
    simulationRef.current = null;
    redrawGraphRef.current = () => {};
    updateExportPayloadRef.current = () => {};

    if (nodes.length === 0) {
      return;
    }

    const allNodes = nodes.map((node) => ({ ...node, graphId: nodeGraphId(node) }));
    const nodeById = new Map(allNodes.map((node) => [nodeGraphId(node), node]));
    const allLinks = links
      .filter((edge) => nodeById.has(edgeGraphSourceId(edge)) && nodeById.has(edgeGraphTargetId(edge)))
      .map((edge) => ({
        ...edge,
        source: edgeGraphSourceId(edge),
        target: edgeGraphTargetId(edge),
        sourceGraphId: edgeGraphSourceId(edge),
        targetGraphId: edgeGraphTargetId(edge),
      }));

    const requestedRefs = (proposalFilterIds || []).filter((value) => value && typeof value === 'object');
    const requestedRefKeys = buildProposalRefKeySet(requestedRefs);
    const requestedIds = new Set(
      (proposalFilterIds || [])
        .filter((value) => !value || typeof value !== 'object')
        .map((value) => String(value))
    );
    const hasFilter = requestedRefKeys.size > 0 || requestedIds.size > 0;
    let displayedNodeIds = new Set(allNodes.map((node) => nodeGraphId(node)));
    let localLinks = allLinks;

    if (hasFilter) {
      const matchedFilterNodeIds = new Set(
        allNodes
          .filter((node) => {
            const rawNodeId = String(node.id);
            const normalizedNodeId = normalizeProposalId(node.id, ecosystem);
            const unpaddedNumericNodeId = /^\d+$/.test(rawNodeId) ? String(Number(rawNodeId)) : rawNodeId;
            return (
              requestedRefKeys.has(nodeRefKey(node, ecosystem))
              || requestedIds.has(normalizedNodeId)
              || requestedIds.has(rawNodeId)
              || requestedIds.has(unpaddedNumericNodeId)
            );
          })
          .map((node) => nodeGraphId(node))
      );

      if (includeConnections) {
        displayedNodeIds = new Set(matchedFilterNodeIds);
        localLinks = allLinks.filter((edge) => {
          const sourceIncluded = matchedFilterNodeIds.has(edgeGraphSourceId(edge));
          const targetIncluded = matchedFilterNodeIds.has(edgeGraphTargetId(edge));
          if (sourceIncluded || targetIncluded) {
            displayedNodeIds.add(edgeGraphSourceId(edge));
            displayedNodeIds.add(edgeGraphTargetId(edge));
            return true;
          }
          return false;
        });
      } else {
        displayedNodeIds = matchedFilterNodeIds;
        localLinks = allLinks.filter((edge) => (
          displayedNodeIds.has(edgeGraphSourceId(edge)) && displayedNodeIds.has(edgeGraphTargetId(edge))
        ));
      }
    }

    const localNodes = allNodes.filter((node) => displayedNodeIds.has(nodeGraphId(node)));
    if (localNodes.length === 0) {
      return;
    }

    const adjacency = new Map(localNodes.map((node) => [nodeGraphId(node), new Set()]));
    const degreeById = new Map(localNodes.map((node) => [nodeGraphId(node), 0]));
    const incomingById = new Map(localNodes.map((node) => [nodeGraphId(node), 0]));
    const outgoingById = new Map(localNodes.map((node) => [nodeGraphId(node), 0]));

    localLinks.forEach((edge) => {
      const sourceId = edgeGraphSourceId(edge);
      const targetId = edgeGraphTargetId(edge);
      adjacency.get(sourceId)?.add(targetId);
      adjacency.get(targetId)?.add(sourceId);
      degreeById.set(sourceId, (degreeById.get(sourceId) || 0) + 1);
      degreeById.set(targetId, (degreeById.get(targetId) || 0) + 1);
      outgoingById.set(sourceId, (outgoingById.get(sourceId) || 0) + 1);
      incomingById.set(targetId, (incomingById.get(targetId) || 0) + 1);
    });

    localNodes.forEach((node) => {
      const nId = nodeGraphId(node);
      node.degree = degreeById.get(nId) || 0;
      node.incomingDegree = incomingById.get(nId) || 0;
      node.outgoingDegree = outgoingById.get(nId) || 0;
    });

    const relationThreshold = Math.max(0, Number(String(minRelations).trim() || '0') || 0);
    const thresholdMatchedNodeIds = new Set(
      localNodes
        .filter((node) => Number(node.degree || 0) >= relationThreshold)
        .map((node) => nodeGraphId(node))
    );
    let relationFilteredNodeIds = thresholdMatchedNodeIds;
    let filteredLinks = localLinks.filter((edge) => (
      relationFilteredNodeIds.has(edgeGraphSourceId(edge)) && relationFilteredNodeIds.has(edgeGraphTargetId(edge))
    ));

    if (includeThresholdConnections && thresholdMatchedNodeIds.size > 0) {
      relationFilteredNodeIds = new Set(thresholdMatchedNodeIds);
      filteredLinks = localLinks.filter((edge) => {
        const sourceMatched = thresholdMatchedNodeIds.has(edgeGraphSourceId(edge));
        const targetMatched = thresholdMatchedNodeIds.has(edgeGraphTargetId(edge));
        if (sourceMatched || targetMatched) {
          relationFilteredNodeIds.add(edgeGraphSourceId(edge));
          relationFilteredNodeIds.add(edgeGraphTargetId(edge));
          return true;
        }
        return false;
      });
    }

    const filteredNodes = localNodes.filter((node) => relationFilteredNodeIds.has(nodeGraphId(node)));

    if (filteredNodes.length === 0) {
      exportPayloadRef.current = null;
      svg
        .attr('width', width)
        .attr('height', height)
        .append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', 'var(--app-text-muted)')
        .style('font-size', '14px')
        .text('No proposals match the current relations filter.');
      return;
    }

    const presentSourceIds = Array.from(
      new Set(
        filteredNodes
          .map((node) => String(node.source || '').trim())
          .filter(Boolean)
      )
    );
    const orderedVisibleSourceIds = [
      ...(ecosystem?.sourceOrder || []).filter((sourceId) => presentSourceIds.includes(sourceId)),
      ...presentSourceIds.filter((sourceId) => !(ecosystem?.sourceOrder || []).includes(sourceId)),
    ];
    const multiSourcePatternsEnabled = orderedVisibleSourceIds.length > 1;
    const sourcePatternKindById = new Map(
      orderedVisibleSourceIds.map((sourceId, index) => {
        if (!multiSourcePatternsEnabled || index === 0) {
          return [sourceId, 'solid'];
        }
        if (index === 1) {
          return [sourceId, 'diagonal'];
        }
        if (index === 2) {
          return [sourceId, 'dotted'];
        }
        return [sourceId, 'solid'];
      })
    );

    const importedPositions = importedLayout?.positions || null;
    let importedPositionedNodeCount = 0;
    filteredNodes.forEach((node) => {
      const coords = importedPositions?.[nodeGraphId(node)] || importedPositions?.[String(node.id)];
      if (!coords) {
        return;
      }
      node.x = coords[0];
      node.y = coords[1];
      importedPositionedNodeCount += 1;
    });

    const highlightText = String(highlightProposal || '').trim();
    const searchMatchedIds = highlightText
      ? new Set(
        filteredNodes
          .filter((node) => {
            const nodeEcosystem = getSourceScopedEcosystem(ecosystem, node.source);
            return normalizeProposalId(node.id, nodeEcosystem) === normalizeProposalId(highlightText, nodeEcosystem);
          })
          .map((node) => nodeGraphId(node))
      )
      : new Set();

    const fallbackLabel = `Unknown ${colorBy.charAt(0).toUpperCase()}${colorBy.slice(1)}`;
    const allGroups = Array.from(new Set(allNodes.map((node) => normalizeCategory(node[colorBy], fallbackLabel))));
    const colorMap = getClassificationColorMap(colorBy, allGroups);
    const color = d3.scaleOrdinal()
      .domain(allGroups)
      .range(allGroups.map((group) => colorMap[group]));

    filteredNodes.forEach((node) => {
      node.colorGroup = normalizeCategory(node[colorBy], fallbackLabel);
    });

    const nodePatternId = (sourceId, groupLabel, patternKind) => (
      `dependency-node-pattern-${patternKind}-${sanitizePatternToken(sourceId)}-${sanitizePatternToken(groupLabel)}`
    );
    const getNodePatternKind = (entry) => sourcePatternKindById.get(String(entry.source || '').trim()) || 'solid';
    const getNodeFill = (entry) => {
      const groupLabel = normalizeCategory(entry[colorBy], fallbackLabel);
      const fillColor = color(groupLabel);
      const patternKind = getNodePatternKind(entry);
      if (!multiSourcePatternsEnabled || patternKind === 'solid') {
        return fillColor;
      }
      return `url(#${nodePatternId(String(entry.source || ''), groupLabel, patternKind)})`;
    };
    const preambleRelationTypes = getPreambleRelationTypes(links);

    const getEdgeColor = (edge) => {
      if (!isDifferentialMode) {
        if (linkType === PREAMBLE_EXTRACTED) {
          return getPreambleRelationStroke();
        }
        return DEFAULT_EDGE_COLORS[edge.relationType] || '#607d8b';
      }
      return DIFFERENTIAL_EDGE_COLORS[edge.comparisonStatus] || DIFFERENTIAL_EDGE_COLORS.approach_only;
    };

    const getEdgeMarkerId = (edge) => {
      if (!isDifferentialMode) {
        return `dependency-arrow-${edge.relationType}`;
      }
      return `dependency-arrow-${edge.comparisonStatus}`;
    };

    const getEdgeDasharray = (edge) => {
      if (isDifferentialMode) {
        return edge.comparisonStatus === 'baseline_only' ? '7 5' : null;
      }
      if (linkType !== PREAMBLE_EXTRACTED) {
        return null;
      }
      return getPreambleRelationDasharray(edge.relationType, preambleRelationTypes);
    };

    const updateExportPayload = () => {
      const exportedNodes = filteredNodes.map((entry) => ({
        id: String(entry.id),
        source: entry.source || null,
        graph_id: nodeGraphId(entry),
        x: Number(entry.x || 0),
        y: Number(entry.y || 0),
        degree: Number(entry.degree || 0),
        incomingDegree: Number(entry.incomingDegree || 0),
        outgoingDegree: Number(entry.outgoingDegree || 0),
        group: String(entry.colorGroup || ''),
        layer: entry.layer || null,
        status: entry.status || null,
        type: entry.type || null,
      }));

      exportPayloadRef.current = {
        snapshot: snapshotLabel || null,
        exported_at: new Date().toISOString(),
        width,
        height,
        color_by: colorBy,
        link_type: linkType,
        baseline_type: isDifferentialMode ? baselineType : null,
        layout_mode: layoutMode,
        is_differential_mode: isDifferentialMode,
        filter: {
          proposal_ids: (proposalFilterIds || []).map((value) => {
            if (value && typeof value === 'object') {
              return formatProposalReference(value.id, getSourceScopedEcosystem(ecosystem, value.source));
            }
            return formatProposalReference(value, ecosystem);
          }),
          include_connections: Boolean(includeConnections),
          min_relations: relationThreshold,
          include_threshold_connections: Boolean(includeThresholdConnections),
          only_cross_source: Boolean(onlyCrossSource),
        },
        nodes: exportedNodes,
        links: filteredLinks.map((edge) => ({
          source: edgeSourceProposalId(edge),
          target: edgeTargetProposalId(edge),
          source_source: edgeSourceSourceId(edge) || null,
          target_source: edgeTargetSourceId(edge) || null,
          source_graph_id: edgeGraphSourceId(edge),
          target_graph_id: edgeGraphTargetId(edge),
          relation_type: edge.relationType || null,
          comparison_status: edge.comparisonStatus || 'approach_only',
        })),
        positions: Object.fromEntries(
          exportedNodes.map((entry) => [String(entry.graph_id), [entry.x, entry.y]])
        ),
      };
    };

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const defs = svg.append('defs');
    if (multiSourcePatternsEnabled) {
      orderedVisibleSourceIds.forEach((sourceId) => {
        const patternKind = sourcePatternKindById.get(sourceId) || 'solid';
        if (patternKind === 'solid') {
          return;
        }

        allGroups.forEach((groupLabel) => {
          const fillColor = color(groupLabel);
          const pattern = defs
            .append('pattern')
            .attr('id', nodePatternId(sourceId, groupLabel, patternKind))
            .attr('patternUnits', 'userSpaceOnUse')
            .attr('width', 8)
            .attr('height', 8);

          pattern
            .append('rect')
            .attr('width', 8)
            .attr('height', 8)
            .attr('fill', fillColor);

          if (patternKind === 'diagonal') {
            pattern
              .append('path')
              .attr('d', 'M-2,2 l4,-4 M0,8 l8,-8 M6,10 l4,-4')
              .attr('stroke', 'rgba(255,255,255,0.78)')
              .attr('stroke-width', 1.35)
              .attr('stroke-linecap', 'round');
          }

          if (patternKind === 'dotted') {
            [[2, 2], [6, 6]].forEach(([cx, cy]) => {
              pattern
                .append('circle')
                .attr('cx', cx)
                .attr('cy', cy)
                .attr('r', 1.15)
                .attr('fill', 'rgba(255,255,255,0.8)');
            });
          }
        });
      });
    }

    const markerDefinitions = Array.from(
      new Map(filteredLinks.map((edge) => [getEdgeMarkerId(edge), getEdgeColor(edge)])).entries()
    );
    markerDefinitions.forEach(([markerId, fillColor]) => {
      defs
        .append('marker')
        .attr('id', markerId)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 14)
        .attr('refY', 0)
        .attr('orient', 'auto')
        .attr('markerWidth', 4.5)
        .attr('markerHeight', 4.5)
        .append('path')
        .attr('d', 'M 0,-5 L 10,0 L 0,5')
        .attr('fill', fillColor);
    });

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'dependency-network-tooltip')
      .style('position', 'absolute')
      .style('padding', '8px 12px')
      .style('background', 'var(--tooltip-bg)')
      .style('color', 'var(--tooltip-text)')
      .style('border', '1px solid var(--tooltip-border)')
      .style('border-radius', '6px')
      .style('box-shadow', 'var(--tooltip-shadow)')
      .style('font-size', '13px')
      .style('pointer-events', 'none')
      .style('line-height', '1.45')
      .style('opacity', 0);

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const renderNodeTooltip = (entry) => {
      const nodeEcosystem = getSourceScopedEcosystem(ecosystem, entry.source);
      return (
        `<strong><a href="${getProposalUrl(entry.id, snapshotLabel, { linkMode }, nodeEcosystem)}" target="_blank" rel="noreferrer">${formatProposalReference(entry.id, nodeEcosystem)}</a></strong><br/>` +
        `Outgoing: ${entry.outgoingDegree}<br/>` +
        `Incoming: ${entry.incomingDegree}<br/>` +
        `Layer: ${entry.layer || 'Unknown'}<br/>` +
        `Status: ${entry.status || 'Unknown'}<br/>` +
        `Type: ${entry.type || 'Unknown'}`
      );
    };

    const renderEdgeTooltip = (edge) => {
      const sourceEcosystem = getSourceScopedEcosystem(ecosystem, edgeSourceSourceId(edge));
      const targetEcosystem = getSourceScopedEcosystem(ecosystem, edgeTargetSourceId(edge));
      const sourceId = edgeSourceProposalId(edge);
      const targetId = edgeTargetProposalId(edge);
      return (
        `<strong><a href="${getProposalUrl(sourceId, snapshotLabel, { linkMode }, sourceEcosystem)}" target="_blank" rel="noreferrer">${formatProposalReference(sourceId, sourceEcosystem)}</a></strong>` +
        ` &rarr; ` +
        `<strong><a href="${getProposalUrl(targetId, snapshotLabel, { linkMode }, targetEcosystem)}" target="_blank" rel="noreferrer">${formatProposalReference(targetId, targetEcosystem)}</a></strong><br/>` +
        `Type: ${
          !isDifferentialMode
            ? (
              edge.relationType === 'body_extracted_regex'
                ? 'Regex-Extracted Dependency'
                : edge.relationType === 'body_extracted_llm'
                  ? 'LLM-Extracted Dependency'
                  : formatRelationTypeLabel(edge.relationType)
            )
            : (
              edge.comparisonStatus === 'overlap'
                ? `${getLinkTypeLabel(linkType)} + ${getLinkTypeLabel(baselineType)}`
                : edge.comparisonStatus === 'baseline_only'
                  ? `${getLinkTypeLabel(baselineType)} only`
                  : `${getLinkTypeLabel(linkType)} only`
            )
        }` +
        (
          !isDifferentialMode
            ? ''
            : `<br/>Comparison: ${
              edge.comparisonStatus === 'overlap'
                ? `Exists in baseline (${getLinkTypeLabel(baselineType)})`
                : edge.comparisonStatus === 'baseline_only'
                  ? `Missing from ${getLinkTypeLabel(linkType)}`
                  : `Only in ${getLinkTypeLabel(linkType)}`
            }`
        )
      );
    };

    const getWordCount = (node) => {
      const wl = node.word_list;
      if (!wl || typeof wl !== 'object') return 0;
      return Object.values(wl).reduce((sum, count) => sum + Number(count || 0), 0);
    };
    const wordCountExtent = d3.extent(filteredNodes, getWordCount);
    const radius = d3.scaleSqrt()
      .domain([wordCountExtent[0] || 0, wordCountExtent[1] || 1])
      .range([7, 20]);
    const getNodeRadius = (entry) => (
      searchMatchedIds.has(nodeGraphId(entry))
        ? radius(getWordCount(entry)) + 5
        : radius(getWordCount(entry))
    );

    const groupAnchors = new Map();
    const anchorRadius = Math.min(width, height) * 0.24;
    allGroups.forEach((group, index) => {
      const angle = ((Math.PI * 2 * index) / Math.max(allGroups.length, 1)) - (Math.PI / 2);
      groupAnchors.set(group, {
        x: width / 2 + Math.cos(angle) * anchorRadius,
        y: height / 2 + Math.sin(angle) * anchorRadius,
      });
    });

    const linkForce = d3.forceLink(filteredLinks).id((node) => nodeGraphId(node));
    const chargeForce = d3.forceManyBody();
    const collisionForce = d3.forceCollide().radius((node) => radius(Number(node.degree || 0)) + 10);
    const centerForce = d3.forceCenter(width / 2, height / 2);
    const xForce = d3.forceX(width / 2).strength(0.05);
    const yForce = d3.forceY(height / 2).strength(0.05);

    if (layoutMode === 'clustered') {
      linkForce.distance(92).strength(0.28);
      chargeForce.strength(-220);
      xForce.x((node) => groupAnchors.get(node.colorGroup)?.x ?? width / 2).strength(0.22);
      yForce.y((node) => groupAnchors.get(node.colorGroup)?.y ?? height / 2).strength(0.22);
    } else if (layoutMode === 'spread') {
      linkForce.distance(155).strength(0.22);
      chargeForce.strength(-360);
      xForce.x(width / 2).strength(0.03);
      yForce.y(height / 2).strength(0.03);
    } else {
      linkForce.distance(108).strength(0.26);
      chargeForce.strength(-250);
      xForce.x(width / 2).strength(0.05);
      yForce.y(height / 2).strength(0.05);
    }

    const simulation = d3.forceSimulation(filteredNodes)
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

    let pinnedInteraction = null;
    let link;
    let node;
    let labels;
    let renderGraph = () => {};

    const applyDefaultLinkStyles = () => {
      link
        .attr('stroke', (edge) => getEdgeColor(edge))
        .attr('stroke-opacity', (edge) => {
          if (searchMatchedIds.size === 0) {
            return 0.72;
          }
          return searchMatchedIds.has(edgeGraphSourceId(edge)) || searchMatchedIds.has(edgeGraphTargetId(edge)) ? 0.95 : 0.08;
        })
        .attr('stroke-width', DEFAULT_LINK_WIDTH)
        .attr('stroke-dasharray', (edge) => getEdgeDasharray(edge));
    };

    const applyDefaultNodeStyles = () => {
      node
        .attr('stroke', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? '#f4a261' : '#fff'))
        .attr('stroke-width', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? 3 : 1.5))
        .attr('fill-opacity', (entry) => {
          if (searchMatchedIds.size === 0) {
            return 0.95;
          }
          return searchMatchedIds.has(nodeGraphId(entry)) ? 1 : 0.18;
        });
    };

    const applyPinnedNodeStyles = (entry) => {
      const selectedGraphId = nodeGraphId(entry);
      node
        .attr('stroke', (candidate) => (nodeGraphId(candidate) === selectedGraphId ? '#f4a261' : '#fff'))
        .attr('stroke-width', (candidate) => (nodeGraphId(candidate) === selectedGraphId ? 3.5 : 1.5))
        .attr('fill-opacity', (candidate) => (nodeGraphId(candidate) === selectedGraphId ? 1 : 0.18));

      link
        .attr('stroke-opacity', (edge) => (
          edgeGraphSourceId(edge) === selectedGraphId || edgeGraphTargetId(edge) === selectedGraphId ? 0.95 : 0.1
        ))
        .attr('stroke-width', (edge) => (
          edgeGraphSourceId(edge) === selectedGraphId || edgeGraphTargetId(edge) === selectedGraphId ? ACTIVE_LINK_WIDTH : DEFAULT_LINK_WIDTH
        ));
    };

    const applyPinnedEdgeStyles = (selectedEdge) => {
      link
        .attr('stroke-opacity', (edge) => (edge.key === selectedEdge.key ? 1 : 0.08))
        .attr('stroke-width', (edge) => (edge.key === selectedEdge.key ? PINNED_LINK_WIDTH : DEFAULT_LINK_WIDTH));

      node
        .attr('fill-opacity', (entry) => (
          nodeGraphId(entry) === edgeGraphSourceId(selectedEdge) || nodeGraphId(entry) === edgeGraphTargetId(selectedEdge) ? 1 : 0.18
        ))
        .attr('stroke', (entry) => (
          nodeGraphId(entry) === edgeGraphSourceId(selectedEdge) || nodeGraphId(entry) === edgeGraphTargetId(selectedEdge) ? '#f4a261' : '#fff'
        ))
        .attr('stroke-width', (entry) => (
          nodeGraphId(entry) === edgeGraphSourceId(selectedEdge) || nodeGraphId(entry) === edgeGraphTargetId(selectedEdge) ? 3 : 1.5
        ));
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
      .selectAll('path')
      .data(filteredLinks)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke', (edge) => getEdgeColor(edge))
      .attr('stroke-opacity', 0.72)
      .attr('stroke-width', DEFAULT_LINK_WIDTH)
      .attr('stroke-dasharray', (edge) => getEdgeDasharray(edge))
      .attr('marker-end', (edge) => `url(#${getEdgeMarkerId(edge)})`)
      .on('mouseover', function (event, edge) {
        if (pinnedInteraction) {
          return;
        }
        d3.select(this)
          .attr('stroke-opacity', 1)
          .attr('stroke-width', PINNED_LINK_WIDTH);
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
      .on('mouseout', function () {
        if (pinnedInteraction) {
          return;
        }
        applyDefaultLinkStyles();
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, edge) {
        event.stopPropagation();
        pinnedInteraction = { type: 'edge', edge };
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
      .selectAll('circle')
      .data(filteredNodes)
      .join('circle')
      .attr('r', (entry) => getNodeRadius(entry))
      .attr('fill', (entry) => getNodeFill(entry))
      .attr('fill-opacity', (entry) => {
        if (searchMatchedIds.size === 0) {
          return 0.95;
        }
        return searchMatchedIds.has(nodeGraphId(entry)) ? 1 : 0.18;
      })
      .attr('stroke', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? '#f4a261' : '#fff'))
      .attr('stroke-width', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? 3 : 1.5))
      .on('mouseover', function (event, entry) {
        if (pinnedInteraction) {
          return;
        }
        d3.select(this)
          .attr('stroke', '#f4a261')
          .attr('stroke-width', 3);
        link
          .attr('stroke-opacity', (edge) => (
            edgeGraphSourceId(edge) === nodeGraphId(entry) || edgeGraphTargetId(edge) === nodeGraphId(entry) ? 0.95 : 0.1
          ))
          .attr('stroke-width', (edge) => (
            edgeGraphSourceId(edge) === nodeGraphId(entry) || edgeGraphTargetId(edge) === nodeGraphId(entry) ? 3.2 : 2.2
          ));
        tooltip
          .style('opacity', 1)
          .style('pointer-events', 'none')
          .html(renderNodeTooltip(entry));
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
        applyDefaultNodeStyles();
        applyDefaultLinkStyles();
        tooltip.style('opacity', 0);
      })
      .on('click', function (event, entry) {
        event.stopPropagation();
        pinnedInteraction = { type: 'node', entry };
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
            renderGraph();
          })
          .on('end', (event, entry) => {
            if (physicsEnabledRef.current && !event.active) {
              simulation.alphaTarget(0);
            }
            entry.fx = null;
            entry.fy = null;
            renderGraph();
          })
      );

    const labeledNodeIds = new Set(
      localNodes
        .filter((entry) => relationFilteredNodeIds.has(nodeGraphId(entry)))
        .slice()
        .sort((left, right) => Number(right.degree || 0) - Number(left.degree || 0))
        .slice(0, 16)
        .map((entry) => nodeGraphId(entry))
    );

    labels = root.append('g')
      .selectAll('text')
      .data(filteredNodes.filter((entry) => labeledNodeIds.has(nodeGraphId(entry)) || searchMatchedIds.has(nodeGraphId(entry))))
      .join('text')
      .text((entry) => formatProposalReference(entry.id, getSourceScopedEcosystem(ecosystem, entry.source)))
      .style('font-size', '10.5px')
      .style('fill', 'var(--chart-text)')
      .style('font-weight', (entry) => (searchMatchedIds.has(nodeGraphId(entry)) ? 700 : 400))
      .style('opacity', (entry) => {
        if (searchMatchedIds.size > 0) {
          return searchMatchedIds.has(nodeGraphId(entry)) ? 1 : 0.22;
        }
        return 1;
      })
      .style('paint-order', 'stroke')
      .style('stroke', 'var(--chart-outline)')
      .style('stroke-width', 3)
      .style('stroke-linecap', 'round')
      .style('stroke-linejoin', 'round');

    renderGraph = () => {
      link
        .attr('d', (edge) => {
          const rawSourceX = edge.source.x ?? (width / 2);
          const rawSourceY = edge.source.y ?? (height / 2);
          const rawTargetX = edge.target.x ?? (width / 2);
          const rawTargetY = edge.target.y ?? (height / 2);
          const dx = rawTargetX - rawSourceX;
          const dy = rawTargetY - rawSourceY;
          const distance = Math.sqrt((dx * dx) + (dy * dy)) || 1;
          const unitX = dx / distance;
          const unitY = dy / distance;
          const sourcePadding = getNodeRadius(edge.source) + 1;
          const targetPadding = getNodeRadius(edge.target) - 5;
          const sourceX = rawSourceX + (unitX * sourcePadding);
          const sourceY = rawSourceY + (unitY * sourcePadding);
          const targetX = rawTargetX - (unitX * targetPadding);
          const targetY = rawTargetY - (unitY * targetPadding);
          const adjustedDx = targetX - sourceX;
          const adjustedDy = targetY - sourceY;
          const adjustedDistance = Math.sqrt((adjustedDx * adjustedDx) + (adjustedDy * adjustedDy)) || 1;
          const midpointX = (sourceX + targetX) / 2;
          const midpointY = (sourceY + targetY) / 2;
          const normalX = -adjustedDy / adjustedDistance;
          const normalY = adjustedDx / adjustedDistance;
          const curveOffset = Math.min(28, Math.max(10, adjustedDistance * 0.08));
          const controlX = midpointX + (normalX * curveOffset);
          const controlY = midpointY + (normalY * curveOffset);
          return `M ${sourceX},${sourceY} Q ${controlX},${controlY} ${targetX},${targetY}`;
        });

      node
        .attr('cx', (entry) => entry.x = Math.max(24, Math.min(width - 24, entry.x ?? (width / 2))))
        .attr('cy', (entry) => entry.y = Math.max(24, Math.min(height - 24, entry.y ?? (height / 2))));

      labels
        .attr('x', (entry) => entry.x + getNodeRadius(entry) + 5)
        .attr('y', (entry) => entry.y + 3);

      updateExportPayload();
    };

    simulationRef.current = simulation;
    redrawGraphRef.current = renderGraph;
    updateExportPayloadRef.current = updateExportPayload;

    svg.on('click', () => {
      clearPinnedInteraction();
    });

    simulation.on('tick', renderGraph);
    if (physicsEnabledRef.current) {
      renderGraph();
    } else {
      if (importedPositions && importedPositionedNodeCount > 0 && importedPositionedNodeCount < filteredNodes.length) {
        filteredNodes.forEach((entry) => {
          const coords = importedPositions[nodeGraphId(entry)] || importedPositions[String(entry.id)];
          if (!coords) {
            return;
          }
          entry.fx = coords[0];
          entry.fy = coords[1];
        });
      }

      if (!(importedPositions && importedPositionedNodeCount === filteredNodes.length)) {
        for (let iteration = 0; iteration < 140; iteration += 1) {
          simulation.tick();
        }
      }

      filteredNodes.forEach((entry) => {
        if (!importedPositions?.[nodeGraphId(entry)] && !importedPositions?.[String(entry.id)]) {
          return;
        }
        entry.fx = null;
        entry.fy = null;
      });
      renderGraph();
      simulation.alphaTarget(0);
      simulation.stop();
    }

    const legend = d3.select(legendRef.current);
    legend.selectAll('*').remove();

    const entries = color.domain().filter(Boolean);
    const renderLegendItems = (container, groups, sourceId = '') => {
      const patternKind = sourcePatternKindById.get(sourceId) || 'solid';
      groups.forEach((group) => {
        const item = container
          .append('div')
          .attr('class', 'dependency-node-legend__item');

        item
          .append('span')
          .attr('class', `dependency-node-legend__swatch dependency-node-legend__swatch--${patternKind}`)
          .style('--legend-swatch-base', color(group));

        item
          .append('span')
          .text(group);
      });
    };

    if (entries.length > 0) {
      if (orderedVisibleSourceIds.length > 1) {
        const groupedLegend = legend
          .append('div')
          .attr('class', 'dependency-node-legend-groups');

        orderedVisibleSourceIds.forEach((sourceId) => {
          const sourceEntries = Array.from(
            new Set(
              filteredNodes
                .filter((node) => String(node.source || '') === sourceId)
                .map((node) => node.colorGroup)
                .filter(Boolean)
            )
          );

          if (sourceEntries.length === 0) {
            return;
          }

          const source = ecosystem?.sources?.[sourceId];
          const section = groupedLegend
            .append('section')
            .attr('class', 'dependency-node-legend-group');

          section
            .append('div')
            .attr('class', 'dependency-node-legend-group__title')
            .text(source?.shortLabel || source?.acronym || sourceId || 'IPs');

          const container = section
            .append('div')
            .attr('class', 'dependency-node-legend');

          renderLegendItems(container, sourceEntries, sourceId);
        });
      } else {
        const container = legend
          .append('div')
          .attr('class', 'dependency-node-legend');

        renderLegendItems(container, entries, orderedVisibleSourceIds[0] || '');
      }
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
      d3.select('body').selectAll('.dependency-network-tooltip').remove();
    };
  }, [baselineType, colorBy, ecosystem, height, highlightProposal, importedLayout, includeConnections, includeThresholdConnections, isDifferentialMode, layoutMode, linkMode, linkType, links, minRelations, nodes, onlyCrossSource, proposalFilterIds, snapshotLabel, width, exportPayloadRef, legendRef, physicsEnabledRef, redrawGraphRef, simulationRef, updateExportPayloadRef]);

  return <svg ref={svgRef} role="img" />;
}
