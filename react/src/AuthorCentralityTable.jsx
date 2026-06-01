import { useMemo, useState } from 'react';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { InputText } from 'primereact/inputtext';

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
    rankMap[row.author] = currentRank;
  });
  return rankMap;
}

export const AuthorCentralityTable = ({
  rows,
  columns,
  defaultSortField,
  defaultSortOrder = -1,
}) => {
  const [globalFilter, setGlobalFilter] = useState('');

  const ranksByField = useMemo(() => {
    const result = {};
    columns.filter((col) => col.showRank).forEach((col) => {
      result[col.field] = buildRankMap(rows, col.field);
    });
    return result;
  }, [rows, columns]);

  const filteredRows = useMemo(() => {
    const search = globalFilter.trim().toLowerCase();
    if (!search) {
      return rows;
    }

    return rows.filter((row) => String(row.author || '').toLowerCase().includes(search));
  }, [globalFilter, rows]);

  const header = useMemo(() => (
    <div className="centrality-table__header">
      <span className="p-input-icon-left centrality-table__filter">
        <InputText
          value={globalFilter}
          onChange={(event) => setGlobalFilter(event.target.value)}
          placeholder="Filter authors"
          aria-label="Filter authors"
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
      emptyMessage="No authors found."
    >
      <Column
        field="author"
        header="Author"
        sortable
        body={(row) => row.displayAuthor || row.author}
      />
      {columns.map((column) => (
        <Column
          key={column.field}
          field={column.field}
          header={column.header}
          sortable
          body={(row) => {
            const value = column.format === 'integer'
              ? Number(row[column.field] || 0)
              : formatNumber(row[column.field], column.digits || 4);
            const rank = column.showRank ? ranksByField[column.field]?.[row.author] : null;
            return (
              <span>
                {value}
                {rank != null && (
                  <span className="rank-badge">#{rank}</span>
                )}
              </span>
            );
          }}
        />
      ))}
    </DataTable>
  );
};
