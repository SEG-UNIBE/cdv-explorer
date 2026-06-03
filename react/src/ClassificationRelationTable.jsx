import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { formatProposalLabel, getProposalUrl } from './proposalLinks';

function isProposalRef(value) {
  return value && typeof value === 'object' && 'id' in value;
}

function getSourceScopedEcosystem(ecosystem, sourceId) {
  const source = ecosystem?.sources?.[sourceId];
  return source ? { ...ecosystem, ...source } : ecosystem;
}

function getProposalRefKey(proposal) {
  return isProposalRef(proposal)
    ? `${proposal.source || ''}|${proposal.id}`
    : String(proposal);
}

function getProposalRefId(proposal) {
  return isProposalRef(proposal) ? proposal.id : proposal;
}

function getProposalRefEcosystem(proposal, ecosystem) {
  return isProposalRef(proposal)
    ? getSourceScopedEcosystem(ecosystem, proposal.source)
    : ecosystem;
}

export function buildClassificationRelationProposalUrl(proposal, snapshotLabel, linkMode, ecosystem) {
  return getProposalUrl(
    getProposalRefId(proposal),
    snapshotLabel,
    { linkMode },
    getProposalRefEcosystem(proposal, ecosystem)
  );
}

export function buildClassificationRelationProposalLabel(proposal, ecosystem) {
  return formatProposalLabel(
    getProposalRefId(proposal),
    getProposalRefEcosystem(proposal, ecosystem)
  );
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
              <span key={getProposalRefKey(bip)}>
                {index > 0 ? ', ' : ''}
                <a
                  href={buildClassificationRelationProposalUrl(bip, snapshotLabel, linkMode, ecosystem)}
                  target="_blank"
                  rel="noreferrer"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {buildClassificationRelationProposalLabel(bip, ecosystem)}
                </a>
              </span>
            ))}
          </span>
        )}
      />
    </DataTable>
  );
};
