import { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';
import {
  BODY_EXTRACTED_REGEX,
  DEFAULT_DEPENDENCY_APPROACH,
  DEPENDENCY_SHORT_LABELS,
} from './dependencyApproaches';
import { LINK_TYPE_OPTIONS } from './NetworkDiagram';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { normalizeProposalFilterValue, parseProposalFilterExpression } from './dashboard/dashboardData';
import { formatProposalLabel, getProposalUrl } from './proposalLinks';

const SHORT_LABELS = DEPENDENCY_SHORT_LABELS;

function getApproachDisplayLabel(approachKey) {
  return SHORT_LABELS[approachKey] || approachKey;
}

function truncateTitle(value, maxLength = 45) {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength).trimEnd()}...`;
}

function getCellColor(metric, value) {
  const clamped = Math.max(0, Math.min(1, Number(value || 0)));

  if (metric === 'hits') {
    return `rgba(47, 158, 68, ${0.12 + (clamped * 0.72)})`;
  }

  if (metric === 'approach_only') {
    return `rgba(148, 163, 184, ${0.12 + (clamped * 0.72)})`;
  }

  return `rgba(217, 72, 65, ${0.12 + (clamped * 0.72)})`;
}

function formatPercent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function buildDefaultSelection(pairwiseComparisons) {
  const comparisons = Object.values(pairwiseComparisons || {});
  return comparisons.find(
    (entry) => entry.approach === BODY_EXTRACTED_REGEX && entry.baseline === DEFAULT_DEPENDENCY_APPROACH
  ) || comparisons.find((entry) => entry.approach !== entry.baseline) || comparisons[0] || null;
}

function buildCellExplanation(metric, comparison) {
  if (!comparison) {
    return '';
  }

  if (metric === 'overlap') {
    return `${getApproachDisplayLabel(comparison.approach)} captures ${formatPercent(comparison.summary.hit_rate)} of the edges present in ${getApproachDisplayLabel(comparison.baseline)}.`;
  }

  if (metric === 'baseline_only') {
    return `${formatPercent(comparison.summary.missed_rate)} of the edges present in ${getApproachDisplayLabel(comparison.baseline)} are missing from ${getApproachDisplayLabel(comparison.approach)}.`;
  }

  if (metric === 'approach_only') {
    const approachOnlyRate = comparison.summary.approach_total
      ? Number(comparison.summary.approach_only || 0) / Number(comparison.summary.approach_total)
      : 0;
    return `${formatPercent(approachOnlyRate)} of the edges found by ${getApproachDisplayLabel(comparison.approach)} are absent from ${getApproachDisplayLabel(comparison.baseline)}.`;
  }

  return '';
}

function getApproachOnlyRate(comparison) {
  if (!comparison?.summary?.approach_total) {
    return 0;
  }

  return Number(comparison.summary.approach_only || 0) / Number(comparison.summary.approach_total || 1);
}

function renderCellTooltipHtml(metric, comparison) {
  if (!comparison) {
    return '';
  }

  const approachShortLabel = SHORT_LABELS[comparison.approach] || comparison.approach;
  const metricLabel = metric === 'overlap'
    ? 'Same'
    : metric === 'baseline_only'
      ? `Not in ${approachShortLabel}`
      : `Only in ${approachShortLabel}`;

  return (
    `<strong>${metricLabel}</strong><br/>` +
    `${buildCellExplanation(metric, comparison)}<br/>` +
    `Same: ${comparison.summary.overlap} (${formatPercent(comparison.summary.hit_rate)})<br/>` +
    `Not in ${approachShortLabel}: ${comparison.summary.baseline_only} (${formatPercent(comparison.summary.missed_rate)})<br/>` +
    `Only in ${approachShortLabel}: ${comparison.summary.approach_only} (${formatPercent(getApproachOnlyRate(comparison))})`
  );
}

function getMetricValue(metric, comparison) {
  if (!comparison) {
    return 0;
  }

  if (metric === 'overlap') {
    return comparison.summary.hit_rate;
  }

  if (metric === 'baseline_only') {
    return comparison.summary.missed_rate;
  }

  return getApproachOnlyRate(comparison);
}

const CELL_METRICS = [
  { key: 'overlap', status: 'overlap', colorMetric: 'hits' },
  { key: 'baseline_only', status: 'baseline_only', colorMetric: 'missed' },
  { key: 'approach_only', status: 'approach_only', colorMetric: 'approach_only' },
];

function getMetricLabel(metric, comparison) {
  const approachShortLabel = SHORT_LABELS[comparison?.approach] || 'Approach';
  if (metric === 'overlap') {
    return 'Same';
  }
  if (metric === 'baseline_only') {
    return `Not in ${approachShortLabel}`;
  }
  return `Only in ${approachShortLabel}`;
}

function ComparisonTable({
  comparisons,
  selectedKey,
  selectedStatus,
  onSelect,
  onShowTooltip,
  onMoveTooltip,
  onHideTooltip,
}) {
  const approachKeys = LINK_TYPE_OPTIONS.map((option) => option.value);

  return (
    <table className="dependency-heatmap-table dependency-heatmap-table--triple">
      <thead>
        <tr>
          <th>Approach \ Baseline</th>
          {approachKeys.map((baseline) => (
            <th key={baseline} title={SHORT_LABELS[baseline]}>
              {SHORT_LABELS[baseline]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {approachKeys.map((approach) => (
          <tr key={approach}>
            <th title={SHORT_LABELS[approach]}>{SHORT_LABELS[approach]}</th>
            {approachKeys.map((baseline) => {
              const comparisonKey = `${approach}__vs__${baseline}`;
              const comparison = comparisons?.[comparisonKey];

              return (
                <td key={comparisonKey}>
                  <div className="dependency-heatmap-cell dependency-heatmap-cell--triple">
                    {CELL_METRICS.map((metric) => {
                      const metricValue = getMetricValue(metric.key, comparison);
                      const isSelected = selectedKey === comparisonKey && selectedStatus === metric.status;

                      return (
                        <button
                          key={metric.key}
                          type="button"
                          className={`dependency-heatmap-cell__metric${isSelected ? ' is-selected' : ''}`}
                          style={{ backgroundColor: getCellColor(metric.colorMetric, metricValue) }}
                          onClick={() => onSelect(comparisonKey, metric.status)}
                          onMouseEnter={(event) => onShowTooltip(event, renderCellTooltipHtml(metric.key, comparison))}
                          onMouseMove={onMoveTooltip}
                          onMouseLeave={onHideTooltip}
                          aria-label={getMetricLabel(metric.key, comparison)}
                        >
                          <span className="dependency-heatmap-cell__metric-value">
                            {formatPercent(metricValue)}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DependencyComparisonHeatmaps({
  pairwiseComparisons,
  proposalShortLabel = 'BIP',
}) {
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();
  const [selectedComparisonKey, setSelectedComparisonKey] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sourceFilterText, setSourceFilterText] = useState('');
  const [targetFilterText, setTargetFilterText] = useState('');
  const [sortField, setSortField] = useState('source');
  const [sortDirection, setSortDirection] = useState('asc');
  const tooltipRef = useRef(null);

  useEffect(() => {
    const tooltipNode = document.createElement('div');
    document.body.appendChild(tooltipNode);

    tooltipRef.current = tooltipNode;

    const tooltip = tooltipNode;
    tooltip.className = 'dependency-comparison-tooltip';
    Object.assign(tooltip.style, {
      position: 'absolute',
      background: 'var(--tooltip-bg)',
      color: 'var(--tooltip-text)',
      padding: '6px 10px',
      borderRadius: '4px',
      border: '1px solid var(--tooltip-border)',
      boxShadow: 'var(--tooltip-shadow)',
      fontSize: '12px',
      pointerEvents: 'none',
      maxWidth: '360px',
      lineHeight: '1.45',
      opacity: '0',
      zIndex: '2000',
    });

    return () => {
      tooltip.remove();
      tooltipRef.current = null;
    };
  }, []);

  const showTooltip = (event, html) => {
    const tooltip = tooltipRef.current;
    if (!tooltip || !html) {
      return;
    }

    tooltip.innerHTML = html;
    tooltip.style.opacity = '1';
    tooltip.style.left = `${event.pageX + 10}px`;
    tooltip.style.top = `${event.pageY - 28}px`;
  };

  const moveTooltip = (event) => {
    const tooltip = tooltipRef.current;
    if (!tooltip || tooltip.style.opacity !== '1') {
      return;
    }

    tooltip.style.left = `${event.pageX + 10}px`;
    tooltip.style.top = `${event.pageY - 28}px`;
  };

  const hideTooltip = () => {
    const tooltip = tooltipRef.current;
    if (!tooltip) {
      return;
    }

    tooltip.style.opacity = '0';
  };

  const handleSelectComparisonMetric = (comparisonKey, status) => {
    setSelectedComparisonKey(comparisonKey);
    setStatusFilter(status);
  };

  const handleShowAll = () => {
    setStatusFilter('');
    setSourceFilterText('');
    setTargetFilterText('');
  };

  useEffect(() => {
    const defaultSelection = buildDefaultSelection(pairwiseComparisons);
    if (!defaultSelection) {
      setSelectedComparisonKey('');
      return;
    }

    setSelectedComparisonKey((current) => (
      current && pairwiseComparisons?.[current]
        ? current
        : `${defaultSelection.approach}__vs__${defaultSelection.baseline}`
    ));
  }, [pairwiseComparisons]);

  const selectedComparison = selectedComparisonKey
    ? pairwiseComparisons?.[selectedComparisonKey]
    : buildDefaultSelection(pairwiseComparisons);
  const availableEdgeIds = useMemo(() => {
    const ids = new Set();
    (selectedComparison?.edges || []).forEach((edge) => {
      const source = normalizeProposalFilterValue(edge.source);
      const target = normalizeProposalFilterValue(edge.target);
      if (source) {
        ids.add(source);
      }
      if (target) {
        ids.add(target);
      }
    });
    return Array.from(ids).sort((left, right) => Number(left) - Number(right));
  }, [selectedComparison]);
  const selectedSourceIds = useMemo(
    () => parseProposalFilterExpression(sourceFilterText, availableEdgeIds),
    [availableEdgeIds, sourceFilterText]
  );
  const selectedTargetIds = useMemo(
    () => parseProposalFilterExpression(targetFilterText, availableEdgeIds),
    [availableEdgeIds, targetFilterText]
  );

  useEffect(() => {
    setSourceFilterText((current) => {
      if (!current.trim()) {
        return current;
      }
      return parseProposalFilterExpression(current, availableEdgeIds).length ? current : '';
    });
  }, [availableEdgeIds]);

  useEffect(() => {
    setTargetFilterText((current) => {
      if (!current.trim()) {
        return current;
      }
      return parseProposalFilterExpression(current, availableEdgeIds).length ? current : '';
    });
  }, [availableEdgeIds]);

  const filteredEdges = useMemo(() => {
    const edges = selectedComparison?.edges || [];

    return edges.filter((edge) => {
      if (statusFilter && edge.status !== statusFilter) {
        return false;
      }

      if (sourceFilterText.trim()) {
        const source = normalizeProposalFilterValue(edge.source);
        if (!selectedSourceIds.includes(source)) {
          return false;
        }
      }

      if (targetFilterText.trim()) {
        const target = normalizeProposalFilterValue(edge.target);
        if (!selectedTargetIds.includes(target)) {
          return false;
        }
      }

      return true;
    });
  }, [selectedComparison, selectedSourceIds, selectedTargetIds, sourceFilterText, statusFilter, targetFilterText]);

  const sortedEdges = useMemo(() => {
    const direction = sortDirection === 'desc' ? -1 : 1;
    const getSortableValue = (edge, field) => {
      if (field === 'status') {
        return String(edge.status || '').toLowerCase();
      }
      const normalized = normalizeProposalFilterValue(edge[field]);
      if (/^\d+$/.test(normalized)) {
        return Number(normalized);
      }
      return Number.POSITIVE_INFINITY;
    };

    return [...filteredEdges].sort((left, right) => {
      const leftValue = getSortableValue(left, sortField);
      const rightValue = getSortableValue(right, sortField);

      if (leftValue !== rightValue) {
        if (typeof leftValue === 'string' || typeof rightValue === 'string') {
          return String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true }) * direction;
        }
        return (leftValue - rightValue) * direction;
      }

      const leftText = String(left[sortField] || '');
      const rightText = String(right[sortField] || '');
      const fallback = leftText.localeCompare(rightText, undefined, { numeric: true });
      if (fallback !== 0) {
        return fallback * direction;
      }

      const secondaryField = sortField === 'source' ? 'target' : 'source';
      return String(left[secondaryField] || '').localeCompare(String(right[secondaryField] || ''), undefined, { numeric: true });
    });
  }, [filteredEdges, sortDirection, sortField]);

  const handleSortChange = (field) => {
    if (field === sortField) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }

    setSortField(field);
    setSortDirection('asc');
  };

  const getSortIndicator = (field) => {
    if (field !== sortField) {
      return '';
    }
    return sortDirection === 'asc' ? ' ↑' : ' ↓';
  };

  if (!pairwiseComparisons || Object.keys(pairwiseComparisons).length === 0) {
    return null;
  }

  return (
    <div>
      <ComparisonTable
        comparisons={pairwiseComparisons}
        selectedKey={selectedComparisonKey}
        selectedStatus={statusFilter}
        onSelect={handleSelectComparisonMetric}
        onShowTooltip={showTooltip}
        onMoveTooltip={moveTooltip}
        onHideTooltip={hideTooltip}
      />

      {selectedComparison ? (
        <div className="dependency-comparison-detail">
          <div className="dependency-comparison-detail__header">
            <div>
              <h4>{getApproachDisplayLabel(selectedComparison.approach)} vs {getApproachDisplayLabel(selectedComparison.baseline)}</h4>
              <div className="dependency-comparison-detail__summary">
                Same: {selectedComparison.summary.overlap} ({formatPercent(selectedComparison.summary.hit_rate)}) | Not in {SHORT_LABELS[selectedComparison.approach] || 'approach'}: {selectedComparison.summary.baseline_only} ({formatPercent(selectedComparison.summary.missed_rate)}) | Only in {SHORT_LABELS[selectedComparison.approach] || 'approach'}: {selectedComparison.summary.approach_only} ({formatPercent(getApproachOnlyRate(selectedComparison))})
              </div>
            </div>
            <div className="dependency-comparison-detail__filters">
              <Button
                type="button"
                label="Show all"
                severity="secondary"
                text
                onClick={handleShowAll}
                disabled={!statusFilter && !sourceFilterText.trim() && !targetFilterText.trim()}
              />
              <InputText
                value={sourceFilterText}
                onChange={(event) => setSourceFilterText(event.target.value)}
                placeholder="Filter Source (e.g. 1,3-5,7)"
                aria-label="Filter source nodes (e.g. 1,3-5,7)"
              />
              <InputText
                value={targetFilterText}
                onChange={(event) => setTargetFilterText(event.target.value)}
                placeholder="Filter Target (e.g. 1,3-5,7)"
                aria-label="Filter target nodes (e.g. 1,3-5,7)"
              />
            </div>
          </div>
          <div className="dependency-comparison-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>
                    <button
                      type="button"
                      className="analysis-table__sort-button"
                      onClick={() => handleSortChange('source')}
                    >
                      {`Source${getSortIndicator('source')}`}
                    </button>
                  </th>
                  <th>
                    <button
                      type="button"
                      className="analysis-table__sort-button"
                      onClick={() => handleSortChange('target')}
                    >
                      {`Target${getSortIndicator('target')}`}
                    </button>
                  </th>
                  <th>
                    <button
                      type="button"
                      className="analysis-table__sort-button"
                      onClick={() => handleSortChange('status')}
                    >
                      {`Status${getSortIndicator('status')}`}
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedEdges.map((edge) => (
                  <tr key={`${selectedComparisonKey}-${edge.status}-${edge.source}-${edge.target}`}>
                    <td>
                      <a href={getProposalUrl(edge.source, snapshotLabel, { linkMode }, ecosystem)} target="_blank" rel="noreferrer">
                        {formatProposalLabel(edge.source, ecosystem)}
                      </a>
                      {edge.source_title ? <span>{` ${truncateTitle(edge.source_title)}`}</span> : null}
                    </td>
                    <td>
                      <a href={getProposalUrl(edge.target, snapshotLabel, { linkMode }, ecosystem)} target="_blank" rel="noreferrer">
                        {formatProposalLabel(edge.target, ecosystem)}
                      </a>
                      {edge.target_title ? <span>{` ${truncateTitle(edge.target_title)}`}</span> : null}
                    </td>
                    <td>{edge.status}</td>
                  </tr>
                ))}
                {sortedEdges.length === 0 ? (
                  <tr>
                    <td colSpan={3}>No edges match the current filters.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
