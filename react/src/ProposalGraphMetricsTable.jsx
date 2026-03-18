import { useMemo, useState } from 'react';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { InputText } from 'primereact/inputtext';

function normalizeProposalId(value) {
  const text = String(value ?? '').trim();
  if (!text) {
    return '';
  }

  const match = text.match(/^(?:bip\s*[- ]*)?0*(\d+)$/i);
  return match ? String(Number(match[1])) : text;
}

function getProposalHref(id) {
  const normalized = normalizeProposalId(id);
  return normalized ? `https://bips.dev/${normalized}/` : '#';
}

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

export const ProposalGraphMetricsTable = ({
  rows,
  proposalShortLabel = 'IP',
  defaultSortField,
  defaultSortOrder = -1,
}) => {
  const [globalFilter, setGlobalFilter] = useState('');

  const filteredRows = useMemo(() => {
    const search = globalFilter.trim().toLowerCase();
    if (!search) {
      return rows;
    }

    return rows.filter((row) => String(row.id || '').toLowerCase().includes(search));
  }, [globalFilter, rows]);

  const header = (
    <div className="centrality-table__header">
      <span className="p-input-icon-left centrality-table__filter">
        <InputText
          value={globalFilter}
          onChange={(event) => setGlobalFilter(event.target.value)}
          placeholder="Filter proposals"
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
      emptyMessage="No proposals found."
    >
      <Column
        field="id"
        header="IP"
        sortable
        body={(row) => {
          const normalized = normalizeProposalId(row.id);
          const title = String(row.title || '').trim();
          const shortTitle = truncateTitle(title, 50);
          return (
            <span>
              <a href={getProposalHref(row.id)} target="_blank" rel="noreferrer">
                {normalized ? `${proposalShortLabel} ${normalized}` : String(row.id || '')}
              </a>
              {shortTitle ? (
                <span title={title}>{` ${shortTitle}`}</span>
              ) : null}
            </span>
          );
        }}
      />
      <Column field="in_degree" header="In Degree" sortable body={(row) => Number(row.in_degree || 0)} />
      <Column field="out_degree" header="Out Degree" sortable body={(row) => Number(row.out_degree || 0)} />
      <Column
        field="betweenness"
        header="Betweenness"
        sortable
        body={(row) => formatNumber(row.betweenness, 4)}
      />
      <Column
        field="pagerank"
        header="PageRank"
        sortable
        body={(row) => formatNumber(row.pagerank, 4)}
      />
    </DataTable>
  );
};
