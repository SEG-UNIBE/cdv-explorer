import { useMemo, useState } from 'react';
import { Column } from 'primereact/column';
import { DataTable } from 'primereact/datatable';
import { RadioButton } from 'primereact/radiobutton';
import { BODY_EXTRACTED_LLM, getDependencyApproachLabel } from '../../dependencyApproaches';
import { formatProposalReference, getProposalUrl } from '../../proposalLinks';
import { CollapsibleControls } from '../CollapsibleControls';
import { useDashboardLinkMode, useDashboardSnapshot } from '../DashboardSnapshotContext';
import { ExportableCard } from '../ExportableCard';
import { SectionSourceToggle } from './SectionSourceToggle';

const COMPACT_METRIC_LABELS = {
  in_degree: 'In-Degree',
  weighted_eigenvector: 'WEV',
  pagerank: 'PageRank',
  betweenness: 'Betweenness',
};

// Mirrors the ordered LaTeX badge palette: five light same-hue badges, five
// inverted badges, then cross-hue combinations for further recurring IPs.
const CENTRALITY_HIGHLIGHT_STYLES = [
  ['#111111', '#fee2e2'],
  ['#111111', '#dbeafe'],
  ['#111111', '#dcfce7'],
  ['#111111', '#f3e8ff'],
  ['#111111', '#ccfbf1'],
  ['#ffffff', '#7f1d1d'],
  ['#ffffff', '#1e3a8a'],
  ['#ffffff', '#166534'],
  ['#ffffff', '#6b21a8'],
  ['#ffffff', '#115e59'],
  ['#111111', '#dbeafe'],
  ['#111111', '#dcfce7'],
  ['#111111', '#f3e8ff'],
  ['#111111', '#ccfbf1'],
  ['#111111', '#fee2e2'],
];

const CONCORDANCE_SCOPE_ALL = 'all';
const CONCORDANCE_SCOPE_TOP = 'top';

function formatCentralityValue(metric, value) {
  const numericValue = Number(value || 0);
  if (metric === 'in_degree') return String(Math.trunc(numericValue));
  if (metric === 'betweenness') return numericValue.toFixed(4);
  return numericValue.toFixed(3);
}

function formatConcordance(value) {
  return value == null ? '—' : Number(value).toFixed(3);
}

function formatScopeItemCount(count) {
  const itemCount = Number(count || 0);
  return itemCount ? `${itemCount} IPs` : '— IPs';
}

function truncateTitle(value, maxLength = 18) {
  const title = String(value || '').trim();
  return title.length > maxLength ? `${title.slice(0, maxLength).trimEnd()}...` : title;
}

function CentralityEntry({
  entry,
  metric,
  ecosystem,
  snapshot,
  linkMode,
  highlightedId,
  setHighlightedId,
}) {
  if (!entry) return <span aria-label="No ranked IP">—</span>;
  const title = String(entry.title || '').trim();
  const isHighlighted = highlightedId === entry.id;
  const isDimmed = Boolean(highlightedId && !isHighlighted);
  const highlightIndex = Number.isInteger(entry.highlight_index)
    ? entry.highlight_index
    : null;
  const highlightStyle = highlightIndex == null
    ? null
    : CENTRALITY_HIGHLIGHT_STYLES[
      highlightIndex % CENTRALITY_HIGHLIGHT_STYLES.length
    ];
  return (
    <div
      className={`centrality-ranking-entry${isHighlighted ? ' centrality-ranking-entry--highlighted' : ''}${isDimmed ? ' centrality-ranking-entry--dimmed' : ''}`}
      onMouseEnter={() => setHighlightedId(entry.id)}
      onMouseLeave={() => setHighlightedId(null)}
      onFocus={() => setHighlightedId(entry.id)}
      onBlur={() => setHighlightedId(null)}
    >
      <span
        className={`centrality-ranking-entry__proposal${highlightStyle ? ' centrality-ranking-entry__proposal--highlighted' : ''}`}
        style={highlightStyle ? {
          '--centrality-highlight-foreground': highlightStyle[0],
          '--centrality-highlight-background': highlightStyle[1],
        } : undefined}
      >
        <a
          href={getProposalUrl(entry.id, snapshot, { linkMode }, ecosystem)}
          target="_blank"
          rel="noreferrer"
        >
          {formatProposalReference(entry.id, ecosystem)}
        </a>
        {title ? <span title={title}>{truncateTitle(title)}</span> : null}
      </span>
      <span className="centrality-ranking-entry__value">
        {formatCentralityValue(metric, entry.value)}
      </span>
    </div>
  );
}

