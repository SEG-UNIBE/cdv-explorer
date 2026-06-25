import { compareProposalIds } from './proposalRefs';

export function normalizeProposalFilterValue(value) {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }

  const match = text.match(/^(?:bip\s*[- ]*)?0*(\d+)$/i);
  return match ? match[1] : text;
}

function normalizeIdForSource(id, source) {
  if (source && typeof source.normalizeProposalId === 'function') {
    return source.normalizeProposalId(id, { lowercaseFallback: true });
  }
  return normalizeProposalFilterValue(id);
}

function refKey(ref) {
  return `${ref?.source || ''}|${ref?.id ?? ''}`;
}

function normalizeAvailableProposalNode(entry, fallbackSource = '') {
  if (entry && typeof entry === 'object') {
    return entry;
  }
  return { source: fallbackSource, id: entry };
}

export function parseProposalFilterExpression(text, availableNodes = [], ecosystem = null) {
  const tokens = String(text || '')
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean);
  if (tokens.length === 0) return [];

  const sources = ecosystem?.sources || {};
  const sourceOrder = ecosystem?.sourceOrder || Object.keys(sources);
  const fallbackSource = ecosystem?.defaultSourceId || '';
  const hasSourceAwareInputs = Boolean(ecosystem)
    || (availableNodes || []).some((entry) => entry && typeof entry === 'object');
  const sourceByAcronym = {};
  sourceOrder.forEach((id) => {
    const acronym = sources[id]?.acronym;
    if (acronym) sourceByAcronym[acronym.toUpperCase()] = id;
  });

  const presentSources = new Set();
  const normalizedIdsBySource = new Map();
  (availableNodes || []).map((node) => normalizeAvailableProposalNode(node, fallbackSource)).forEach((node) => {
    if (node?.id == null) return;
    const sourceId = node.source || '';
    presentSources.add(sourceId);
    const source = sources[sourceId];
    const norm = normalizeIdForSource(node.id, source);
    if (!normalizedIdsBySource.has(sourceId)) {
      normalizedIdsBySource.set(sourceId, new Set());
    }
    normalizedIdsBySource.get(sourceId).add(norm);
  });

  const refs = [];
  const seen = new Set();
  const addRef = (source, id) => {
    const key = `${source}|${id}`;
    if (seen.has(key)) return;
    seen.add(key);
    refs.push({ source, id });
  };

  const acronymPattern = '[A-Za-z]+';

  for (const token of tokens) {
    let match = token.match(new RegExp(`^(${acronymPattern})\\s*[- ]*0*(\\d+)\\s*-\\s*(?:\\1\\s*[- ]*)?0*(\\d+)$`, 'i'));
    if (match) {
      const sourceId = sourceByAcronym[match[1].toUpperCase()];
      if (sourceId) {
        const lo = Math.min(Number(match[2]), Number(match[3]));
        const hi = Math.max(Number(match[2]), Number(match[3]));
        const present = normalizedIdsBySource.get(sourceId) || new Set();
        for (let n = lo; n <= hi; n += 1) {
          const norm = normalizeIdForSource(String(n), sources[sourceId]);
          if (present.has(norm)) addRef(sourceId, norm);
        }
        continue;
      }
    }

    match = token.match(/^0*(\d+)\s*-\s*0*(\d+)$/);
    if (match) {
      const lo = Math.min(Number(match[1]), Number(match[2]));
      const hi = Math.max(Number(match[1]), Number(match[2]));
      presentSources.forEach((sourceId) => {
        const present = normalizedIdsBySource.get(sourceId) || new Set();
        for (let n = lo; n <= hi; n += 1) {
          const norm = normalizeIdForSource(String(n), sources[sourceId]);
          if (present.has(norm)) addRef(sourceId, norm);
        }
      });
      continue;
    }

    match = token.match(new RegExp(`^(${acronymPattern})\\s*[- ]*0*([\\w]+)$`, 'i'));
    if (match) {
      const sourceId = sourceByAcronym[match[1].toUpperCase()];
      if (sourceId) {
        const norm = normalizeIdForSource(match[2], sources[sourceId]);
        const present = normalizedIdsBySource.get(sourceId) || new Set();
        if (present.has(norm)) addRef(sourceId, norm);
        continue;
      }
    }

    match = token.match(new RegExp(`^(${acronymPattern})$`, 'i'));
    if (match) {
      const sourceId = sourceByAcronym[match[1].toUpperCase()];
      if (sourceId) {
        const present = normalizedIdsBySource.get(sourceId) || new Set();
        present.forEach((norm) => addRef(sourceId, norm));
        continue;
      }
    }

    match = token.match(/^0*([\w]+)$/);
    if (match) {
      const candidate = match[1];
      presentSources.forEach((sourceId) => {
        const norm = normalizeIdForSource(candidate, sources[sourceId]);
        const present = normalizedIdsBySource.get(sourceId) || new Set();
        if (present.has(norm)) addRef(sourceId, norm);
      });
    }
  }

  const sortedRefs = refs.sort((a, b) => {
    const sa = String(a.source || '');
    const sb = String(b.source || '');
    if (sa !== sb) return sa.localeCompare(sb);
    return compareProposalIds(a.id, b.id);
  });

  return hasSourceAwareInputs ? sortedRefs : sortedRefs.map((ref) => ref.id);
}

export function buildProposalRefKeySet(refs) {
  return new Set((refs || []).map(refKey));
}

export function nodeRefKey(node, ecosystem = null) {
  const sourceId = node?.source || '';
  const source = ecosystem?.sources?.[sourceId];
  return refKey({ source: sourceId, id: normalizeIdForSource(node?.id, source) });
}
