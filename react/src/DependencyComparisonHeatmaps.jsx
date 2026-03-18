import { useEffect, useMemo, useRef, useState } from 'react';
import { Dropdown } from 'primereact/dropdown';
import { InputText } from 'primereact/inputtext';
import { LINK_TYPE_OPTIONS } from './NetworkDiagram';

const STATUS_OPTIONS = [
  { label: 'All statuses', value: '' },
  { label: 'Hits', value: 'overlap' },
  { label: 'Approach only', value: 'approach_only' },
  { label: 'Missed', value: 'baseline_only' },
];

const SHORT_LABELS = {
  explicit_dependencies: 'Preamble',
  explicit_references: 'Regex',
  implicit_dependencies: 'LLM',
};

function getProposalHref(id) {
  const text = String(id || '').trim();
  return text ? `https://bips.dev/${Number(text) || text}/` : '#';
}

function truncateTitle(value, maxLength = 26) {
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
    (entry) => entry.approach === 'explicit_references' && entry.baseline === 'explicit_dependencies'
  ) || comparisons.find((entry) => entry.approach !== entry.baseline) || comparisons[0] || null;
}

function buildCellExplanation(metric, comparison) {
  if (!comparison) {
    return '';
  }

  if (metric === 'combined') {
    return `${comparison.approach_label} captures ${formatPercent(comparison.summary.hit_rate)} of the edges present in ${comparison.baseline_label} and misses ${formatPercent(comparison.summary.missed_rate)} of them.`;
  }

  if (metric === 'hits') {
    return `${comparison.approach_label} captures ${formatPercent(comparison.summary.hit_rate)} of the edges present in ${comparison.baseline_label}.`;
  }

  if (metric === 'approach_only') {
    const approachOnlyRate = comparison.summary.approach_total
      ? Number(comparison.summary.approach_only || 0) / Number(comparison.summary.approach_total)
      : 0;
    return `${formatPercent(approachOnlyRate)} of the edges found by ${comparison.approach_label} are absent from ${comparison.baseline_label}.`;
  }

  return `${formatPercent(comparison.summary.missed_rate)} of the edges present in ${comparison.baseline_label} are missing from ${comparison.approach_label}.`;
}

function renderCellTooltipHtml(metric, comparison) {
  if (!comparison) {
    return '';
  }

  return (
    `<strong>${
      metric === 'combined'
        ? 'Hits / Missed'
        : metric === 'approach_only'
          ? 'Approach Only'
          : metric === 'hits'
            ? 'Hits'
            : 'Missed'
    }</strong><br/>` +
    `${buildCellExplanation(metric, comparison)}<br/>` +
    `${comparison.approach_label} vs ${comparison.baseline_label}<br/>` +
    `Hits: ${comparison.summary.overlap}<br/>` +
    `Missed: ${comparison.summary.baseline_only}<br/>` +
    `Approach only: ${comparison.summary.approach_only}`
  );
}

