import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { formatProposalLabel, getProposalUrl } from './proposalLinks';

function buildProposalUrl(id, snapshotLabel, linkMode, ecosystem) {
  return getProposalUrl(id, snapshotLabel, { linkMode }, ecosystem);
}

export const ClassificationRelationTable = ({
  rows,
  dimensions = [],
  proposalShortLabel = 'IP',
}) => {
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();
  const totalCount = rows.reduce((sum, row) => sum + Number(row.count || 0), 0);

  return (
    <DataTable
      value={rows}
      sortField="count"
      sortOrder={-1}
      removableSort
      scrollable
      scrollHeight="460px"
      size="small"
      className="centrality-table"
      emptyMessage="No classification combinations found."
    >
      {dimensions.map((dim) => (
        <Column key={dim.field} field={dim.field} header={dim.label} sortable />
      ))}
      <Column field="count" header={`${proposalShortLabel}s`} sortable body={(row) => Number(row.count || 0)} />
      <Column
        field="share"
        header="Share"
        body={(row) => `${(((Number(row.count || 0) / Math.max(totalCount, 1)) * 100).toFixed(1)).replace(/\.0$/, '')}%`}
      />
      <Column
        field="bips"
        header={proposalShortLabel}
        body={(row) => (
          <span>
            {(row.bips || []).map((bip, index) => (
              <span key={bip}>
                {index > 0 ? ', ' : ''}
                <a
                  href={buildProposalUrl(bip, snapshotLabel, linkMode, ecosystem)}
                  target="_blank"
                  rel="noreferrer"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {formatProposalLabel(bip, ecosystem)}
                </a>
              </span>
            ))}
          </span>
        )}
      />
    </DataTable>
  );
};
