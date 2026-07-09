import { useEffect, useMemo, useRef, useState } from 'react';
import { positionTooltip } from './tooltipPosition';
import { Button } from 'primereact/button';
import {
  BODY_EXTRACTED_REGEX,
  DEFAULT_DEPENDENCY_APPROACH,
  PAIRWISE_LINK_TYPE_OPTIONS,
  getDependencyApproachLabel,
} from './dependencyApproaches';
import { ProposalFilterControl } from './ProposalFilterControl';
import { CollapsibleControls } from './dashboard/CollapsibleControls';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { parseProposalFilterExpression } from './dashboard/dashboardData';
import { formatProposalLabel, getProposalUrl, normalizeProposalId } from './proposalLinks';
import { renderTooltipCardHtml } from './tooltipHtml';

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

function formatScore(value) {
  const numeric = Number(value);
  if (value === null || value === undefined || !Number.isFinite(numeric)) {
    return 'n/a';
  }
  return numeric.toFixed(2);
}

function buildDefaultSelection(pairwiseComparisons) {
  const comparisons = Object.values(pairwiseComparisons || {});
  return comparisons.find(
    (entry) => entry.approach === BODY_EXTRACTED_REGEX && entry.baseline === DEFAULT_DEPENDENCY_APPROACH
  ) || comparisons.find((entry) => entry.approach !== entry.baseline) || comparisons[0] || null;
}

function resolveSourceIdForGraphKey(value, ecosystem) {
  const text = String(value || '').trim();
  const separatorIndex = text.indexOf(':');
  if (separatorIndex < 0) {
    return '';
  }
  const sourceSlug = text.slice(0, separatorIndex);
  const sourceEntry = Object.values(ecosystem?.sources || {}).find(
    (source) => String(source?.sourceSlug || source?.sourceId || '') === sourceSlug
  );
  return String(sourceEntry?.sourceId || sourceSlug || '').trim();
}

function buildProposalRefKey(ref) {
  return `${String(ref?.source || '').trim()}|${String(ref?.id || '').trim()}`;
}

function buildComparisonMetricCards(comparison, llmModel) {
  if (!comparison) {
    return [];
  }

  const approachShortLabel = getDependencyApproachLabel(comparison.approach, llmModel);
  const baselineShortLabel = getDependencyApproachLabel(comparison.baseline, llmModel);
  // Badge text stays compact: no LLM model suffix ("LLM", not "LLM (model)").
  const approachBadgeLabel = getDependencyApproachLabel(comparison.approach);
  const baselineBadgeLabel = getDependencyApproachLabel(comparison.baseline);
  return [
    {
      label: 'Approach',
      value: `${approachBadgeLabel} vs ${baselineBadgeLabel}`,
      description: 'The row approach compared against the column baseline selected in the matrix above.',
    },
    {
      label: 'Same',
      value: `${comparison.summary.overlap} (${formatPercent(comparison.summary.hit_rate)})`,
      description: 'Edges found by both approaches, as a share of the baseline’s edges.',
    },
    {
      label: `Not in ${approachBadgeLabel}`,
      value: `${comparison.summary.baseline_only} (${formatPercent(comparison.summary.missed_rate)})`,
      description: `Edges ${baselineShortLabel} found that ${approachShortLabel} did not.`,
    },
    {
      label: `Only in ${approachBadgeLabel}`,
      value: `${comparison.summary.approach_only} (${formatPercent(getApproachOnlyRate(comparison))})`,
      description: `Edges ${approachShortLabel} found that are absent from ${baselineShortLabel}.`,
    },
    {
      label: 'Cohen’s κ',
      value: formatScore(comparison.summary.kappa),
    },
  ];
}

function buildCellExplanation(metric, comparison, llmModel) {
  if (!comparison) {
    return '';
  }

  if (metric === 'overlap') {
    return `${getDependencyApproachLabel(comparison.approach, llmModel)} captures ${formatPercent(comparison.summary.hit_rate)} of the edges present in ${getDependencyApproachLabel(comparison.baseline, llmModel)}.`;
  }

  if (metric === 'baseline_only') {
    return `${formatPercent(comparison.summary.missed_rate)} of the edges present in ${getDependencyApproachLabel(comparison.baseline, llmModel)} are missing from ${getDependencyApproachLabel(comparison.approach, llmModel)}.`;
  }

  if (metric === 'approach_only') {
    const approachOnlyRate = comparison.summary.approach_total
      ? Number(comparison.summary.approach_only || 0) / Number(comparison.summary.approach_total)
      : 0;
    return `${formatPercent(approachOnlyRate)} of the edges found by ${getDependencyApproachLabel(comparison.approach, llmModel)} are absent from ${getDependencyApproachLabel(comparison.baseline, llmModel)}.`;
  }

  return '';
}

