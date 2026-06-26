import { useMemo } from 'react';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
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

function formatNumber(value, digits = 4) {
  return Number(value || 0)
    .toFixed(digits)
    .replace(/\.?0+$/, '');
}

function RankBadge({ rank }) {
  if (!Number.isFinite(Number(rank)) || Number(rank) <= 0) {
    return null;
  }
  return <span className="rank-badge">#{rank}</span>;
}

export const ProposalGraphMetricsTable = ({
  rows,
  proposalFilterIds = [],
  defaultSortField,
  defaultSortOrder = -1,
}) => {
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();
  const sourceSlugToSourceId = useMemo(() => (
    Object.fromEntries(
      Object.values(ecosystem?.sources || {}).map((source) => [
        String(source?.sourceSlug || source?.sourceId || '').trim(),
        String(source?.sourceId || source?.sourceSlug || '').trim(),
      ])
    )
  ), [ecosystem]);

  const filteredRows = useMemo(() => {
    const filteredProposalKeys = new Set(
      (proposalFilterIds || [])
        .filter((entry) => entry && typeof entry === 'object')
        .map((entry) => `${String(entry.source || '').trim()}|${String(entry.id || '').trim()}`)
    );

    const rowMatchesProposalFilter = (row) => {
      if (filteredProposalKeys.size === 0) {
        return true;
      }

      const rawId = String(row.id || '').trim();
      const separatorIndex = rawId.indexOf(':');
      const rowSourceSlug = separatorIndex >= 0 ? rawId.slice(0, separatorIndex) : '';
      const rowSourceId = sourceSlugToSourceId[rowSourceSlug] || rowSourceSlug;
      const rowProposalId = normalizeProposalId(rawId, ecosystem);

      return filteredProposalKeys.has(`${rowSourceId}|${rowProposalId}`);
    };

    return rows.filter((row) => (
      rowMatchesProposalFilter(row)
    ));
  }, [ecosystem, proposalFilterIds, rows, sourceSlugToSourceId]);

  return (
    <DataTable
      value={filteredRows}
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
      <Column field="in_degree" header="In Degree" sortable body={(row) => <span>{Number(row.in_degree || 0)}<RankBadge rank={row.in_degree_rank} /></span>} />
      <Column field="out_degree" header="Out Degree" sortable body={(row) => <span>{Number(row.out_degree || 0)}<RankBadge rank={row.out_degree_rank} /></span>} />
      <Column
        field="weighted_eigenvector"
        header="Weighted Eigenvector"
        sortable
        body={(row) => <span>{formatNumber(row.weighted_eigenvector, 4)}<RankBadge rank={row.weighted_eigenvector_rank} /></span>}
      />
      <Column
        field="pagerank"
        header="PageRank"
        sortable
        body={(row) => <span>{formatNumber(row.pagerank, 4)}<RankBadge rank={row.pagerank_rank} /></span>}
      />
      <Column
        field="betweenness"
        header="Betweenness"
        sortable
        body={(row) => <span>{formatNumber(row.betweenness, 4)}<RankBadge rank={row.betweenness_rank} /></span>}
      />
    </DataTable>
  );
};
