export function renderBipListHtml(bips, options = {}) {
  const {
    emptyText = 'No BIP list available.',
    label = 'List:',
  } = options;

  const bipIds = Array.isArray(bips) ? bips : [];
  if (bipIds.length === 0) {
    return emptyText;
  }

  const bipLinks = bipIds
    .map((bip) => `<a href="https://bips.dev/${bip}/" target="_blank" rel="noreferrer">BIP${bip}</a>`)
    .join(', ');

  return `${label} ${bipLinks}`;
}
