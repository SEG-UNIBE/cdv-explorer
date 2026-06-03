import { formatProposalReference, getProposalUrl } from './proposalLinks';

function isRefShape(value) {
  return value && typeof value === 'object' && 'id' in value;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderLegacyProposalList(proposalIds, snapshotLabel, opts) {
  const { linkMode, ecosystem } = opts;
  return proposalIds
    .map((proposalId) => (
      `<a href="${escapeHtml(getProposalUrl(proposalId, snapshotLabel, { linkMode }, ecosystem))}" target="_blank" rel="noreferrer">` +
      `${escapeHtml(formatProposalReference(proposalId, ecosystem))}</a>`
    ))
    .join(', ');
}

function renderRefGroup(refs, snapshotLabel, source, opts) {
  const { linkMode } = opts;
  return refs
    .map((ref) => {
      const url = typeof source?.getProposalUrl === 'function'
        ? source.getProposalUrl(ref.id, snapshotLabel, { linkMode })
        : '#';
      const label = typeof source?.formatProposalReference === 'function'
        ? source.formatProposalReference(ref.id)
        : ref.id;
      return `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`;
    })
    .join(', ');
}

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

  const list = Array.isArray(proposals) ? proposals : [];
  if (list.length === 0) {
    return emptyText;
  }

  // Legacy path: flat array of id strings/numbers — single-source semantics,
  // routes through the ecosystem-level link helpers.
  if (!isRefShape(list[0])) {
    return `${label} ${renderLegacyProposalList(list, snapshotLabel, { linkMode, ecosystem })}`;
  }

  // Tuple path: refs are { source, id } — group by source and use each source's
  // own link/format builders so SLIPs link to satoshilabs/slips, BIPs to bitcoin/bips, etc.
  const sourcesMap = ecosystem?.sources || {};
  const sourceOrder = ecosystem?.sourceOrder || Object.keys(sourcesMap);
  const groups = new Map();
  list.forEach((ref) => {
    const sourceId = ref?.source || '';
    if (!groups.has(sourceId)) groups.set(sourceId, []);
    groups.get(sourceId).push(ref);
  });

  const orderedSourceIds = [
    ...sourceOrder.filter((id) => groups.has(id)),
    ...Array.from(groups.keys()).filter((id) => !sourceOrder.includes(id)),
  ];

  if (orderedSourceIds.length === 1) {
    const sourceId = orderedSourceIds[0];
    const source = sourcesMap[sourceId] || ecosystem;
    return `${label} ${renderRefGroup(groups.get(sourceId), snapshotLabel, source, { linkMode })}`;
  }

  const sections = orderedSourceIds.map((sourceId) => {
    const source = sourcesMap[sourceId] || ecosystem;
    const heading = escapeHtml(source?.shortLabel || source?.acronym || sourceId || 'IPs');
    const body = renderRefGroup(groups.get(sourceId), snapshotLabel, source, { linkMode });
    return `<strong>${heading}:</strong> ${body}`;
  });

  return `${label}<br/>${sections.join('<br/>')}`;
}

export const renderBipListHtml = renderProposalListHtml;
