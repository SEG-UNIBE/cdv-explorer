import { useMemo, useState } from 'react';

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
  if (field === 'author') {
    return String(row.displayAuthor || row.author || '');
  }
  return Number(row[field] || 0);
}

export const AuthorCentralityTable = ({
  rows,
  columns,
  defaultSortField,
  defaultSortOrder = -1,
}) => {
  const [globalFilter, setGlobalFilter] = useState('');
  const [sortField, setSortField] = useState(defaultSortField);
  const [sortDirection, setSortDirection] = useState(defaultSortOrder === -1 ? 'desc' : 'asc');

  const filteredRows = useMemo(() => {
    const search = globalFilter.trim().toLowerCase();
    if (!search) {
      return rows;
    }

    return rows.filter((row) => String(row.author || '').toLowerCase().includes(search));
  }, [globalFilter, rows]);

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
      return String(left.displayAuthor || left.author || '').localeCompare(
        String(right.displayAuthor || right.author || ''),
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

  return (
    <div className="centrality-table">
      <div className="centrality-table__header">
        <span className="centrality-table__filter">
          <input
            className="p-inputtext"
            value={globalFilter}
            onChange={(event) => setGlobalFilter(event.target.value)}
            placeholder="Filter authors"
            aria-label="Filter authors"
          />
        </span>
      </div>
      {sortedRows.length ? (
        <div className="centrality-table__wrap">
          <table className="analysis-table">
            <thead>
              <tr>
                <th>
                  <button type="button" className="analysis-table__sort-button" onClick={() => handleSortChange('author')}>
                    {`Author${getSortIndicator('author')}`}
                  </button>
                </th>
                {columns.map((column) => (
                  <th key={column.field}>
                    <button type="button" className="analysis-table__sort-button" onClick={() => handleSortChange(column.field)}>
                      {`${column.header}${getSortIndicator(column.field)}`}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row) => (
                <tr key={row.author}>
                  <td>{row.displayAuthor || row.author}</td>
                  {columns.map((column) => {
                    const value = column.format === 'integer'
                      ? Number(row[column.field] || 0)
                      : formatNumber(row[column.field], column.digits || 4);
                    const rank = column.showRank ? row[`${column.field}Rank`] : null;
                    return (
                      <td key={column.field}>
                        {value}
                        <RankBadge rank={rank} />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="centrality-table centrality-table--empty">
          <p className="centrality-table__empty">No authors found.</p>
        </div>
      )}
    </div>
  );
};
