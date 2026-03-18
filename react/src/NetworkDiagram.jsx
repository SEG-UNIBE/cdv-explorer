import * as d3 from 'd3';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Dropdown } from 'primereact/dropdown';
import { getClassificationColorMap } from './classificationColors';

export const LINK_TYPE_OPTIONS = [
  { label: 'Explicit Dependencies (Preamble)', value: 'explicit_dependencies' },
  { label: 'Explicit References (Regex)', value: 'explicit_references' },
  { label: 'Implicit Dependencies (LLM)', value: 'implicit_dependencies' },
];

const COLOR_BY_OPTIONS = [
  { label: 'Layer', value: 'layer' },
  { label: 'Status', value: 'status' },
  { label: 'Type', value: 'type' },
];

const EXPLICIT_DEPENDENCY_COLORS = {
  requires: '#667085',
  replaces: '#667085',
  superseded_by: '#667085',
};

const DEFAULT_EDGE_COLORS = {
  explicit_references: '#607d8b',
  implicit_dependencies: '#7b2cbf',
};

const EXPLICIT_DEPENDENCY_STYLES = {
  requires: null,
  replaces: '8 5',
  superseded_by: '2.5 4',
};

function normalizeProposalId(value) {
  const text = String(value ?? '').trim();
  if (!text) {
    return '';
  }

  const match = text.match(/^(?:bip\s*[- ]*)?0*(\d+)$/i);
  return match ? String(Number(match[1])) : text.toLowerCase();
}

function getProposalLabel(id) {
  const normalized = normalizeProposalId(id);
  return normalized ? `BIP ${normalized}` : String(id ?? '');
}

function getProposalUrl(id) {
  const normalized = normalizeProposalId(id);
  return normalized ? `https://bips.dev/${normalized}/` : '#';
}

function buildDisplayedLinks(linksByType, linkType) {
  if (linkType === 'explicit_dependencies') {
    return ['requires', 'replaces', 'superseded_by']
      .flatMap((relationType) => (linksByType?.[relationType] || []).map((edge, index) => ({
        ...edge,
        relationType,
        key: `${relationType}-${edge.source}-${edge.target}-${index}`,
      })));
  }

  return (linksByType?.[linkType] || []).map((edge, index) => ({
    ...edge,
    relationType: linkType,
    key: `${linkType}-${edge.source}-${edge.target}-${index}`,
  }));
}

function normalizeCategory(value, fallbackLabel) {
  const text = String(value ?? '').trim();
  return text || fallbackLabel;
}

