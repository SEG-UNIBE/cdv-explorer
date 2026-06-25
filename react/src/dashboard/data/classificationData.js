import { CLASSIFICATION_DIMENSIONS } from '../constants';
import { collectProposalRefs, makeProposalRef, proposalRefKey } from './proposalRefs';

function normalizeCategoryValue(value) {
  const text = String(value || '').trim();
  return text || 'Unspecified';
}

function normalizeChordLayer(value) {
  const text = String(value || '').trim();
  if (!text || text.includes('Unknown')) {
    return 'Unspecified';
  }
  return text;
}

function normalizeChordStatus(value) {
  const text = String(value || '').trim() || 'Unknown Status';
  const base = text.split('(')[0].trim() || 'Unknown Status';
  return base.includes('Unknown') ? 'Unknown Status' : base;
}

function normalizeChordType(value) {
  const text = String(value || '').trim() || 'Unknown Type';
  const aliases = {
    Standard: 'Standards Track',
    Standards: 'Standards Track',
    'Standard Track': 'Standards Track',
    'Standards-Track': 'Standards Track',
  };
  const normalized = aliases[text] || text;
  return normalized.includes('Unknown') ? 'Unknown Type' : normalized;
}

const FIELD_NORMALIZERS = {
  layer: normalizeChordLayer,
  status: normalizeChordStatus,
  type: normalizeChordType,
};

function normalizeChordValueForField(field, value) {
  const normalizer = FIELD_NORMALIZERS[field];
  if (normalizer) return normalizer(value);
  const text = String(value || '').trim();
  return text || 'Unspecified';
}

export function buildFacetDistribution(nodes, field) {
  const counts = new Map();
  const bipsByCategory = new Map();

  (nodes || []).forEach((node) => {
    const category = normalizeCategoryValue(node?.[field]);
    counts.set(category, (counts.get(category) || 0) + 1);

    if (node?.id != null) {
      if (!bipsByCategory.has(category)) {
        bipsByCategory.set(category, new Map());
      }
      const ref = makeProposalRef(node);
      bipsByCategory.get(category).set(proposalRefKey(ref), ref);
    }
  });

  return Array.from(counts.entries())
    .map(([id, value]) => ({
      id,
      value,
      bips: collectProposalRefs(bipsByCategory.get(id)),
    }))
    .sort((left, right) => right.value - left.value || left.id.localeCompare(right.id));
}

export function buildFacetTimeline(nodes, field) {
  const countsByYear = new Map();
  const bipsByYear = new Map();
  const allCategories = new Set();

  (nodes || []).forEach((node) => {
    if (!node?.created) {
      return;
    }

    const year = new Date(node.created).getFullYear();
    if (!Number.isFinite(year) || year <= 1900) {
      return;
    }

    const category = normalizeCategoryValue(node?.[field]);
    allCategories.add(category);
    const hasId = node?.id != null;

    if (!countsByYear.has(year)) {
      countsByYear.set(year, new Map());
    }
    if (!bipsByYear.has(year)) {
      bipsByYear.set(year, new Map());
    }

    const yearMap = countsByYear.get(year);
    yearMap.set(category, (yearMap.get(category) || 0) + 1);

    if (hasId) {
      const yearBipsMap = bipsByYear.get(year);
      if (!yearBipsMap.has(category)) {
        yearBipsMap.set(category, new Map());
      }
      const ref = makeProposalRef(node);
      yearBipsMap.get(category).set(proposalRefKey(ref), ref);
    }
  });

  const categories = Array.from(allCategories).sort((left, right) => left.localeCompare(right));
  const rows = Array.from(countsByYear.entries())
    .sort((left, right) => left[0] - right[0])
    .map(([year, categoryMap]) => {
      const values = {};
      const bips = {};
      const yearBipsMap = bipsByYear.get(year) || new Map();
      categories.forEach((category) => {
        values[category] = categoryMap.get(category) || 0;
        bips[category] = collectProposalRefs(yearBipsMap.get(category));
      });

      return {
        year: String(year),
        values,
        bips,
      };
    });

  return {
    categories,
    rows,
  };
}

