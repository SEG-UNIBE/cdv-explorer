import { SECTION_VIEW_MERGED } from './sections/SectionSourceToggle';

export function normalizeSectionSourceView(view, selectedSourceIds, supportsMerged) {
  if (selectedSourceIds.length <= 1) {
    return SECTION_VIEW_MERGED;
  }
  if (supportsMerged && view === SECTION_VIEW_MERGED) {
    return SECTION_VIEW_MERGED;
  }
  if (selectedSourceIds.includes(view)) {
    return view;
  }
  return supportsMerged ? SECTION_VIEW_MERGED : selectedSourceIds[0];
}

export function getSectionDataset(selectedDataset, sectionSourceView) {
  if (sectionSourceView === SECTION_VIEW_MERGED) {
    return selectedDataset;
  }
  return selectedDataset?.bySource?.[sectionSourceView] || selectedDataset;
}

export function getSectionEcosystem(ecosystem, activeEcosystem, sectionSourceView) {
  if (sectionSourceView === SECTION_VIEW_MERGED) {
    return activeEcosystem;
  }
  const source = ecosystem?.sources?.[sectionSourceView];
  return source ? { ...ecosystem, ...source } : activeEcosystem;
}
