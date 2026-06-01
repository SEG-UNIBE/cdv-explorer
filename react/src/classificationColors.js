const PALETTE = [
  '#4e79a7',
  '#f28e2c',
  '#e15759',
  '#76b7b2',
  '#59a14f',
  '#edc949',
  '#af7aa1',
  '#ff9da7',
  '#9c755f',
  '#bab0ab',
  '#66c2a5',
  '#fc8d62',
  '#8da0cb',
  '#e78ac3',
  '#a6d854',
  '#ffd92f',
  '#e5c494',
  '#b3b3b3',
  '#8dd3c7',
  '#ffffb3',
  '#bebada',
  '#fb8072',
  '#80b1d3',
  '#fdb462',
  '#b3de69',
  '#fccde5',
  '#d9d9d9',
  '#bc80bd',
  '#ccebc5',
  '#ffed6f',
];
const FIXED_STATUS_COLORS = {
  Draft: '#4e79a7',
  Active: '#f28e2c',
  Proposed: '#59a14f',
  Deferred: '#76b7b2',
  Rejected: '#e15759',
  Withdrawn: '#edc949',
  Final: '#af7aa1',
  Replaced: '#ff9da7',
  Obsolete: '#9c755f',
  Accepted: '#bab0ab',
  Complete: '#66c2a5',
  Deployed: '#fc8d62',
  Closed: '#868e96',
  Unknown: '#bab0ab',
  'Unknown Status': '#bab0ab',
};

export function getClassificationColorMap(dimension, categories = []) {
  const uniqueCategories = Array.from(
    new Set((categories || []).map((category) => String(category || '').trim()).filter(Boolean))
  );
  let fallbackIndex = 0;

  return Object.fromEntries(
    uniqueCategories.map((category) => {
      if (dimension === 'status' && FIXED_STATUS_COLORS[category]) {
        return [category, FIXED_STATUS_COLORS[category]];
      }

      const color = PALETTE[fallbackIndex % PALETTE.length];
      fallbackIndex += 1;
      return [category, color];
    })
  );
}