function getApproachOnlyRate(comparison) {
  if (!comparison?.summary?.approach_total) {
    return 0;
  }

  return Number(comparison.summary.approach_only || 0) / Number(comparison.summary.approach_total || 1);
}

function renderCellTooltipHtml(metric, comparison, llmModel) {
  if (!comparison) {
    return '';
  }

  const approachShortLabel = getDependencyApproachLabel(comparison.approach, llmModel);
  const metricLabel = metric === 'overlap'
    ? 'Same'
    : metric === 'baseline_only'
      ? `Not in ${approachShortLabel}`
      : `Only in ${approachShortLabel}`;

  return (
    renderTooltipCardHtml({
      titleHtml: `<strong>${metricLabel}</strong>`,
      rows: [
        ['Same', `${comparison.summary.overlap} (${formatPercent(comparison.summary.hit_rate)})`],
        [`Not in ${approachShortLabel}`, `${comparison.summary.baseline_only} (${formatPercent(comparison.summary.missed_rate)})`],
        [`Only in ${approachShortLabel}`, `${comparison.summary.approach_only} (${formatPercent(getApproachOnlyRate(comparison))})`],
      ],
      bodyHtml: buildCellExplanation(metric, comparison, llmModel),
    })
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
  const approachShortLabel = getDependencyApproachLabel(comparison?.approach, comparison?.llm_model || '') || 'Approach';
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
  llmModel,
  selectedKey,
  selectedStatus,
  onSelect,
  onShowTooltip,
  onMoveTooltip,
  onHideTooltip,
}) {
  const approachKeys = PAIRWISE_LINK_TYPE_OPTIONS.map((option) => option.value);

  return (
    <table className="dependency-heatmap-table dependency-heatmap-table--triple">
      <thead>
        <tr>
          <th>Approach \ Baseline</th>
          {approachKeys.map((baseline) => (
            <th key={baseline} title={getDependencyApproachLabel(baseline, llmModel)}>
              {getDependencyApproachLabel(baseline, llmModel)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {approachKeys.map((approach) => (
          <tr key={approach}>
            <th title={getDependencyApproachLabel(approach, llmModel)}>{getDependencyApproachLabel(approach, llmModel)}</th>
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
                          onMouseEnter={(event) => onShowTooltip(event, renderCellTooltipHtml(metric.key, {
                            ...comparison,
                            llm_model: llmModel,
                          }, llmModel))}
                          onMouseMove={onMoveTooltip}
                          onMouseLeave={onHideTooltip}
                          aria-label={getMetricLabel(metric.key, {
                            ...comparison,
                            llm_model: llmModel,
                          })}
                        >
                          <span className="dependency-heatmap-cell__metric-value">
                            {formatPercent(metricValue)}
                          </span>
                        </button>
                      );
                    })}
                    <div className="dependency-heatmap-cell__agreement">
                      <span className="dependency-heatmap-cell__agreement-label">κ</span>
                      <span className="dependency-heatmap-cell__agreement-value">
                        {formatScore(comparison?.summary?.kappa)}
                      </span>
                    </div>
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
  activeLlmModel = '',
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
    positionTooltip(tooltip, event.pageX, event.pageY);
  };

  const moveTooltip = (event) => {
    const tooltip = tooltipRef.current;
    if (!tooltip || tooltip.style.opacity !== '1') {
      return;
    }

    positionTooltip(tooltip, event.pageX, event.pageY);
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
  const comparisonMetricCards = useMemo(
    () => buildComparisonMetricCards(selectedComparison, activeLlmModel),
    [activeLlmModel, selectedComparison]
  );
  const availableSourceNodes = useMemo(() => {
    const refs = new Map();
    (selectedComparison?.edges || []).forEach((edge) => {
      const ref = {
        source: resolveSourceIdForGraphKey(edge.source, ecosystem),
        id: normalizeProposalId(edge.source, ecosystem),
      };
      if (ref.id) {
        refs.set(buildProposalRefKey(ref), ref);
      }
    });
    return Array.from(refs.values()).sort((left, right) => (
      String(left.source || '').localeCompare(String(right.source || ''))
      || String(left.id || '').localeCompare(String(right.id || ''), undefined, { numeric: true })
    ));
  }, [ecosystem, selectedComparison]);
  const availableTargetNodes = useMemo(() => {
    const refs = new Map();
    (selectedComparison?.edges || []).forEach((edge) => {
      const ref = {
        source: resolveSourceIdForGraphKey(edge.target, ecosystem),
        id: normalizeProposalId(edge.target, ecosystem),
      };
      if (ref.id) {
        refs.set(buildProposalRefKey(ref), ref);
      }
    });
    return Array.from(refs.values()).sort((left, right) => (
      String(left.source || '').localeCompare(String(right.source || ''))
      || String(left.id || '').localeCompare(String(right.id || ''), undefined, { numeric: true })
    ));
  }, [ecosystem, selectedComparison]);
  const selectedSourceIds = useMemo(
    () => parseProposalFilterExpression(sourceFilterText, availableSourceNodes, ecosystem),
    [availableSourceNodes, ecosystem, sourceFilterText]
  );
  const selectedTargetIds = useMemo(
    () => parseProposalFilterExpression(targetFilterText, availableTargetNodes, ecosystem),
    [availableTargetNodes, ecosystem, targetFilterText]
  );

  useEffect(() => {
    setSourceFilterText((current) => {
      if (!current.trim()) {
        return current;
      }
      return parseProposalFilterExpression(current, availableSourceNodes, ecosystem).length ? current : '';
    });
  }, [availableSourceNodes, ecosystem]);

  useEffect(() => {
    setTargetFilterText((current) => {
      if (!current.trim()) {
        return current;
      }
      return parseProposalFilterExpression(current, availableTargetNodes, ecosystem).length ? current : '';
    });
  }, [availableTargetNodes, ecosystem]);

  const filteredEdges = useMemo(() => {
    const edges = selectedComparison?.edges || [];
    const selectedSourceRefKeys = new Set((selectedSourceIds || []).map(buildProposalRefKey));
    const selectedTargetRefKeys = new Set((selectedTargetIds || []).map(buildProposalRefKey));

    return edges.filter((edge) => {
      if (statusFilter && edge.status !== statusFilter) {
        return false;
      }

      if (sourceFilterText.trim()) {
        const sourceRef = {
          source: resolveSourceIdForGraphKey(edge.source, ecosystem),
          id: normalizeProposalId(edge.source, ecosystem),
        };
        if (!selectedSourceRefKeys.has(buildProposalRefKey(sourceRef))) {
          return false;
        }
      }

      if (targetFilterText.trim()) {
        const targetRef = {
          source: resolveSourceIdForGraphKey(edge.target, ecosystem),
          id: normalizeProposalId(edge.target, ecosystem),
        };
        if (!selectedTargetRefKeys.has(buildProposalRefKey(targetRef))) {
          return false;
        }
      }

      return true;
    });
  }, [ecosystem, selectedComparison, selectedSourceIds, selectedTargetIds, sourceFilterText, statusFilter, targetFilterText]);

  const sortedEdges = useMemo(() => {
    const direction = sortDirection === 'desc' ? -1 : 1;
    const getSortableValue = (edge, field) => {
      if (field === 'status') {
        return String(edge.status || '').toLowerCase();
      }
      const normalized = normalizeProposalId(edge[field], ecosystem);
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
  }, [ecosystem, filteredEdges, sortDirection, sortField]);

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
        llmModel={activeLlmModel}
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
            <div className="dependency-comparison-detail__summary dependency-comparison-detail__summary--badges">
              {comparisonMetricCards.map((metric) => (
                <div
                  key={metric.label}
                  className={`metric-badge${metric.label === 'Approach' ? ' metric-badge--wide-value' : ''}`}
                  onMouseEnter={(event) => showTooltip(event, metric.description ? renderTooltipCardHtml({
                    titleHtml: `<strong>${metric.label}</strong>`,
                    bodyHtml: metric.description,
                  }) : '')}
                  onMouseMove={moveTooltip}
                  onMouseLeave={hideTooltip}
                >
                  <span className="metric-badge__label">{metric.label}</span>
                  <span className="metric-badge__value">{metric.value}</span>
                </div>
              ))}
            </div>
          </div>
          <CollapsibleControls className="dependency-comparison-controls">
            <div className="dependency-comparison-controls__grid">
              <ProposalFilterControl
                value={sourceFilterText}
                onChange={setSourceFilterText}
                ecosystem={ecosystem}
                ariaLabel="Filter source proposals for dependency comparison details"
                layout="split"
                entryLabel="Filter Proposals (Source)"
                trailingControl={(
                  <Button
                    type="button"
                    label="Clear"
                    severity="secondary"
                    text
                    onClick={() => setSourceFilterText('')}
                    disabled={!sourceFilterText.trim()}
                  />
                )}
                className="dependency-comparison-controls__filter"
              />
              <ProposalFilterControl
                value={targetFilterText}
                onChange={setTargetFilterText}
                ecosystem={ecosystem}
                ariaLabel="Filter target proposals for dependency comparison details"
                layout="split"
                entryLabel="Filter Proposals (Target)"
                trailingControl={(
                  <Button
                    type="button"
                    label="Clear"
                    severity="secondary"
                    text
                    onClick={() => setTargetFilterText('')}
                    disabled={!targetFilterText.trim()}
                  />
                )}
                className="dependency-comparison-controls__filter"
              />
            </div>
          </CollapsibleControls>
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
