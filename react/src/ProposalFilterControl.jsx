import { useMemo, useState } from 'react';

function getSources(ecosystem) {
  const sources = ecosystem?.sources || {};
  const order = ecosystem?.sourceOrder || Object.keys(sources);
  return order
    .map((sourceId) => sources[sourceId])
    .filter(Boolean);
}

function normalizePart(value) {
  return String(value || '').trim().replace(/^0+(\d)/, '$1');
}

function sourceForText(text, sources) {
  const normalized = String(text || '').trim().toLowerCase();
  if (!normalized) return null;
  return sources.find((source) => (
    String(source.acronym || '').toLowerCase() === normalized
    || String(source.shortLabel || '').toLowerCase() === normalized
    || String(source.sourceId || '').toLowerCase() === normalized
  )) || null;
}

function sourceForAcronym(acronym, sources) {
  return sources.find((source) => (
    String(source.acronym || '').toLowerCase() === String(acronym || '').toLowerCase()
  )) || null;
}

function buildSourceToken(source, part) {
  const acronym = source?.acronym || '';
  const text = String(part || '').trim();
  if (!acronym || !text) return text;
  if (/^[A-Za-z]+\s*[- ]*/.test(text)) return text;
  return `${acronym}${text}`;
}

function parseToken(token, sources) {
  let source = null;
  let display = token;
  let match = token.match(/^([A-Za-z]+)\s*[- ]*0*([\w]+)\s*-\s*(?:\1\s*[- ]*)?0*([\w]+)$/i);

  if (match) {
    source = sourceForAcronym(match[1], sources);
    display = `${normalizePart(match[2])}-${normalizePart(match[3])}`;
  } else {
    match = token.match(/^([A-Za-z]+)\s*[- ]*0*([\w]+)$/i);
    if (match) {
      source = sourceForAcronym(match[1], sources);
      display = normalizePart(match[2]);
    } else {
      source = sourceForText(token, sources);
      display = source ? 'all' : token;
    }
  }

  return { source, display };
}

function partToRange(part) {
  const match = String(part || '').trim().match(/^(\d+)(?:-(\d+))?$/);
  if (!match) return null;
  const start = Number(match[1]);
  const end = match[2] == null ? start : Number(match[2]);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  return {
    start: Math.min(start, end),
    end: Math.max(start, end),
  };
}

function compactParts(parts) {
  const numericRanges = [];
  const nonNumeric = [];

  (parts || []).forEach((part) => {
    const normalized = normalizePart(part);
    const range = partToRange(normalized);
    if (range) {
      numericRanges.push(range);
      return;
    }
    if (normalized) nonNumeric.push(normalized);
  });

  numericRanges.sort((left, right) => left.start - right.start || left.end - right.end);
  const merged = [];
  numericRanges.forEach((range) => {
    const previous = merged[merged.length - 1];
    if (previous && range.start <= previous.end + 1) {
      previous.end = Math.max(previous.end, range.end);
      return;
    }
    merged.push({ ...range });
  });

  return [
    ...merged.map((range) => (range.start === range.end ? String(range.start) : `${range.start}-${range.end}`)),
    ...Array.from(new Set(nonNumeric)),
  ];
}

function buildTokenFromGroupPart(group, part) {
  if (!group.source) return part;
  return buildSourceToken(group.source, part);
}

function normalizeFilterValue(value, sources) {
  const groups = parseGroups(value, sources);
  const tokens = [];

  groups.forEach((group) => {
    if (group.parts.includes('all')) {
      tokens.push(group.source?.acronym || group.source?.sourceId || group.parts[0]);
      return;
    }
    compactParts(group.parts).forEach((part) => {
      tokens.push(buildTokenFromGroupPart(group, part));
    });
  });

  return tokens.join(',');
}

function parseGroups(value, sources) {
  const groups = new Map();
  String(value || '')
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean)
    .forEach((token, index) => {
      const { source, display } = parseToken(token, sources);

      const key = source?.sourceId || '__bare__';
      if (!groups.has(key)) {
        groups.set(key, {
          key,
          source,
          label: source?.shortLabel || source?.acronym || 'IDs',
          parts: [],
          tokenIndices: [],
        });
      }
      groups.get(key).parts.push(display);
      groups.get(key).tokenIndices.push(index);
    });
  return Array.from(groups.values());
}

