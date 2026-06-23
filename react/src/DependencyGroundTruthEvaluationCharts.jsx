import { useMemo, useState } from 'react';
import { formatProposalReference, getProposalUrl } from './proposalLinks';
import {
  useDashboardEcosystem,
  useDashboardLinkMode,
  useDashboardSnapshot,
} from './dashboard/DashboardSnapshotContext';
import { renderTooltipCardHtml } from './tooltipHtml';
import { useAnalysisMetricTooltip } from './useAnalysisMetricTooltip';

const SCORE_SERIES = [
  { key: 'precision', label: 'Precision', color: '#f28e2c' },
  { key: 'recall', label: 'Recall', color: '#76b7b2' },
  { key: 'f1', label: 'F1', color: '#af7aa1' },
];

const COUNT_SERIES = [
  { key: 'tp', label: 'TP', color: '#59a14f' },
  { key: 'fp', label: 'FP', color: '#e15759' },
  { key: 'fn', label: 'FN', color: '#4e79a7' },
];
const TOOLTIP_EDGE_SCROLL_THRESHOLD = 15;

function formatScore(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function formatCount(value) {
  return String(Math.round(Number(value || 0)));
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderProposalAnchor(graphKey, ecosystem, snapshotLabel, linkMode) {
  const label = formatProposalReference(graphKey, ecosystem);
  const url = getProposalUrl(graphKey, snapshotLabel, { linkMode }, ecosystem);
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`;
}

function renderEdgeListHtml(edges, ecosystem, snapshotLabel, linkMode, { showRelationType = false } = {}) {
  const list = Array.isArray(edges) ? edges.filter(Boolean) : [];
  if (!list.length) {
    return '';
  }

  const renderItems = (entries) => entries.map((edge) => (
    `<div class="tooltip-edge-list__item">` +
    `${renderProposalAnchor(edge.source, ecosystem, snapshotLabel, linkMode)}` +
    `<span class="tooltip-edge-list__arrow">&rarr;</span>` +
    `${renderProposalAnchor(edge.target, ecosystem, snapshotLabel, linkMode)}` +
    `${showRelationType && edge?.relationType ? `<span class="tooltip-edge-list__type">(${escapeHtml(edge.relationType)})</span>` : ''}` +
    `</div>`
  ));

  const listClassName = list.length > TOOLTIP_EDGE_SCROLL_THRESHOLD
    ? 'tooltip-edge-list tooltip-edge-list--scroll'
    : 'tooltip-edge-list';
  return `<div class="${listClassName}">${renderItems(list).join('')}</div>`;
}

function renderOptionalListRow(label, edges, ecosystem, snapshotLabel, linkMode, options = {}) {
  const content = renderEdgeListHtml(edges, ecosystem, snapshotLabel, linkMode, options);
  return content ? [label, content] : null;
}

function buildBarTooltipHtml({
  chartTitle,
  row,
  seriesEntry,
  valueFormatter,
  ecosystem,
  snapshotLabel,
  linkMode,
}) {
  if (seriesEntry.key === 'tp') {
    return renderTooltipCardHtml({
      titleHtml: `<strong>${chartTitle}</strong>`,
      rows: [
        ['Info', 'Present in both the approach output and the curated ground truth'],
        renderOptionalListRow('Matching<br/>Edges', row.matchedEdges, ecosystem, snapshotLabel, linkMode, { showRelationType: true }),
      ],
    });
  }

  if (seriesEntry.key === 'fp') {
    return renderTooltipCardHtml({
      titleHtml: `<strong>${chartTitle}</strong>`,
      rows: [
        ['Info', `Present in ${row.label} but absent from ground truth`],
        renderOptionalListRow(`Only in<br/>${row.label}`, row.falsePositiveEdges, ecosystem, snapshotLabel, linkMode),
      ],
    });
  }

  if (seriesEntry.key === 'fn') {
    return renderTooltipCardHtml({
      titleHtml: `<strong>${chartTitle}</strong>`,
      rows: [
        ['Info', 'Present in ground truth but missed by the approach'],
        renderOptionalListRow(`Missing in<br/>${row.label}`, row.falseNegativeEdges, ecosystem, snapshotLabel, linkMode, { showRelationType: true }),
      ],
    });
  }

  if (seriesEntry.key === 'precision') {
    return renderTooltipCardHtml({
      titleHtml: `<strong>${chartTitle}</strong>`,
      rows: [
        ['Info', `Precision decreases when edges are present in ${row.label} but absent from ground truth.`],
        renderOptionalListRow(`Only in<br/>${row.label}`, row.falsePositiveEdges, ecosystem, snapshotLabel, linkMode),
      ],
    });
  }

  if (seriesEntry.key === 'recall') {
    return renderTooltipCardHtml({
      titleHtml: `<strong>${chartTitle}</strong>`,
      rows: [
        ['Info', 'Recall decreases when the approach misses edges present in ground truth.'],
        renderOptionalListRow(`Missing in<br/>${row.label}`, row.falseNegativeEdges, ecosystem, snapshotLabel, linkMode, { showRelationType: true }),
      ],
    });
  }

  return renderTooltipCardHtml({
    titleHtml: `<strong>${chartTitle}</strong>`,
    rows: [
      ['Info', 'F1 balances both false positives and false negatives.'],
      renderOptionalListRow(`Only in<br/>${row.label}`, row.falsePositiveEdges, ecosystem, snapshotLabel, linkMode),
      renderOptionalListRow(`Missing in<br/>${row.label}`, row.falseNegativeEdges, ecosystem, snapshotLabel, linkMode, { showRelationType: true }),
    ],
  });
}

function GroupedBarChart({
  title,
  subtitle,
  rows,
  series,
  valueFormatter,
  valueMax = null,
  showHtmlTooltip,
  moveTooltip,
  hideTooltip,
  ecosystem,
  snapshotLabel,
  linkMode,
}) {
  const [pinnedBarKey, setPinnedBarKey] = useState(null);
  const width = 560;
  const height = 310;
  const margin = { top: 26, right: 18, bottom: 72, left: 44 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const groupCount = rows.length || 1;
  const groupWidth = innerWidth / groupCount;
  const barGap = 8;
  const groupGap = 18;
  const barWidth = Math.max(
    16,
    Math.min(36, (groupWidth - groupGap - (barGap * (series.length - 1))) / Math.max(series.length, 1)),
  );
  const effectiveMax = valueMax ?? Math.max(
    1,
    ...rows.flatMap((row) => series.map((entry) => Number(row?.[entry.key] || 0))),
  );
  const ticks = valueMax === 1 ? [0, 0.25, 0.5, 0.75, 1] : [0, 0.25, 0.5, 0.75, 1].map((tick) => tick * effectiveMax);

  const bars = useMemo(() => rows.map((row, rowIndex) => {
    const totalBarsWidth = (barWidth * series.length) + (barGap * (series.length - 1));
    const groupStart = margin.left + (rowIndex * groupWidth) + Math.max(0, (groupWidth - totalBarsWidth) / 2);
    return series.map((entry, seriesIndex) => {
      const value = Number(row?.[entry.key] || 0);
      const normalized = effectiveMax > 0 ? value / effectiveMax : 0;
      const barHeight = normalized * innerHeight;
      return {
        key: `${row.label}-${entry.key}`,
        label: row.label,
        seriesLabel: entry.label,
        value,
        x: groupStart + (seriesIndex * (barWidth + barGap)),
        y: margin.top + (innerHeight - barHeight),
        width: barWidth,
        height: barHeight,
        color: entry.color,
        tooltipHtml: buildBarTooltipHtml({
          chartTitle: title,
          row,
          seriesEntry: entry,
          valueFormatter,
          ecosystem,
          snapshotLabel,
          linkMode,
        }),
      };
    });
  }).flat(), [barGap, barWidth, effectiveMax, ecosystem, groupWidth, innerHeight, linkMode, margin.left, margin.top, rows, series, snapshotLabel, title, valueFormatter]);

  return (
    <div
      className="dependency-evaluation-chart"
      onClick={() => {
        setPinnedBarKey(null);
        hideTooltip();
      }}
    >
      <div className="dependency-evaluation-chart__header">
        <div className="dependency-evaluation-chart__title-row">
          <div className="dependency-evaluation-chart__title">{title}</div>
          <div className="dependency-evaluation-chart__legend">
            {series.map((entry) => (
              <div key={entry.key} className="dependency-evaluation-chart__legend-item">
                <span
                  className="dependency-evaluation-chart__legend-swatch"
                  style={{ backgroundColor: entry.color }}
                  aria-hidden="true"
                />
                <span>{entry.label}</span>
              </div>
            ))}
          </div>
        </div>
        {subtitle ? <div className="dependency-evaluation-chart__subtitle">{subtitle}</div> : null}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        {ticks.map((tick) => {
          const normalized = effectiveMax > 0 ? tick / effectiveMax : 0;
          const y = margin.top + innerHeight - (normalized * innerHeight);
          return (
            <g key={tick}>
              <line
                x1={margin.left}
                x2={width - margin.right}
                y1={y}
                y2={y}
                stroke="var(--chart-grid)"
                strokeOpacity="0.55"
              />
              <text
                x={margin.left - 8}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="var(--chart-text)"
              >
                {valueFormatter(tick)}
              </text>
            </g>
          );
        })}
        {bars.map((bar) => (
          <g key={bar.key}>
            <rect
              x={bar.x}
              y={bar.y}
              width={bar.width}
              height={Math.max(bar.height, 1)}
              rx="5"
              fill={bar.color}
              className="dependency-evaluation-chart__bar"
              onMouseEnter={(event) => {
                if (pinnedBarKey) return;
                showHtmlTooltip(event, bar.tooltipHtml);
              }}
              onMouseMove={(event) => {
                if (pinnedBarKey) return;
                moveTooltip(event);
              }}
              onMouseLeave={() => {
                if (pinnedBarKey) return;
                hideTooltip();
              }}
              onClick={(event) => {
                event.stopPropagation();
                setPinnedBarKey(bar.key);
                showHtmlTooltip(event, bar.tooltipHtml, { interactive: true });
              }}
              opacity={pinnedBarKey && pinnedBarKey !== bar.key ? 0.35 : 1}
            />
            <text
              x={bar.x + (bar.width / 2)}
              y={bar.y - 6}
              textAnchor="middle"
              fontSize="11"
              fill="var(--chart-text)"
            >
              {valueFormatter(bar.value)}
            </text>
          </g>
        ))}
        {rows.map((row, index) => (
          <text
            key={row.label}
            x={margin.left + (index * groupWidth) + (groupWidth / 2)}
            y={height - 24}
            textAnchor="middle"
            fontSize="12"
            fontWeight="600"
            fill="var(--chart-text)"
          >
            {row.label}
          </text>
        ))}
      </svg>
    </div>
  );
}

export function DependencyGroundTruthEvaluationCharts({ evaluation }) {
  const {
    showHtmlTooltip,
    moveTooltip,
    hideTooltip,
  } = useAnalysisMetricTooltip();
  const ecosystem = useDashboardEcosystem();
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();

  if (!evaluation?.approaches?.length) {
    return null;
  }

  return (
    <div className="dependency-evaluation-chart-grid">
      <GroupedBarChart
        title="Confusion Counts"
        subtitle="True positives, false positives, and false negatives"
        rows={evaluation.approaches}
        series={COUNT_SERIES}
        valueFormatter={formatCount}
        showHtmlTooltip={showHtmlTooltip}
        moveTooltip={moveTooltip}
        hideTooltip={hideTooltip}
        ecosystem={ecosystem}
        snapshotLabel={snapshotLabel}
        linkMode={linkMode}
      />
      <GroupedBarChart
        title="Quality Metrics"
        subtitle="Precision, recall, and F1 on curated source proposals"
        rows={evaluation.approaches}
        series={SCORE_SERIES}
        valueFormatter={formatScore}
        valueMax={1}
        showHtmlTooltip={showHtmlTooltip}
        moveTooltip={moveTooltip}
        hideTooltip={hideTooltip}
        ecosystem={ecosystem}
        snapshotLabel={snapshotLabel}
        linkMode={linkMode}
      />
    </div>
  );
}