function HeatmapTable({
  title,
  metric,
  comparisons,
  selectedKey,
  onSelect,
  onShowTooltip,
  onMoveTooltip,
  onHideTooltip,
}) {
  const approachKeys = LINK_TYPE_OPTIONS.map((option) => option.value);

  return (
    <div className="dependency-heatmap-card">
      <h4>{title}</h4>
      <table className="dependency-heatmap-table">
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
                const metricValue = metric === 'hits'
                  ? comparison?.summary?.hit_rate
                  : metric === 'approach_only'
                    ? (
                      comparison?.summary?.approach_total
                        ? Number(comparison?.summary?.approach_only || 0) / Number(comparison?.summary?.approach_total || 1)
                        : 0
                    )
                    : comparison?.summary?.missed_rate;
                const hitRate = comparison?.summary?.hit_rate;
                const missedRate = comparison?.summary?.missed_rate;

                return (
                  <td key={comparisonKey}>
                    <button
                      type="button"
                      className={`dependency-heatmap-cell${selectedKey === comparisonKey ? ' is-selected' : ''}${metric === 'combined' ? ' dependency-heatmap-cell--combined' : ''}`}
                      style={metric === 'combined' ? undefined : { backgroundColor: getCellColor(metric, metricValue) }}
                      onClick={() => onSelect(comparisonKey)}
                      onMouseEnter={(event) => onShowTooltip(event, renderCellTooltipHtml(metric, comparison))}
                      onMouseMove={onMoveTooltip}
                      onMouseLeave={onHideTooltip}
                    >
                      {metric === 'combined' ? (
                        <span className="dependency-heatmap-cell__stack">
                          <span
                            className="dependency-heatmap-cell__band dependency-heatmap-cell__band--hit"
                            style={{ backgroundColor: getCellColor('hits', hitRate) }}
                          >
                            {formatPercent(hitRate)}
                          </span>
                          <span
                            className="dependency-heatmap-cell__band dependency-heatmap-cell__band--missed"
                            style={{ backgroundColor: getCellColor('missed', missedRate) }}
                          >
                            {formatPercent(missedRate)}
                          </span>
                        </span>
                      ) : (
                        <span>{formatPercent(metricValue)}</span>
                      )}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DependencyComparisonHeatmaps({
  pairwiseComparisons,
  proposalShortLabel = 'BIP',
}) {
  const [selectedComparisonKey, setSelectedComparisonKey] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  const tooltipRef = useRef(null);

  useEffect(() => {
    const tooltipNode = document.createElement('div');
    document.body.appendChild(tooltipNode);

    tooltipRef.current = tooltipNode;

    const tooltip = tooltipNode;
    tooltip.className = 'dependency-comparison-tooltip';
    Object.assign(tooltip.style, {
      position: 'absolute',
      background: '#1a1a1a',
      color: '#fff',
      padding: '6px 10px',
      borderRadius: '4px',
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

  const filteredEdges = useMemo(() => {
    const edges = selectedComparison?.edges || [];
    const search = searchFilter.trim().toLowerCase();

    return edges.filter((edge) => {
      if (statusFilter && edge.status !== statusFilter) {
        return false;
      }

      if (!search) {
        return true;
      }

      return [
        edge.source,
        edge.target,
        edge.source_title,
        edge.target_title,
        edge.status,
      ].some((value) => String(value || '').toLowerCase().includes(search));
    });
  }, [searchFilter, selectedComparison, statusFilter]);

  if (!pairwiseComparisons || Object.keys(pairwiseComparisons).length === 0) {
    return null;
  }

  return (
    <div>
      <div className="dependency-heatmap-grid">
        <HeatmapTable
          title="Hits / Missed"
          metric="combined"
          comparisons={pairwiseComparisons}
          selectedKey={selectedComparisonKey}
          onSelect={setSelectedComparisonKey}
          onShowTooltip={showTooltip}
          onMoveTooltip={moveTooltip}
          onHideTooltip={hideTooltip}
        />
        <HeatmapTable
          title="Approach Only"
          metric="approach_only"
          comparisons={pairwiseComparisons}
          selectedKey={selectedComparisonKey}
          onSelect={setSelectedComparisonKey}
          onShowTooltip={showTooltip}
          onMoveTooltip={moveTooltip}
          onHideTooltip={hideTooltip}
        />
      </div>

      {selectedComparison ? (
        <div className="dependency-comparison-detail">
          <div className="dependency-comparison-detail__header">
            <div>
              <h4>{selectedComparison.approach_label} vs {selectedComparison.baseline_label}</h4>
              <div className="dependency-comparison-detail__summary">
                Hits: {selectedComparison.summary.overlap} ({formatPercent(selectedComparison.summary.hit_rate)}) | Missed: {selectedComparison.summary.baseline_only} ({formatPercent(selectedComparison.summary.missed_rate)}) | Approach only: {selectedComparison.summary.approach_only}
              </div>
            </div>
            <div className="dependency-comparison-detail__filters">
              <Dropdown
                value={statusFilter}
                options={STATUS_OPTIONS}
                onChange={(event) => setStatusFilter(event.value)}
                placeholder="Filter status"
              />
              <InputText
                value={searchFilter}
                onChange={(event) => setSearchFilter(event.target.value)}
                placeholder="Filter edges"
              />
            </div>
          </div>
          <div className="dependency-comparison-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Target</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredEdges.map((edge) => (
                  <tr key={`${selectedComparisonKey}-${edge.status}-${edge.source}-${edge.target}`}>
                    <td>
                      <a href={getProposalHref(edge.source)} target="_blank" rel="noreferrer">
                        {proposalShortLabel} {edge.source}
                      </a>
                      {edge.source_title ? <span>{` ${truncateTitle(edge.source_title)}`}</span> : null}
                    </td>
                    <td>
                      <a href={getProposalHref(edge.target)} target="_blank" rel="noreferrer">
                        {proposalShortLabel} {edge.target}
                      </a>
                      {edge.target_title ? <span>{` ${truncateTitle(edge.target_title)}`}</span> : null}
                    </td>
                    <td>{edge.status}</td>
                  </tr>
                ))}
                {filteredEdges.length === 0 ? (
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