function removeGroupFromValue(value, group) {
  const remove = new Set(group.tokenIndices);
  return String(value || '')
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean)
    .filter((_, index) => !remove.has(index))
    .join(',');
}

function appendToValue(value, tokens) {
  const existing = String(value || '').split(',').map((token) => token.trim()).filter(Boolean);
  return [...existing, ...tokens].join(',');
}

function appendAndNormalize(value, tokens, sources) {
  return normalizeFilterValue(appendToValue(value, tokens), sources);
}

export function ProposalFilterControl({
  value,
  onChange,
  ecosystem,
  placeholder = 'Type BIP, then 2,3-5 and press Enter',
  ariaLabel = 'Filter proposals',
  singleSelect = false,
  layout = 'default',
  entryLabel = '',
  trailingControl = null,
  className = '',
}) {
  const [draft, setDraft] = useState('');
  const [activeSourceId, setActiveSourceId] = useState('');
  const sources = useMemo(() => getSources(ecosystem), [ecosystem]);
  const activeSource = sources.find((source) => source.sourceId === activeSourceId) || null;
  const groups = useMemo(() => parseGroups(value, sources), [sources, value]);

  const commit = (tokens) => {
    if (singleSelect) {
      const firstToken = tokens[0]?.split(',')[0]?.trim() || '';
      if (!firstToken) return;
      // Strip ranges: keep only the starting proposal (e.g. "BIP1-10" -> "BIP1")
      const collapsed = firstToken.replace(/^([A-Za-z]*\s*[- ]*0*\d+)\s*-\s*[A-Za-z]*\s*[- ]*0*\d+$/i, '$1');
      onChange(normalizeFilterValue(collapsed, sources));
      return;
    }
    onChange(appendAndNormalize(value, tokens, sources));
  };

  const commitDraft = () => {
    const text = draft.trim();
    if (!text) return;

    const directSource = sourceForText(text, sources);
    if (directSource) {
      setActiveSourceId(directSource.sourceId);
      setDraft('');
      return;
    }

    const sourceWithParts = text.match(/^([A-Za-z]+)\s+(.+)$/);
    if (sourceWithParts) {
      const source = sourceForText(sourceWithParts[1], sources);
      if (source) {
        const tokens = sourceWithParts[2]
          .split(',')
          .map((part) => buildSourceToken(source, part))
          .filter(Boolean);
        commit(tokens);
        setActiveSourceId(source.sourceId);
        setDraft('');
        return;
      }
    }

    const parts = text.split(',').map((part) => part.trim()).filter(Boolean);
    const tokens = activeSource
      ? parts.map((part) => buildSourceToken(activeSource, part))
      : parts;
    commit(tokens);
    setDraft('');
  };

  const chips = (
    <div className="proposal-filter-control__chips" aria-live="polite">
      {groups.map((group) => (
        <span key={group.key} className="proposal-filter-chip">
          <button
            type="button"
            className="proposal-filter-chip__label"
            onClick={() => group.source && setActiveSourceId(group.source.sourceId)}
            title={group.source ? `Use ${group.label} for the next entry` : undefined}
          >
            {group.label}: {group.parts.join(',')}
          </button>
          <button
            type="button"
            className="proposal-filter-chip__remove"
            aria-label={`Remove ${group.label} filter`}
            onClick={() => onChange(removeGroupFromValue(value, group))}
          >
            x
          </button>
        </span>
      ))}
    </div>
  );

  const input = (
    <input
      type="text"
      className="p-inputtext p-component"
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          commitDraft();
        }
      }}
      onBlur={commitDraft}
      placeholder={placeholder}
      aria-label={ariaLabel}
    />
  );

  if (layout === 'split') {
    return (
      <div className={`proposal-filter-control proposal-filter-control--split ${className}`.trim()}>
        <div className="proposal-filter-control__entry">
          {entryLabel ? <strong className="proposal-filter-control__entry-label">{entryLabel}</strong> : null}
          {input}
          {trailingControl}
        </div>
        {chips}
      </div>
    );
  }

  return (
    <div className={`proposal-filter-control ${className}`.trim()}>
      {chips}
      {input}
    </div>
  );
}
