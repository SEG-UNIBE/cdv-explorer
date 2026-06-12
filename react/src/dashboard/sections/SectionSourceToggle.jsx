export const SECTION_VIEW_MERGED = '__merged__';

function getSourceLabel(source, fallback) {
  return source?.shortLabel || source?.acronym || source?.label || fallback;
}

export function SectionSourceToggle({
  ecosystemBase,
  selectedSourceIds = [],
  value,
  onChange,
  supportsMerged = false,
}) {
  if (selectedSourceIds.length <= 1) {
    return null;
  }

  const buttons = [
    {
      value: SECTION_VIEW_MERGED,
      label: 'Merged',
      disabled: !supportsMerged,
    },
    ...selectedSourceIds.map((sourceId) => ({
      value: sourceId,
      label: getSourceLabel(ecosystemBase?.sources?.[sourceId], sourceId),
      disabled: false,
    })),
  ];

  return (
    <div className="section-source-toggle" aria-label="Section source view">
      {buttons.map((button) => (
        <button
          key={button.value}
          type="button"
          className={`section-source-toggle__button${value === button.value ? ' is-active' : ''}`}
          onClick={() => onChange?.(button.value)}
          disabled={button.disabled}
          aria-pressed={value === button.value && !button.disabled}
        >
          {button.label}
        </button>
      ))}
    </div>
  );
}