export function buildClassificationChordData(
  nodes,
  categoryDomains = {},
  dimensions = CLASSIFICATION_DIMENSIONS,
) {
  const groups = [];
  const groupIndexByKey = new Map();
  const pairCounts = new Map();
  const pairBips = new Map();

  dimensions.forEach(({ field, label }) => {
    const categories = Array.from(new Set(
      (Array.isArray(categoryDomains[field]) ? categoryDomains[field] : [])
        .map((category) => normalizeChordValueForField(field, category))
    ));
    categories.forEach((category) => {
      const key = `${field}|||${category}`;
      groupIndexByKey.set(key, groups.length);
      groups.push({
        id: key,
        label: `${label}: ${category}`,
        dimension: field,
        category,
      });
    });
  });

  const dimPairs = [];
  for (let i = 0; i < dimensions.length; i += 1) {
    for (let j = i + 1; j < dimensions.length; j += 1) {
      dimPairs.push([dimensions[i].field, dimensions[j].field]);
    }
  }

  (nodes || []).forEach((node) => {
    const hasId = node?.id != null;
    const ref = hasId ? makeProposalRef(node) : null;
    const refKey = hasId ? proposalRefKey(ref) : null;
    const values = {};
    dimensions.forEach(({ field }) => {
      values[field] = normalizeChordValueForField(field, node?.[field]);
    });

    dimPairs.forEach(([leftField, rightField]) => {
      const leftKey = `${leftField}|||${values[leftField]}`;
      const rightKey = `${rightField}|||${values[rightField]}`;
      const leftIndex = groupIndexByKey.get(leftKey);
      const rightIndex = groupIndexByKey.get(rightKey);

      if (leftIndex == null || rightIndex == null) {
        return;
      }

      const pairKey = [leftIndex, rightIndex].sort((left, right) => left - right).join('|||');
      pairCounts.set(pairKey, (pairCounts.get(pairKey) || 0) + 1);

      if (hasId) {
        if (!pairBips.has(pairKey)) {
          pairBips.set(pairKey, new Map());
        }
        pairBips.get(pairKey).set(refKey, ref);
      }
    });
  });

  const matrix = Array.from({ length: groups.length }, () => Array(groups.length).fill(0));
  pairCounts.forEach((count, key) => {
    const [leftIndex, rightIndex] = key.split('|||').map(Number);
    matrix[leftIndex][rightIndex] = count;
    matrix[rightIndex][leftIndex] = count;
  });

  return {
    groups,
    matrix,
    pairBips: Object.fromEntries(
      Array.from(pairBips.entries()).map(([key, bipMap]) => [
        key,
        collectProposalRefs(bipMap),
      ])
    ),
  };
}

export function buildClassificationRelationRows(nodes, dimensions = CLASSIFICATION_DIMENSIONS) {
  const dim0 = dimensions[0];
  const dim1 = dimensions[1];
  const dim2 = dimensions[2];

  const pairsMap = new Map();
  const tripletsMap = new Map();

  if (!dim0 || !dim1) {
    return { pairs: [], triplets: [] };
  }

  (nodes || []).forEach((node) => {
    if (node?.id == null) {
      return;
    }
    const ref = makeProposalRef(node);
    const refKey = proposalRefKey(ref);

    const v0 = normalizeChordValueForField(dim0.field, node?.[dim0.field]);
    const v1 = normalizeChordValueForField(dim1.field, node?.[dim1.field]);

    const pairKey = `${v0}|||${v1}`;
    if (!pairsMap.has(pairKey)) {
      pairsMap.set(pairKey, { [dim0.field]: v0, [dim1.field]: v1, count: 0, bips: new Map() });
    }
    const pairEntry = pairsMap.get(pairKey);
    pairEntry.count += 1;
    pairEntry.bips.set(refKey, ref);

    if (dim2) {
      const v2 = normalizeChordValueForField(dim2.field, node?.[dim2.field]);
      const tripletKey = `${v0}|||${v1}|||${v2}`;
      if (!tripletsMap.has(tripletKey)) {
        tripletsMap.set(tripletKey, { [dim0.field]: v0, [dim1.field]: v1, [dim2.field]: v2, count: 0, bips: new Map() });
      }
      const tripletEntry = tripletsMap.get(tripletKey);
      tripletEntry.count += 1;
      tripletEntry.bips.set(refKey, ref);
    }
  });

  const finalize = (map) => Array.from(map.values())
    .map((entry) => ({
      ...entry,
      bips: collectProposalRefs(entry.bips),
    }))
    .sort((left, right) => (
      right.count - left.count ||
      String(left[dim0.field] || '').localeCompare(String(right[dim0.field] || '')) ||
      String(left[dim1.field] || '').localeCompare(String(right[dim1.field] || ''))
    ));

  return {
    pairs: finalize(pairsMap),
    triplets: finalize(tripletsMap),
  };
}
