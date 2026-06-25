export function cleanAuthorName(author) {
  return String(author || '').split('<')[0].trim();
}

export function compareProposalIds(a, b) {
  const na = Number(a);
  const nb = Number(b);
  if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
  return String(a).localeCompare(String(b));
}

export function makeProposalRef(node) {
  return { source: node?.source || '', id: String(node?.id ?? '') };
}

export function proposalRefKey(ref) {
  return `${ref.source}|${ref.id}`;
}

function compareProposalRefs(a, b) {
  const sa = String(a?.source || '');
  const sb = String(b?.source || '');
  if (sa !== sb) return sa.localeCompare(sb);
  return compareProposalIds(a?.id, b?.id);
}

export function collectProposalRefs(refMap) {
  return Array.from((refMap || new Map()).values()).sort(compareProposalRefs);
}