export function CentralitySection({
  ecosystem,
  ecosystemBase,
  selectedSourceIds,
  sectionSourceView,
  setSectionSourceView,
  centralityComparison,
}) {
  const snapshot = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const meta = centralityComparison?.meta || {};
  const byApproach = centralityComparison?.by_approach || {};
  const approachOrder = meta.approach_order || [];
  const metricOrder = meta.metric_order || [];
  const topN = Number(meta.top_n || 5);
  const llmModel = meta.llm_model || '';
  const [concordanceScope, setConcordanceScope] = useState(CONCORDANCE_SCOPE_TOP);
  const [highlightedId, setHighlightedId] = useState(null);
  const rankingRows = useMemo(() => approachOrder.flatMap((approach) => {
    const approachData = byApproach[approach] || {};
    const approachLabel = getDependencyApproachLabel(
      approach,
      approach === BODY_EXTRACTED_LLM ? llmModel : '',
    );
    return Array.from({ length: topN }, (_unused, rankIndex) => ({
      id: `${approach}-${rankIndex + 1}`,
      approach,
      approachLabel,
      rank: rankIndex + 1,
      highlightedId,
      linkMode,
      snapshot,
      entries: Object.fromEntries(
        metricOrder.map((metric) => [
          metric,
          approachData.top_by_metric?.[metric]?.[rankIndex] || null,
        ]),
      ),
    }));
  }), [
    approachOrder,
    byApproach,
    highlightedId,
    linkMode,
    llmModel,
    metricOrder,
    snapshot,
    topN,
  ]);

  const concordance = centralityComparison?.concordance?.[concordanceScope] || {};
  const scopeItemCount = meta.scope_item_counts?.[concordanceScope];
  const approachConcordance = concordance.across_approaches || [];
  const measureConcordance = useMemo(() => (
    concordance.across_measures || []
  ).map((row) => ({
    ...row,
    displayLabel: getDependencyApproachLabel(
      row.approach,
      row.approach === BODY_EXTRACTED_LLM ? llmModel : '',
    ),
  })), [concordance, llmModel]);

  if (!approachOrder.length || !rankingRows.length) return null;

  return (
    <section className="dashboard-section">
      <div className="dashboard-section__header">
        <h2 className="dashboard-section__title">Centrality</h2>
        <SectionSourceToggle
          ecosystemBase={ecosystemBase}
          selectedSourceIds={selectedSourceIds}
          value={sectionSourceView}
          onChange={setSectionSourceView}
          supportsMerged
        />
      </div>

      <ExportableCard className="mb-4" exportTitle="Top Central IPs">
        <h3>Top Central IPs</h3>
        <p>
          The highest-ranked IPs under four complementary centrality measures,
          compared across the Preamble, Regex, and LLM interrelation networks.
        </p>
        <div className="centrality-ranking-table-wrap">
          <DataTable
            value={rankingRows}
            dataKey="id"
            size="small"
            rowGroupMode="rowspan"
            groupRowsBy="approachLabel"
            className="centrality-ranking-table"
            tableStyle={{ minWidth: '72rem' }}
          >
            <Column
              field="approachLabel"
              header="Approach"
              headerClassName="centrality-ranking-table__approach-column"
              bodyClassName="centrality-ranking-table__approach-column"
            />
            <Column
              field="rank"
              header="Rank"
              headerClassName="centrality-ranking-table__rank-column"
              bodyClassName="centrality-ranking-table__rank-column"
            />
            {metricOrder.map((metric) => (
              <Column
                key={metric}
                header={COMPACT_METRIC_LABELS[metric] || meta.metric_labels?.[metric] || metric}
                body={(row) => (
                  <CentralityEntry
                    entry={row.entries[metric]}
                    metric={metric}
                    ecosystem={ecosystem}
                    snapshot={row.snapshot}
                    linkMode={row.linkMode}
                    highlightedId={row.highlightedId}
                    setHighlightedId={setHighlightedId}
                  />
                )}
              />
            ))}
          </DataTable>
        </div>
      </ExportableCard>

      <ExportableCard className="mb-4" exportTitle="Centrality Ranking Concordance">
        <h3>Centrality Ranking Concordance</h3>
        <p>
          Kendall&apos;s W measures agreement among complete centrality rankings.
          By default, it compares the distinct IPs represented in the Top-{topN} table;
          the full catalog can be selected instead.
          A value of 0 indicates no concordance; a value of 1 indicates identical rankings.
        </p>
        <CollapsibleControls>
          <div className="network-layout-picker">
            <div className="network-layout-picker__label">Scope</div>
            <div className="network-layout-picker__options centrality-concordance-scope-options">
              {[
                { value: CONCORDANCE_SCOPE_TOP, label: `Top ${topN}` },
                { value: CONCORDANCE_SCOPE_ALL, label: 'All IPs' },
              ].map((option) => (
                <label key={option.value} className="network-layout-picker__option">
                  <RadioButton
                    inputId={`centrality-concordance-scope-${option.value}`}
                    name="centrality-concordance-scope"
                    value={option.value}
                    checked={concordanceScope === option.value}
                    onChange={(event) => setConcordanceScope(event.value)}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
              <span className="centrality-concordance-scope-count">
                {formatScopeItemCount(scopeItemCount)}
              </span>
            </div>
          </div>
        </CollapsibleControls>
        <div className="centrality-concordance-grid">
          <section className="centrality-concordance-panel">
            <h4>Across Extraction Approaches</h4>
            <DataTable
              value={approachConcordance}
              dataKey="metric"
              size="small"
              className="centrality-concordance-table"
            >
              <Column field="label" header="Centrality Measure" />
              <Column
                field="kendalls_w"
                header="Kendall’s W"
                body={(row) => formatConcordance(row.kendalls_w)}
              />
            </DataTable>
          </section>
          <section className="centrality-concordance-panel">
            <h4>Across Centrality Measures</h4>
            <DataTable
              value={measureConcordance}
              dataKey="approach"
              size="small"
              className="centrality-concordance-table"
            >
              <Column field="displayLabel" header="Extraction Approach" />
              <Column
                field="kendalls_w"
                header="Kendall’s W"
                body={(row) => formatConcordance(row.kendalls_w)}
              />
            </DataTable>
          </section>
        </div>
      </ExportableCard>
    </section>
  );
}