export const NetworkDiagram = ({
  width = 1200,
  height = 800,
  data,
  highlightProposal = '',
  proposalFilterIds = [],
  includeConnections = true,
  layoutMode = 'balanced',
}) => {
  const ref = useRef();
  const legendRef = useRef();
  const [colorBy, setColorBy] = useState('layer');
  const [linkType, setLinkType] = useState('explicit_dependencies');

  const nodes = useMemo(
    () => (Array.isArray(data?.nodes) ? data.nodes.map((node) => ({ ...node })) : []),
    [data]
  );

  const links = useMemo(
    () => buildDisplayedLinks(data?.links || {}, linkType),
    [data, linkType]
  );

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    d3.select('body').selectAll('.dependency-network-tooltip').remove();

    if (nodes.length === 0) {
      return;
    }

    const allNodes = nodes.map((node) => ({ ...node }));
    const nodeById = new Map(allNodes.map((node) => [String(node.id), node]));
    const allLinks = links
      .filter((edge) => nodeById.has(String(edge.source)) && nodeById.has(String(edge.target)))
      .map((edge) => ({
        ...edge,
        source: String(edge.source),
        target: String(edge.target),
      }));

    const requestedIds = new Set((proposalFilterIds || []).map((value) => String(value)));
    const hasFilter = requestedIds.size > 0;
    let displayedNodeIds = new Set(allNodes.map((node) => String(node.id)));
    let localLinks = allLinks;

    if (hasFilter) {
      const matchedFilterNodeIds = new Set(
        allNodes
          .filter((node) => requestedIds.has(normalizeProposalId(node.id)) || requestedIds.has(String(node.id)))
          .map((node) => String(node.id))
      );

      if (includeConnections) {
        displayedNodeIds = new Set(matchedFilterNodeIds);
        localLinks = allLinks.filter((edge) => {
          const sourceIncluded = matchedFilterNodeIds.has(String(edge.source));
          const targetIncluded = matchedFilterNodeIds.has(String(edge.target));
          if (sourceIncluded || targetIncluded) {
            displayedNodeIds.add(String(edge.source));
            displayedNodeIds.add(String(edge.target));
            return true;
          }
          return false;
        });
      } else {
        displayedNodeIds = matchedFilterNodeIds;
        localLinks = allLinks.filter((edge) => (
          displayedNodeIds.has(String(edge.source)) && displayedNodeIds.has(String(edge.target))
        ));
      }
    }

    const localNodes = allNodes.filter((node) => displayedNodeIds.has(String(node.id)));

    if (localNodes.length === 0) {
      return;
    }

    const adjacency = new Map(localNodes.map((node) => [String(node.id), new Set()]));
    const degreeById = new Map(localNodes.map((node) => [String(node.id), 0]));
    const incomingById = new Map(localNodes.map((node) => [String(node.id), 0]));
    const outgoingById = new Map(localNodes.map((node) => [String(node.id), 0]));

    localLinks.forEach((edge) => {
      const sourceId = String(edge.source);
      const targetId = String(edge.target);
      adjacency.get(sourceId)?.add(targetId);
      adjacency.get(targetId)?.add(sourceId);
      degreeById.set(sourceId, (degreeById.get(sourceId) || 0) + 1);
      degreeById.set(targetId, (degreeById.get(targetId) || 0) + 1);
      outgoingById.set(sourceId, (outgoingById.get(sourceId) || 0) + 1);
      incomingById.set(targetId, (incomingById.get(targetId) || 0) + 1);
    });

    localNodes.forEach((node) => {
      const nodeId = String(node.id);
      node.degree = degreeById.get(nodeId) || 0;
      node.incomingDegree = incomingById.get(nodeId) || 0;
      node.outgoingDegree = outgoingById.get(nodeId) || 0;
    });

    const normalizedHighlight = normalizeProposalId(highlightProposal);
    const searchMatchedIds = normalizedHighlight
      ? new Set(
        localNodes
          .filter((node) => normalizeProposalId(node.id) === normalizedHighlight)
          .map((node) => String(node.id))
      )
      : new Set();

    const getEdgeSourceId = (edge) => (typeof edge.source === 'object' ? String(edge.source.id) : String(edge.source));
    const getEdgeTargetId = (edge) => (typeof edge.target === 'object' ? String(edge.target.id) : String(edge.target));

    const fallbackLabel = `Unknown ${colorBy.charAt(0).toUpperCase()}${colorBy.slice(1)}`;
    const allGroups = Array.from(
      new Set(allNodes.map((node) => normalizeCategory(node[colorBy], fallbackLabel)))
    );
    const colorMap = getClassificationColorMap(colorBy, allGroups);
    const color = d3.scaleOrdinal()
      .domain(allGroups)
      .range(allGroups.map((group) => colorMap[group]));

    localNodes.forEach((node) => {
      node.colorGroup = normalizeCategory(node[colorBy], fallbackLabel);
    });

    const getEdgeColor = (edge) => {
      if (linkType === 'explicit_dependencies') {
        return EXPLICIT_DEPENDENCY_COLORS[edge.relationType] || '#667085';
      }
      return DEFAULT_EDGE_COLORS[edge.relationType] || '#607d8b';
    };

    const getEdgeDasharray = (edge) => {
      if (linkType !== 'explicit_dependencies') {
        return null;
      }
      return EXPLICIT_DEPENDENCY_STYLES[edge.relationType] || null;
    };

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('width', '100%')
      .style('height', 'auto');

    const defs = svg.append('defs');
    const markerTypes = Array.from(new Set(localLinks.map((edge) => edge.relationType)));
    markerTypes.forEach((relationType) => {
      defs
        .append('marker')
        .attr('id', `dependency-arrow-${relationType}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 14)
        .attr('refY', 0)
        .attr('orient', 'auto')
        .attr('markerWidth', 4.5)
        .attr('markerHeight', 4.5)
        .append('path')
        .attr('d', 'M 0,-5 L 10,0 L 0,5')
        .attr('fill', linkType === 'explicit_dependencies'
          ? EXPLICIT_DEPENDENCY_COLORS[relationType] || '#667085'
          : DEFAULT_EDGE_COLORS[relationType] || '#607d8b');
    });

    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'dependency-network-tooltip')
      .style('position', 'absolute')
      .style('padding', '8px 12px')
      .style('background', '#1a1a1a')
      .style('color', '#f0f0f0')
      .style('border', '1px solid #555')
      .style('border-radius', '6px')
      .style('box-shadow', '0px 2px 6px rgba(0,0,0,0.4)')
      .style('font-size', '13px')
      .style('pointer-events', 'none')
      .style('line-height', '1.45')
      .style('opacity', 0);

    const setTooltipPosition = (pageX, pageY) => {
      tooltip
        .style('left', `${pageX + 10}px`)
        .style('top', `${pageY - 28}px`);
    };

    const renderNodeTooltip = (entry) => (
      `<strong><a href="${getProposalUrl(entry.id)}" target="_blank" rel="noreferrer">${getProposalLabel(entry.id)}</a></strong><br/>` +
      `Outgoing: ${entry.outgoingDegree}<br/>` +
      `Incoming: ${entry.incomingDegree}<br/>` +
      `Layer: ${entry.layer || 'Unknown'}<br/>` +
      `Status: ${entry.status || 'Unknown'}<br/>` +
      `Type: ${entry.type || 'Unknown'}<br/>` +
      `Compliance Score: ${entry.compliance_score ?? 'N/A'}`
    );

    const relationLabel = {
      explicit_references: 'Explicit Reference',
      implicit_dependencies: 'Implicit Dependency',
      requires: 'Requires',
      replaces: 'Replaces',
      superseded_by: 'Superseded By',
    };

    const renderEdgeTooltip = (edge) => (
      `<strong><a href="${getProposalUrl(getEdgeSourceId(edge))}" target="_blank" rel="noreferrer">${getProposalLabel(getEdgeSourceId(edge))}</a></strong>` +
      ` &rarr; ` +
      `<strong><a href="${getProposalUrl(getEdgeTargetId(edge))}" target="_blank" rel="noreferrer">${getProposalLabel(getEdgeTargetId(edge))}</a></strong><br/>` +
      `Type: ${relationLabel[edge.relationType] || edge.relationType}`
    );

    const degreeExtent = d3.extent(localNodes, (node) => Number(node.degree || 0));
    const radius = d3.scaleSqrt()
      .domain([degreeExtent[0] || 0, degreeExtent[1] || 1])
      .range([7, 16]);
    const getNodeRadius = (entry) => (
      searchMatchedIds.has(String(entry.id))
        ? radius(Number(entry.degree || 0)) + 5
        : radius(Number(entry.degree || 0))
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

    const linkForce = d3.forceLink(localLinks).id((node) => String(node.id));
    const chargeForce = d3.forceManyBody();
    const collisionForce = d3.forceCollide().radius((node) => radius(Number(node.degree || 0)) + 10);
    const centerForce = d3.forceCenter(width / 2, height / 2);
    const xForce = d3.forceX(width / 2).strength(0.05);
    const yForce = d3.forceY(height / 2).strength(0.05);

    if (layoutMode === 'clustered') {
      linkForce.distance(92).strength(0.28);
      chargeForce.strength(-220);
      xForce
        .x((node) => groupAnchors.get(node.colorGroup)?.x ?? width / 2)
        .strength(0.22);
      yForce
        .y((node) => groupAnchors.get(node.colorGroup)?.y ?? height / 2)
        .strength(0.22);
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

    const simulation = d3.forceSimulation(localNodes)
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

    let pinnedInteraction = null;
    let link;
    let node;

    const applyDefaultLinkStyles = () => {
      link
        .attr('stroke', (edge) => getEdgeColor(edge))
        .attr('stroke-opacity', (edge) => {
          if (searchMatchedIds.size === 0) {
            return 0.72;
          }
          return searchMatchedIds.has(getEdgeSourceId(edge)) || searchMatchedIds.has(getEdgeTargetId(edge)) ? 0.95 : 0.08;
        })
        .attr('stroke-width', 2.2)
        .attr('stroke-dasharray', (edge) => getEdgeDasharray(edge));
    };

    const applyDefaultNodeStyles = () => {
      node
        .attr('stroke', (entry) => (searchMatchedIds.has(String(entry.id)) ? '#f4a261' : '#fff'))
        .attr('stroke-width', (entry) => (searchMatchedIds.has(String(entry.id)) ? 3 : 1.5))
        .attr('fill-opacity', (entry) => {
          if (searchMatchedIds.size === 0) {
            return 0.95;
          }
          return searchMatchedIds.has(String(entry.id)) ? 1 : 0.18;
        });
    };

    const applyPinnedNodeStyles = (entry) => {
      node
        .attr('stroke', (candidate) => (String(candidate.id) === String(entry.id) ? '#f4a261' : '#fff'))
        .attr('stroke-width', (candidate) => (String(candidate.id) === String(entry.id) ? 3.5 : 1.5))
        .attr('fill-opacity', (candidate) => (String(candidate.id) === String(entry.id) ? 1 : 0.18));

      link
        .attr('stroke-opacity', (edge) => (
          getEdgeSourceId(edge) === String(entry.id) || getEdgeTargetId(edge) === String(entry.id) ? 0.95 : 0.1
        ))
        .attr('stroke-width', (edge) => (
          getEdgeSourceId(edge) === String(entry.id) || getEdgeTargetId(edge) === String(entry.id) ? 3.2 : 2.2
        ));
    };

    const applyPinnedEdgeStyles = (selectedEdge) => {
      link
        .attr('stroke-opacity', (edge) => (edge.key === selectedEdge.key ? 1 : 0.08))
        .attr('stroke-width', (edge) => (edge.key === selectedEdge.key ? 3.4 : 2.2));

      node
        .attr('fill-opacity', (entry) => (
          String(entry.id) === getEdgeSourceId(selectedEdge) || String(entry.id) === getEdgeTargetId(selectedEdge) ? 1 : 0.18
        ))
        .attr('stroke', (entry) => (
          String(entry.id) === getEdgeSourceId(selectedEdge) || String(entry.id) === getEdgeTargetId(selectedEdge) ? '#f4a261' : '#fff'
        ))
        .attr('stroke-width', (entry) => (
          String(entry.id) === getEdgeSourceId(selectedEdge) || String(entry.id) === getEdgeTargetId(selectedEdge) ? 3 : 1.5
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
      .data(localLinks)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke', (edge) => getEdgeColor(edge))
      .attr('stroke-opacity', 0.72)
      .attr('stroke-width', 2.2)
      .attr('stroke-dasharray', (edge) => getEdgeDasharray(edge))
      .attr('marker-end', (edge) => `url(#dependency-arrow-${edge.relationType})`)
      .on('mouseover', function (event, edge) {
        if (pinnedInteraction) {
          return;
        }

        d3.select(this)
          .attr('stroke-opacity', 1)
          .attr('stroke-width', 3.4);

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
      .data(localNodes)
      .join('circle')
      .attr('r', (entry) => getNodeRadius(entry))
      .attr('fill', (entry) => colorBy === 'compliance_score'
        ? color(Number(entry.compliance_score ?? 50))
        : color(normalizeCategory(entry[colorBy], fallbackLabel)))
      .attr('fill-opacity', (entry) => {
        if (searchMatchedIds.size === 0) {
          return 0.95;
        }
        return searchMatchedIds.has(String(entry.id)) ? 1 : 0.18;
      })
      .attr('stroke', (entry) => (searchMatchedIds.has(String(entry.id)) ? '#f4a261' : '#fff'))
      .attr('stroke-width', (entry) => (searchMatchedIds.has(String(entry.id)) ? 3 : 1.5))
      .on('mouseover', function (event, entry) {
        if (pinnedInteraction) {
          return;
        }

        d3.select(this)
          .attr('stroke', '#f4a261')
          .attr('stroke-width', 3);

        link
          .attr('stroke-opacity', (edge) => (
            getEdgeSourceId(edge) === String(entry.id) || getEdgeTargetId(edge) === String(entry.id) ? 0.95 : 0.1
          ))
          .attr('stroke-width', (edge) => (
            getEdgeSourceId(edge) === String(entry.id) || getEdgeTargetId(edge) === String(entry.id) ? 3.2 : 2.2
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

    const labeledNodeIds = new Set(
      localNodes
        .slice()
        .sort((left, right) => Number(right.degree || 0) - Number(left.degree || 0))
        .slice(0, 16)
        .map((entry) => String(entry.id))
    );

    const labels = root.append('g')
      .selectAll('text')
      .data(localNodes.filter((entry) => labeledNodeIds.has(String(entry.id)) || searchMatchedIds.has(String(entry.id))))
      .join('text')
      .text((entry) => getProposalLabel(entry.id))
      .style('font-size', '10.5px')
      .style('fill', '#1f2933')
      .style('font-weight', (entry) => (searchMatchedIds.has(String(entry.id)) ? 700 : 400))
      .style('opacity', (entry) => {
        if (searchMatchedIds.size > 0) {
          return searchMatchedIds.has(String(entry.id)) ? 1 : 0.22;
        }
        return 1;
      })
      .style('paint-order', 'stroke')
      .style('stroke', '#ffffff')
      .style('stroke-width', 3)
      .style('stroke-linecap', 'round')
      .style('stroke-linejoin', 'round');

    svg.on('click', () => {
      clearPinnedInteraction();
    });

    simulation.on('tick', () => {
      link
        .attr('d', (edge) => {
          const rawSourceX = edge.source.x;
          const rawSourceY = edge.source.y;
          const rawTargetX = edge.target.x;
          const rawTargetY = edge.target.y;
          const dx = rawTargetX - rawSourceX;
          const dy = rawTargetY - rawSourceY;
          const distance = Math.sqrt((dx * dx) + (dy * dy)) || 1;
          const unitX = dx / distance;
          const unitY = dy / distance;
          const sourcePadding = getNodeRadius(edge.source) + 1;
          const targetPadding = getNodeRadius(edge.target) -5;
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
        .attr('cx', (entry) => entry.x = Math.max(24, Math.min(width - 24, entry.x)))
        .attr('cy', (entry) => entry.y = Math.max(24, Math.min(height - 24, entry.y)));

      labels
        .attr('x', (entry) => entry.x + getNodeRadius(entry) + 5)
        .attr('y', (entry) => entry.y + 3);
    });

    const legend = d3.select(legendRef.current);
    legend.selectAll('*').remove();

    const entries = color.domain().filter(Boolean);
    if (entries.length > 0) {
      const container = legend
        .append('div')
        .attr('class', 'dependency-node-legend');

      entries.forEach((group) => {
        const item = container
          .append('div')
          .attr('class', 'dependency-node-legend__item');

        item
          .append('span')
          .attr('class', 'dependency-node-legend__swatch')
          .style('background-color', color(group));

        item
          .append('span')
          .text(group);
      });
    }

    return () => {
      simulation.stop();
      svg.selectAll('*').remove();
      d3.select('body').selectAll('.dependency-network-tooltip').remove();
    };
  }, [colorBy, data, height, highlightProposal, includeConnections, layoutMode, linkType, links, nodes, proposalFilterIds, width]);

  const explicitLegendItems = [
    { label: 'Requires', dasharray: EXPLICIT_DEPENDENCY_STYLES.requires },
    { label: 'Replaces', dasharray: EXPLICIT_DEPENDENCY_STYLES.replaces },
    { label: 'Superseded By', dasharray: EXPLICIT_DEPENDENCY_STYLES.superseded_by },
  ];
  const edgeLegendItems = linkType === 'explicit_dependencies'
    ? explicitLegendItems
    : [
      {
        label: linkType === 'explicit_references' ? 'Explicit References (Regex)' : 'Implicit Dependencies (LLM)',
        dasharray: null,
      },
    ];

  return (
    <div>
      <div style={{ display: 'flex', gap: '2rem', alignItems: 'flex-start', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <div className="network-layout-picker">
          <div className="network-layout-picker__label">Edges</div>
          <Dropdown
            inputId="linkType"
            value={linkType}
            options={LINK_TYPE_OPTIONS}
            onChange={(event) => setLinkType(event.value)}
            placeholder="Link Type"
            className="w-full md:w-18rem"
            style={{ minWidth: '260px' }}
          />
        </div>

        <div className="network-layout-picker">
          <div className="network-layout-picker__label">Coloring</div>
          <Dropdown
            inputId="dependency-colorBy"
            value={colorBy}
            options={COLOR_BY_OPTIONS}
            onChange={(event) => setColorBy(event.value)}
            placeholder="Coloring"
            className="w-full md:w-14rem"
            style={{ minWidth: '180px' }}
          />
        </div>
      </div>

      <div className="dependency-edge-legend">
        {edgeLegendItems.map((item) => (
          <div key={item.label} className="dependency-edge-legend__item">
            <svg className="dependency-edge-legend__line" viewBox="0 0 36 12" aria-hidden="true">
              <line
                x1="2"
                y1="6"
                x2="34"
                y2="6"
                stroke={linkType === 'explicit_dependencies' ? '#667085' : (DEFAULT_EDGE_COLORS[linkType] || '#667085')}
                strokeWidth="2.5"
                strokeDasharray={item.dasharray || undefined}
                strokeLinecap="round"
              />
            </svg>
            <span>{item.label}</span>
          </div>
        ))}
      </div>

      <div ref={legendRef} style={{ marginBottom: '1rem' }} />
      <svg ref={ref} role="img" />
    </div>
  );
};
