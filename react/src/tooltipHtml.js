function normalizeTooltipRows(rows = []) {
  return rows
    .filter(Boolean)
    .map((row) => {
      if (Array.isArray(row)) {
        const [label, value] = row;
        return [label, value];
      }
      return [row.label, row.value];
    })
    .filter(([label, value]) => label && value !== undefined && value !== null && value !== '');
}

export function renderTooltipRowsHtml(rows = []) {
  const normalizedRows = normalizeTooltipRows(rows);
  if (normalizedRows.length === 0) {
    return '';
  }

  return (
    `<table class="tooltip-card__table" role="presentation">` +
    normalizedRows
      .map(([label, value]) => `<tr><th>${label}</th><td>${value}</td></tr>`)
      .join('') +
    `</table>`
  );
}

export function renderTooltipSectionHtml({
  labelHtml = '',
  bodyHtml = '',
} = {}) {
  if (!bodyHtml) {
    return '';
  }

  const label = labelHtml ? `<div class="tooltip-card__section-label">${labelHtml}</div>` : '';
  return (
    `<div class="tooltip-card__section">` +
    `${label}` +
    `<div class="tooltip-card__section-content">${bodyHtml}</div>` +
    `</div>`
  );
}

export function renderTooltipCardHtml({
  titleHtml = '',
  rows = [],
  bodyHtml = '',
} = {}) {
  const title = titleHtml ? `<div class="tooltip-card__title">${titleHtml}</div>` : '';
  const table = renderTooltipRowsHtml(rows);
  const body = bodyHtml ? `<div class="tooltip-card__body">${bodyHtml}</div>` : '';
  return `${title}${table}${body}`;
}
