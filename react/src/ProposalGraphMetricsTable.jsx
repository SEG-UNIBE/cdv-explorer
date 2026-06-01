import { useMemo, useState } from 'react';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { InputText } from 'primereact/inputtext';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { formatProposalLabel, getProposalUrl, normalizeProposalId } from './proposalLinks';

function truncateTitle(value, maxLength = 40) {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength).trimEnd()}...`;
}

const RANK_FIELDS = ['in_degree', 'out_degree', 'weighted_eigenvector', 'pagerank', 'betweenness'];

function formatNumber(value, digits = 4) {
  return Number(value || 0)
    .toFixed(digits)
    .replace(/\.?0+$/, '');
}

function buildRankMap(rows, field) {
  const sorted = [...rows].sort((a, b) => (b[field] || 0) - (a[field] || 0));
  const rankMap = {};
  let currentRank = 0;
  let prevVal = null;
  sorted.forEach((row, i) => {
    const val = row[field] || 0;
    if (val !== prevVal) {
      currentRank = i + 1;
      prevVal = val;
    }
    rankMap[row.id] = currentRank;
  });
  return rankMap;
}

function RankBadge({ rank }) {
  return <span className="rank-badge">#{rank}</span>;
}

export const ProposalGraphMetricsTable = ({
  rows,
  proposalShortLabel = 'IP',
  defaultSortField,
  defaultSortOrder = -1,
}) => {
  const [globalFilter, setGlobalFilter] = useState('');
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

  const ranksByField = useMemo(() => {
    const result = {};
    RANK_FIELDS.forEach((field) => {
      result[field] = buildRankMap(rows, field);
    });
    return result;
  }, [rows]);

  const filteredRows = useMemo(() => {
    const search = globalFilter.trim().toLowerCase();
    if (!search) {
      return rows;
    }

    return rows.filter((row) =>
      String(row.id || '').toLowerCase().includes(search)
      || String(row.title || '').toLowerCase().includes(search)
    );
  }, [globalFilter, rows]);

  const header = useMemo(() => (
    <div className="centrality-table__header">
      <span className="p-input-icon-left centrality-table__filter">
        <InputText
          value={globalFilter}
          onChange={(event) => setGlobalFilter(event.target.value)}
          placeholder="Filter proposals"
          aria-label="Filter proposals"
        />
      </span>
    </div>
  ), [globalFilter]);

  return (
    <DataTable
      value={filteredRows}
      header={header}
      sortField={defaultSortField}
      sortOrder={defaultSortOrder}
      removableSort
      scrollable
      scrollHeight="420px"
      size="small"
      className="centrality-table"
      emptyMessage="No proposals found."
    >
      <Column
        field="id"
        header="IP"
        sortable
        body={(row) => {
          const normalized = normalizeProposalId(row.id, ecosystem);
          const title = String(row.title || '').trim();
          const shortTitle = truncateTitle(title, 50);
          return (
            <span>
              <a href={getProposalUrl(row.id, snapshotLabel, { linkMode }, ecosystem)} target="_blank" rel="noreferrer">
                {normalized ? formatProposalLabel(row.id, ecosystem) : String(row.id || '')}
              </a>
              {shortTitle ? (
                <span title={title}>{` ${shortTitle}`}</span>
              ) : null}
            </span>
          );
        }}
      />
      <Column field="in_degree" header="In Degree" sortable body={(row) => <span>{Number(row.in_degree || 0)}<RankBadge rank={ranksByField.in_degree[row.id]} /></span>} />
      <Column field="out_degree" header="Out Degree" sortable body={(row) => <span>{Number(row.out_degree || 0)}<RankBadge rank={ranksByField.out_degree[row.id]} /></span>} />
      <Column
        field="weighted_eigenvector"
        header="Weighted Eigenvector"
        sortable
        body={(row) => <span>{formatNumber(row.weighted_eigenvector, 4)}<RankBadge rank={ranksByField.weighted_eigenvector[row.id]} /></span>}
      />
      <Column
        field="pagerank"
        header="PageRank"
        sortable
        body={(row) => <span>{formatNumber(row.pagerank, 4)}<RankBadge rank={ranksByField.pagerank[row.id]} /></span>}
      />
      <Column
        field="betweenness"
        header="Betweenness"
        sortable
        body={(row) => <span>{formatNumber(row.betweenness, 4)}<RankBadge rank={ranksByField.betweenness[row.id]} /></span>}
      />
    </DataTable>
  );
};
