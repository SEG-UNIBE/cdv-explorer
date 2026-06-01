import { formatProposalReference, getProposalUrl } from './proposalLinks';

export function renderProposalListHtml(proposals, snapshotOrOptions = null, options = {}) {
  const snapshotLabel = typeof snapshotOrOptions === 'string' || snapshotOrOptions == null
    ? snapshotOrOptions
    : null;
  const {
    emptyText = 'No proposal list available.',
    label = 'List:',
    linkMode = 'history',
    ecosystem = null,
  } = snapshotLabel == null && snapshotOrOptions && typeof snapshotOrOptions === 'object'
    ? snapshotOrOptions
    : options;

  const proposalIds = Array.isArray(proposals) ? proposals : [];
  if (proposalIds.length === 0) {
    return emptyText;
  }

  const proposalLinks = proposalIds
    .map((proposalId) => (
      `<a href="${getProposalUrl(proposalId, snapshotLabel, { linkMode }, ecosystem)}" target="_blank" rel="noreferrer">` +
      `${formatProposalReference(proposalId, ecosystem)}</a>`
    ))
    .join(', ');

  return `${label} ${proposalLinks}`;
}

export const renderBipListHtml = renderProposalListHtml;
