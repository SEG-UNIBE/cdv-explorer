import * as d3 from 'd3';

const PALETTE = [
  ...d3.schemeTableau10,
  ...d3.schemeSet2,
  ...d3.schemeSet3,
];

export function getClassificationColorMap(dimension, categories = []) {
  const uniqueCategories = Array.from(
    new Set((categories || []).map((category) => String(category || '').trim()).filter(Boolean))
  );

  return Object.fromEntries(
    uniqueCategories.map((category, index) => [category, PALETTE[index % PALETTE.length]])
  );
}
