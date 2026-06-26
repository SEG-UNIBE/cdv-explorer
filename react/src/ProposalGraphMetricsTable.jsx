import { useMemo, useState } from 'react';
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

function compareValues(left, right, direction) {
  if (typeof left === 'number' && typeof right === 'number') {
    return (left - right) * direction;
  }
  return String(left || '').localeCompare(String(right || ''), undefined, { numeric: true }) * direction;
}

function getSortableValue(row, field) {
  if (field === 'id') {
    return String(row.displayLabel || row.id || '');
  }
  return Number(row[field] || 0);
}

export function ProposalGraphMetricsTable({
  rows,
  proposalFilterIds = [],
  defaultSortField,
  defaultSortOrder = -1,
}) {
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();
  const [sortField, setSortField] = useState(defaultSortField);
  const [sortDirection, setSortDirection] = useState(defaultSortOrder === -1 ? 'desc' : 'asc');

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

    return rows
      .filter((row) => rowMatchesProposalFilter(row))
      .map((row) => {
        const title = String(row.title || '').trim();
        const normalized = normalizeProposalId(row.id, ecosystem);
        return {
          ...row,
          displayLabel: normalized ? formatProposalLabel(row.id, ecosystem) : String(row.id || ''),
          displayUrl: getProposalUrl(row.id, snapshotLabel, { linkMode }, ecosystem),
          displayTitle: title,
          displayShortTitle: truncateTitle(title, 50),
        };
      });
  }, [ecosystem, linkMode, proposalFilterIds, rows, snapshotLabel, sourceSlugToSourceId]);

  const sortedRows = useMemo(() => {
    const direction = sortDirection === 'desc' ? -1 : 1;
    return [...filteredRows].sort((left, right) => {
      const primary = compareValues(
        getSortableValue(left, sortField),
        getSortableValue(right, sortField),
        direction,
      );
      if (primary !== 0) {
        return primary;
      }
      return String(left.displayLabel || left.id || '').localeCompare(
        String(right.displayLabel || right.id || ''),
        undefined,
        { numeric: true }
      );
    });
  }, [filteredRows, sortDirection, sortField]);

  const handleSortChange = (field) => {
    if (field === sortField) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortField(field);
    setSortDirection('desc');
  };

  const getSortIndicator = (field) => {
    if (field !== sortField) {
      return '';
    }
    return sortDirection === 'asc' ? ' ↑' : ' ↓';
  };

  if (sortedRows.length === 0) {
    return (
      <div className="centrality-table centrality-table--empty">
        <p className="centrality-table__empty">No proposals found.</p>
      </div>
    );
  }

  return (
    <div className="centrality-table">
      <div className="centrality-table__wrap">
        <table className="analysis-table">
          <thead>
            <tr>
              <th>
                <button type="button" className="analysis-table__sort-button" onClick={() => handleSortChange('id')}>
                  {`IP${getSortIndicator('id')}`}
                </button>
              </th>
              <th>
                <button type="button" className="analysis-table__sort-button" onClick={() => handleSortChange('in_degree')}>
                  {`In Degree${getSortIndicator('in_degree')}`}
                </button>
              </th>
              <th>
                <button type="button" className="analysis-table__sort-button" onClick={() => handleSortChange('out_degree')}>
                  {`Out Degree${getSortIndicator('out_degree')}`}
                </button>
              </th>
              <th>
                <button type="button" className="analysis-table__sort-button" onClick={() => handleSortChange('weighted_eigenvector')}>
                  {`Weighted Eigenvector${getSortIndicator('weighted_eigenvector')}`}
                </button>
              </th>
              <th>
                <button type="button" className="analysis-table__sort-button" onClick={() => handleSortChange('pagerank')}>
                  {`PageRank${getSortIndicator('pagerank')}`}
                </button>
              </th>
              <th>
                <button type="button" className="analysis-table__sort-button" onClick={() => handleSortChange('betweenness')}>
                  {`Betweenness${getSortIndicator('betweenness')}`}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => (
              <tr key={row.id}>
                <td>
                  <span>
                    <a href={row.displayUrl} target="_blank" rel="noreferrer">
                      {row.displayLabel}
                    </a>
                    {row.displayShortTitle ? (
                      <span title={row.displayTitle}>{` ${row.displayShortTitle}`}</span>
                    ) : null}
                  </span>
                </td>
                <td>{Number(row.in_degree || 0)}<RankBadge rank={row.in_degree_rank} /></td>
                <td>{Number(row.out_degree || 0)}<RankBadge rank={row.out_degree_rank} /></td>
                <td>{formatNumber(row.weighted_eigenvector, 4)}<RankBadge rank={row.weighted_eigenvector_rank} /></td>
                <td>{formatNumber(row.pagerank, 4)}<RankBadge rank={row.pagerank_rank} /></td>
                <td>{formatNumber(row.betweenness, 4)}<RankBadge rank={row.betweenness_rank} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
