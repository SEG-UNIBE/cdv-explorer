import { useCallback, useEffect, useMemo, useState } from 'react';
import { SECTION_PAYLOAD_FILES, applySectionData, fetchSectionDataForSelection } from '../data';

const SECTION_FIELDS = Object.keys(SECTION_PAYLOAD_FILES);

// Loads the deferred per-section payloads (dependency metrics, evolution,
// conformity) once their dashboard section has scrolled into view, and merges
// them into the core dataset. Results are keyed by the active selection so a
// snapshot/source switch discards payloads from the previous selection.
export function useSectionDataLoader({
  ecosystemId,
  selectedSnapshot,
  orderedSelectedSourceIds,
  canLoad,
}) {
  const [activatedSections, setActivatedSections] = useState({});
  const [sectionState, setSectionState] = useState({ key: null, byField: {} });
  const selectionKey = `${ecosystemId}/${orderedSelectedSourceIds.join('|')}/${selectedSnapshot}`;

  const activateSection = useCallback((field) => {
    setActivatedSections((current) => (
      current[field] ? current : { ...current, [field]: true }
    ));
  }, []);

  useEffect(() => {
    if (!canLoad) {
      return undefined;
    }
    let cancelled = false;
    SECTION_FIELDS.filter((field) => activatedSections[field]).forEach((field) => {
      const store = (data) => {
        if (cancelled) return;
        setSectionState((current) => ({
          key: selectionKey,
          byField: {
            ...(current.key === selectionKey ? current.byField : {}),
            [field]: data,
          },
        }));
      };
      fetchSectionDataForSelection(ecosystemId, selectedSnapshot, orderedSelectedSourceIds, field)
        .then(store)
        .catch((error) => {
          console.error(`Failed to load ${field} payload for ${selectionKey}`, error);
          // Mark the section ready anyway so it renders its empty state
          // instead of a permanent loading placeholder.
          store(null);
        });
    });
    return () => { cancelled = true; };
    // orderedSelectedSourceIds is covered by selectionKey.
  }, [canLoad, ecosystemId, selectedSnapshot, selectionKey, activatedSections]);

  const byField = sectionState.key === selectionKey ? sectionState.byField : {};

  const sectionReady = useMemo(() => Object.fromEntries(
    SECTION_FIELDS.map((field) => [
      field,
      !canLoad || !activatedSections[field] || byField[field] !== undefined,
    ]),
  ), [canLoad, activatedSections, byField]);

  const applyTo = useCallback((dataset) => SECTION_FIELDS.reduce(
    (augmented, field) => applySectionData(augmented, field, byField[field]),
    dataset,
  ), [byField]);

  return { activateSection, sectionReady, applySectionDataTo: applyTo };
}
