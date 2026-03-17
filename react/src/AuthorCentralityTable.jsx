import { useMemo, useState } from 'react';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { InputText } from 'primereact/inputtext';

function formatNumber(value, digits = 4) {
  return Number(value || 0)
    .toFixed(digits)
    .replace(/\.?0+$/, '');
}

export const AuthorCentralityTable = ({
  rows,
  columns,
  defaultSortField,
  defaultSortOrder = -1,
}) => {
  const [globalFilter, setGlobalFilter] = useState('');

  const filteredRows = useMemo(() => {
    const search = globalFilter.trim().toLowerCase();
    if (!search) {
      return rows;
    }

    return rows.filter((row) => String(row.author || '').toLowerCase().includes(search));
  }, [globalFilter, rows]);

  const header = (
    <div className="centrality-table__header">
      <span className="p-input-icon-left centrality-table__filter">
        <InputText
          value={globalFilter}
          onChange={(event) => setGlobalFilter(event.target.value)}
          placeholder="Filter authors"
        />
      </span>
    </div>
  );

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
      <Column field="author" header="Author" sortable />
      {columns.map((column) => (
        <Column
          key={column.field}
          field={column.field}
          header={column.header}
          sortable
          body={(row) => (
            column.format === 'integer'
              ? Number(row[column.field] || 0)
              : formatNumber(row[column.field], column.digits || 4)
          )}
        />
      ))}
    </DataTable>
  );
};
