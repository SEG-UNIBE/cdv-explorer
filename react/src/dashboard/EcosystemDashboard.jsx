import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocalStorageState } from '../useLocalStorageState';
import { Dropdown } from 'primereact/dropdown';
import { InputSwitch } from 'primereact/inputswitch';
import { MultiSelect } from 'primereact/multiselect';
import { Link, useParams } from 'react-router-dom';
import { DEFAULT_DEPENDENCY_APPROACH } from '../dependencyApproaches';
import { LINK_TYPE_OPTIONS } from '../NetworkDiagram';
import { ecosystemsById } from '../ecosystems';
import { getAvailableSnapshots, fetchDatasetForSelection, isDatasetCached } from '../data';
import {
  buildDashboardData,
  buildWordCloudData,
  normalizeProposalFilterValue,
  parseProposalFilterExpression,
} from './dashboardData';
import { AuthorshipSection } from './sections/AuthorshipSection';
import { ClassificationSection } from './sections/ClassificationSection';
import { DependenciesSection } from './sections/DependenciesSection';
import { ConformitySection } from './sections/ConformitySection';
import { EvolutionSection } from './sections/EvolutionSection';
import { DashboardSnapshotProvider } from './DashboardSnapshotContext';
import { DashboardSkeleton } from './DashboardSkeleton';

function getSourceRepositoryHref(repository) {
  const text = String(repository || '').trim();
  const githubMatch = text.match(/^github\/([^/]+)\/([^/]+)$/i);

  if (githubMatch) {
    return `https://github.com/${githubMatch[1]}/${githubMatch[2]}`;
  }

  return null;
}

function formatProposalOption(node, ecosystem) {
  const source = ecosystem?.sources?.[node?.source] || ecosystem;
  if (typeof source?.formatProposalReference === 'function') {
    return source.formatProposalReference(node?.id);
  }
  return normalizeProposalFilterValue(node?.id);
}

export function EcosystemDashboard() {
  const { ecosystemId } = useParams();
  const ecosystem = ecosystemsById[ecosystemId];
  const emptyDataset = useMemo(() => ({
    nodes: [],
    links: {},
    authorship: {},
    classification: {},
    conformity: {},
    meta: {},
  }), []);
  const sourceOptions = useMemo(
    () => (ecosystem?.sourceOrder || [])
      .map((sourceId) => ecosystem?.sources?.[sourceId])
      .filter(Boolean),
    [ecosystem],
  );
  const defaultSelectedSourceIds = useMemo(
    () => (ecosystem?.defaultSourceId ? [ecosystem.defaultSourceId] : []),
    [ecosystem],
  );
  const [selectedSourceIds, setSelectedSourceIds] = useLocalStorageState(
    `cdv-explorer-${ecosystemId}-sources`,
    defaultSelectedSourceIds,
  );
  const orderedSelectedSourceIds = useMemo(
    () => (ecosystem?.sourceOrder || []).filter((id) => selectedSourceIds.includes(id)),
    [ecosystem, selectedSourceIds],
  );
  const primarySourceId = orderedSelectedSourceIds[0] || null;
  const activeSource = useMemo(
    () => (primarySourceId ? ecosystem?.sources?.[primarySourceId] || null : null),
    [ecosystem, primarySourceId],
  );
  const activeEcosystem = useMemo(
    () => (activeSource ? { ...ecosystem, ...activeSource } : ecosystem),
    [ecosystem, activeSource],
  );
  const availableSnapshots = useMemo(
    () => getAvailableSnapshots(ecosystemId, orderedSelectedSourceIds),
    [ecosystemId, orderedSelectedSourceIds],
  );
  const [selectedSnapshot, setSelectedSnapshot] = useLocalStorageState(
    `cdv-explorer-${ecosystemId}-snapshot`,
    availableSnapshots[0] ?? null,
  );
  const [highlightedAuthor, setHighlightedAuthor] = useState('');
  const [collaborationLayoutMode, setCollaborationLayoutMode] = useState('balanced');
  const [collaborationMinClusterCollaborations, setCollaborationMinClusterCollaborations] = useState('0');
  const [highlightedDependencyProposal, setHighlightedDependencyProposal] = useState('');
  const [dependencyMinRelations, setDependencyMinRelations] = useState('0');
  const [dependencyMinRelationsIncludeConnections, setDependencyMinRelationsIncludeConnections] = useState(false);
  const [dependencyFilterText, setDependencyFilterText] = useState('');
  const [dependencyIncludeConnections, setDependencyIncludeConnections] = useState(true);
  const [selectedDependencyMetricsApproach, setSelectedDependencyMetricsApproach] = useState(DEFAULT_DEPENDENCY_APPROACH);
  const [wordCloudFilterText, setWordCloudFilterText] = useState('');
  const [highlightedConformityProposal, setHighlightedConformityProposal] = useState('');
  const [linkMode, setLinkMode] = useLocalStorageState('cdv-explorer-linkmode', 'history');
  const [activeTocSection, setActiveTocSection] = useState('dashboard-authorship');
  const dashboardScrollRef = useRef(null);

  useEffect(() => {
    setSelectedSourceIds((current) => {
      const valid = current.filter((id) => ecosystem?.sources?.[id]);
      if (valid.length > 0) return valid;
      return defaultSelectedSourceIds;
    });
  }, [ecosystem, defaultSelectedSourceIds]);

  useEffect(() => {
    setSelectedSnapshot((current) => {
      if (current && availableSnapshots.includes(current)) {
        return current;
      }
      return availableSnapshots[0] ?? null;
    });
  }, [ecosystemId, availableSnapshots]);

  const [selectedDataset, setSelectedDataset] = useState(emptyDataset);
  const [dataLoading, setDataLoading] = useState(true);
  const [dataReady, setDataReady] = useState(false);
  const [skeletonActive, setSkeletonActive] = useState(true);
  const [contentEntered, setContentEntered] = useState(false);
  const [fetchError, setFetchError] = useState(null);
  const [retryCounter, setRetryCounter] = useState(0);

  useEffect(() => {
    if (!ecosystem || ecosystem.status !== 'available' || !selectedSnapshot || orderedSelectedSourceIds.length === 0) {
      setSelectedDataset(emptyDataset);
      setDataLoading(false);
      setFetchError(null);
      return undefined;
    }
    if (!isDatasetCached(ecosystemId, selectedSnapshot, orderedSelectedSourceIds)) {
      setDataReady(false);
      setSkeletonActive(true);
      setContentEntered(false);
    }
    let cancelled = false;
    setDataLoading(true);
    setFetchError(null);
    fetchDatasetForSelection(ecosystemId, selectedSnapshot, orderedSelectedSourceIds)
      .then((dataset) => {
        if (!cancelled) {
          setSelectedDataset(dataset);
          setDataLoading(false);
          setDataReady(true);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setDataLoading(false);
          setSkeletonActive(false);
          setFetchError({
            snapshot: selectedSnapshot,
            sourceIds: orderedSelectedSourceIds,
            message: error instanceof Error ? error.message : String(error),
          });
        }
      });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecosystemId, orderedSelectedSourceIds, selectedSnapshot, ecosystem, emptyDataset, retryCounter]);
  const {
    yearData,
    wordCloudData,
    conformityRows,
    conformityFailedChecks,
    classificationDistributions,
    classificationTimeline,
    classificationCategoryDomains,
    classificationChordData,
    classificationRelationRows,
    evolutionPayload,
    topAuthors,
    authorContributionHistogram,
    bipAuthorCountHistogram,
    collaborationNetwork,
    collaborationMetricsSummary,
    collaborationMetricsRows,
    collaborationClusterSizeDistribution,
    collaborationDegreeDistribution,
    dependencyMetrics,
  } = useMemo(() => buildDashboardData(selectedDataset, activeEcosystem), [selectedDataset, activeEcosystem]);
  const perSourceDashboardData = useMemo(() => {
    const bySource = selectedDataset?.bySource || {};
    return orderedSelectedSourceIds.reduce((acc, sourceId) => {
      const sourceDataset = bySource[sourceId];
      const source = ecosystem?.sources?.[sourceId];
      if (sourceDataset && source) {
        acc[sourceId] = buildDashboardData(sourceDataset, { ...ecosystem, ...source });
      }
      return acc;
    }, {});
  }, [selectedDataset, ecosystem, orderedSelectedSourceIds]);
  const dependencyMetricsApproachOptions = useMemo(
    () => LINK_TYPE_OPTIONS.filter(
      (option) => dependencyMetrics?.by_approach?.[option.value]
    ),
    [dependencyMetrics]
  );
  const activeDependencyMetricsApproach = dependencyMetricsApproachOptions.some(
    (option) => option.value === selectedDependencyMetricsApproach
  )
    ? selectedDependencyMetricsApproach
    : (dependencyMetricsApproachOptions[0]?.value || DEFAULT_DEPENDENCY_APPROACH);
  const activeDependencyMetrics = dependencyMetrics?.by_approach?.[activeDependencyMetricsApproach] || {
    summary: {},
    per_bip: [],
  };
  const availableProposalNodes = useMemo(
    () => (selectedDataset?.nodes || [])
      .filter((node) => node?.id != null),
    [selectedDataset]
  );
  const availableProposalIds = useMemo(
    () => (selectedDataset?.nodes || [])
      .map((node) => normalizeProposalFilterValue(node?.id))
      .filter(Boolean)
      .sort((left, right) => Number(left) - Number(right)),
    [selectedDataset]
  );
  const selectedWordCloudProposalIds = useMemo(
    () => parseProposalFilterExpression(wordCloudFilterText, availableProposalNodes, ecosystem),
    [availableProposalNodes, ecosystem, wordCloudFilterText]
  );
  const selectedDependencyProposalIds = useMemo(
    () => parseProposalFilterExpression(dependencyFilterText, availableProposalNodes, ecosystem),
    [availableProposalNodes, dependencyFilterText, ecosystem]
  );
  const filteredWordCloudData = useMemo(
    () => buildWordCloudData(selectedDataset?.nodes || [], selectedWordCloudProposalIds, ecosystem),
    [ecosystem, selectedDataset, selectedWordCloudProposalIds]
  );
  const hasWordCloudFilter = wordCloudFilterText.trim().length > 0;
  const hasDependencyFilter = dependencyFilterText.trim().length > 0;

  useEffect(() => {
    setWordCloudFilterText((current) => {
      if (!current.trim()) {
        return current;
      }

      const normalized = parseProposalFilterExpression(current, availableProposalNodes, ecosystem);
      return normalized.length ? current : '';
    });
  }, [availableProposalNodes, ecosystem]);

  useEffect(() => {
    setDependencyFilterText((current) => {
      if (!current.trim()) {
        return current;
      }

      const normalized = parseProposalFilterExpression(current, availableProposalNodes, ecosystem);
      return normalized.length ? current : '';
    });
  }, [availableProposalNodes, ecosystem]);

  useEffect(() => {
    setHighlightedConformityProposal((current) => {
      if (!current.trim()) {
        return current;
      }

      const normalized = normalizeProposalFilterValue(current);
      return availableProposalIds.includes(normalized) ? current : '';
    });
  }, [availableProposalIds]);

  useEffect(() => {
    if (!dependencyMetricsApproachOptions.some((option) => option.value === selectedDependencyMetricsApproach)) {
      setSelectedDependencyMetricsApproach(dependencyMetricsApproachOptions[0]?.value || DEFAULT_DEPENDENCY_APPROACH);
    }
  }, [dependencyMetricsApproachOptions, selectedDependencyMetricsApproach]);

  useEffect(() => {
    document.documentElement.classList.add('dashboard-route-active');
    document.body.classList.add('dashboard-route-active');
    return () => {
      document.documentElement.classList.remove('dashboard-route-active');
      document.body.classList.remove('dashboard-route-active');
    };
  }, []);

  const showConformitySection = useMemo(() => {
    if (!ecosystem) return false;
    if (orderedSelectedSourceIds.length > 1) {
      return orderedSelectedSourceIds.some((sourceId) => (
        (ecosystem.sources?.[sourceId]?.complianceStandards || []).length > 0
      ));
    }
    return (activeEcosystem?.complianceStandards || []).length > 0;
  }, [activeEcosystem, ecosystem, orderedSelectedSourceIds]);
  const dashboardTocItems = useMemo(() => [
    { id: 'dashboard-authorship', label: 'Authorship' },
    { id: 'dashboard-classification', label: 'Classification' },
    { id: 'dashboard-evolution', label: 'Evolution' },
    { id: 'dashboard-dependencies', label: 'Dependencies' },
    ...(showConformitySection ? [{ id: 'dashboard-conformity', label: 'Conformity' }] : []),
  ], [showConformitySection]);

  useEffect(() => {
    const scrollPane = dashboardScrollRef.current;
    if (!scrollPane || dashboardTocItems.length === 0) return undefined;

    const updateActiveSection = () => {
      const paneTop = scrollPane.getBoundingClientRect().top;
      const current = dashboardTocItems.reduce((active, item) => {
        const section = document.getElementById(item.id);
        if (!section) return active;
        const offset = section.getBoundingClientRect().top - paneTop;
        return offset <= 120 ? item.id : active;
      }, dashboardTocItems[0].id);
      setActiveTocSection(current);
    };

    updateActiveSection();
    scrollPane.addEventListener('scroll', updateActiveSection, { passive: true });
    return () => scrollPane.removeEventListener('scroll', updateActiveSection);
  }, [dashboardTocItems]);

  if (!ecosystem) {
    return (
      <section className="content">
        <h1>Unknown Ecosystem</h1>
        <p>The selected ecosystem does not exist in this frontend configuration.</p>
        <p><Link to="/">Back to ecosystem selection</Link></p>
      </section>
    );
  }

  if (ecosystem.status !== 'available') {
    return (
      <section className="content">
        <h1>{ecosystem.name}</h1>
        <p>This ecosystem is listed intentionally, but its adapter has not been implemented yet.</p>
        <p><Link to="/">Back to ecosystem selection</Link></p>
      </section>
    );
  }

  const collaborationAuthorOptions = collaborationNetwork.nodes
    .map((node) => String(node.id || ''))
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right));
  const dependencyProposalOptions = availableProposalNodes
    .map((node) => formatProposalOption(node, ecosystem))
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right, undefined, { numeric: true }));
  const snapshotOptions = availableSnapshots.map((snapshot) => ({
    label: snapshot === 'current' ? 'Current' : snapshot,
    value: snapshot,
  }));
  const selectedSources = orderedSelectedSourceIds
    .map((id) => ecosystem.sources?.[id])
    .filter(Boolean);
  const sourceRepositories = Array.from(
    new Set(selectedSources.flatMap((s) => s.sourceRepositories || [])),
  );
  const sourcePickerOptions = sourceOptions.map((source) => ({
    label: source.shortLabel || source.acronym,
    value: source.sourceId,
  }));
  const showSourcePicker = sourcePickerOptions.length > 1;
  const showMultiSourceSnapshotHelp = orderedSelectedSourceIds.length > 1;
  const dashboardTitle = `${ecosystem.name} Ecosystem`;
  const dashboardDescription = ecosystem.ecosystemDescription;

  const scrollToDashboardSection = (sectionId) => {
    const target = document.getElementById(sectionId);
    if (!target) return;
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setActiveTocSection(sectionId);
  };

  return (
    <DashboardSnapshotProvider
      snapshot={selectedDataset?.snapshot || selectedSnapshot}
      linkMode={linkMode}
      ecosystem={activeEcosystem}
    >
      <section className="content content--dashboard">
      {dataLoading && <div className="dashboard-loading-bar" />}
      <div className="dashboard-shell">
        <aside className="dashboard-ribbon" aria-label="Dashboard controls">
          <div className="dashboard-ribbon__brand">
            <img className="dashboard-title-logo" src={ecosystem.logo} alt={`${ecosystem.name} logo`} />
            <div>
              <div className="dashboard-ribbon__title">{dashboardTitle}</div>
              <span>{selectedSnapshot === 'current' ? 'Current' : selectedSnapshot}</span>
            </div>
          </div>
          <nav className="dashboard-ribbon__toc" aria-label="Dashboard sections">
            <div className="dashboard-ribbon__label">Contents</div>
            {dashboardTocItems.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`dashboard-ribbon__toc-item${activeTocSection === item.id ? ' is-active' : ''}`}
                onClick={() => scrollToDashboardSection(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="dashboard-ribbon__controls">
            <div className="dashboard-ribbon__label">Controls</div>
            {showSourcePicker && (
              <div className="dashboard-ribbon__field">
                <label htmlFor="source-select">Sources</label>
                <MultiSelect
                  inputId="source-select"
                  value={selectedSourceIds}
                  options={sourcePickerOptions}
                  onChange={(event) => {
                    if (Array.isArray(event.value) && event.value.length > 0) {
                      setSelectedSourceIds(event.value);
                    }
                  }}
                  display="chip"
                  placeholder="Select sources"
                  className="dashboard-source-picker w-full"
                  maxSelectedLabels={sourcePickerOptions.length}
                />
              </div>
            )}
            <div className="dashboard-ribbon__field">
              <label htmlFor="snapshot-select">Snapshot</label>
              <Dropdown
                inputId="snapshot-select"
                value={selectedSnapshot}
                options={snapshotOptions}
                onChange={(event) => setSelectedSnapshot(event.value)}
                placeholder="Select snapshot date"
                className="w-full"
              />
              {showMultiSourceSnapshotHelp && (
                <p className="dashboard-ribbon__help">
                  Dates are limited to snapshots available for all selected sources.
                </p>
              )}
            </div>
            <div className="dashboard-ribbon__link-row">
              <span className="dashboard-ribbon__label-inline">IP Links</span>
              <span className={`dashboard-link-mode-text${linkMode === 'history' ? ' is-active' : ''}`}>
                Historic
              </span>
              <InputSwitch
                checked={linkMode === 'current'}
                onChange={(event) => setLinkMode(event.value ? 'current' : 'history')}
                inputId="link-mode-switch"
                aria-label="IP links mode"
                className="dashboard-link-mode-switch"
              />
              <span className={`dashboard-link-mode-text${linkMode === 'current' ? ' is-active' : ''}`}>
                Current
              </span>
            </div>
          </div>
        </aside>

        <main className="dashboard-main" ref={dashboardScrollRef}>
          <div className="dashboard-main__inner">
          <div className="dashboard-toolbar">
            <div className="dashboard-toolbar__copy">
              <div className="dashboard-title-row">
                <img className="dashboard-title-logo" src={ecosystem.logo} alt={`${ecosystem.name} logo`} />
                <h1>{dashboardTitle}</h1>
              </div>
              {dashboardDescription && (
                <p>{dashboardDescription}</p>
              )}
              <ul>
                {sourceRepositories.map((repository) => {
                  const href = getSourceRepositoryHref(repository);

                  return (
                    <li key={repository}>
                      {href ? (
                        <a href={href} target="_blank" rel="noreferrer">
                          {repository}
                        </a>
                      ) : repository}
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>

      {fetchError ? (
        <div className="dashboard-fetch-error">
          <div className="dashboard-fetch-error__icon" aria-hidden="true">⚠</div>
          <p className="dashboard-fetch-error__title">Failed to load dashboard data</p>
          <p className="dashboard-fetch-error__detail">
            Snapshot: <code>{fetchError.snapshot}</code>
            {fetchError.sourceIds.length > 0 && (
              <> · Sources: <code>{fetchError.sourceIds.join(', ')}</code></>
            )}
          </p>
          {fetchError.message && (
            <p className="dashboard-fetch-error__message">{fetchError.message}</p>
          )}
          <button
            type="button"
            className="dashboard-fetch-error__retry"
            onClick={() => {
              setSkeletonActive(true);
              setRetryCounter((c) => c + 1);
            }}
          >
            Try again
          </button>
        </div>
      ) : (
      <div className="sk-crossfade">
        {skeletonActive && (
          <div
            className={`sk-crossfade__layer${dataReady ? ' sk-exit' : ''}`}
            onAnimationEnd={(e) => e.animationName === 'sk-fade-out' && setSkeletonActive(false)}
          >
            <DashboardSkeleton />
          </div>
        )}
        {dataReady && (
          <div
            className={`sk-crossfade__layer${contentEntered ? '' : ' sk-enter'}`}
            onAnimationEnd={(e) => e.animationName === 'sk-fade-in' && setContentEntered(true)}
          >
            <div id="dashboard-authorship" className="dashboard-anchor">
              <AuthorshipSection
                ecosystem={activeEcosystem}
                yearData={yearData}
                topAuthors={topAuthors}
                authorContributionHistogram={authorContributionHistogram}
                bipAuthorCountHistogram={bipAuthorCountHistogram}
                collaborationNetwork={collaborationNetwork}
                collaborationMetricsSummary={collaborationMetricsSummary}
                collaborationMetricsRows={collaborationMetricsRows}
                collaborationClusterSizeDistribution={collaborationClusterSizeDistribution}
                collaborationDegreeDistribution={collaborationDegreeDistribution}
                highlightedAuthor={highlightedAuthor}
                setHighlightedAuthor={setHighlightedAuthor}
                collaborationLayoutMode={collaborationLayoutMode}
                setCollaborationLayoutMode={setCollaborationLayoutMode}
                collaborationMinClusterCollaborations={collaborationMinClusterCollaborations}
                setCollaborationMinClusterCollaborations={setCollaborationMinClusterCollaborations}
                collaborationAuthorOptions={collaborationAuthorOptions}
                wordCloudFilterText={wordCloudFilterText}
                setWordCloudFilterText={setWordCloudFilterText}
                hasWordCloudFilter={hasWordCloudFilter}
                filteredWordCloudData={filteredWordCloudData}
                wordCloudData={wordCloudData}
              />
            </div>
            <div id="dashboard-classification" className="dashboard-anchor">
              <ClassificationSection
                ecosystem={activeEcosystem}
                ecosystemBase={ecosystem}
                selectedSourceIds={orderedSelectedSourceIds}
                perSourceDashboardData={perSourceDashboardData}
                classificationCategoryDomains={classificationCategoryDomains}
                classificationDistributions={classificationDistributions}
                classificationTimeline={classificationTimeline}
                classificationChordData={classificationChordData}
                classificationRelationRows={classificationRelationRows}
              />
            </div>
            <div id="dashboard-evolution" className="dashboard-anchor">
              <EvolutionSection
                ecosystem={activeEcosystem}
                ecosystemBase={ecosystem}
                selectedSourceIds={orderedSelectedSourceIds}
                perSourceDashboardData={perSourceDashboardData}
                evolutionPayload={evolutionPayload}
              />
            </div>
            <div id="dashboard-dependencies" className="dashboard-anchor">
              <DependenciesSection
                ecosystem={activeEcosystem}
                selectedDataset={selectedDataset}
                highlightedDependencyProposal={highlightedDependencyProposal}
                setHighlightedDependencyProposal={setHighlightedDependencyProposal}
                dependencyProposalOptions={dependencyProposalOptions}
                dependencyMinRelations={dependencyMinRelations}
                setDependencyMinRelations={setDependencyMinRelations}
                dependencyMinRelationsIncludeConnections={dependencyMinRelationsIncludeConnections}
                setDependencyMinRelationsIncludeConnections={setDependencyMinRelationsIncludeConnections}
                dependencyFilterText={dependencyFilterText}
                setDependencyFilterText={setDependencyFilterText}
                dependencyIncludeConnections={dependencyIncludeConnections}
                setDependencyIncludeConnections={setDependencyIncludeConnections}
                hasDependencyFilter={hasDependencyFilter}
                selectedDependencyProposalIds={selectedDependencyProposalIds}
                dependencyMetricsApproachOptions={dependencyMetricsApproachOptions}
                activeDependencyMetricsApproach={activeDependencyMetricsApproach}
                setSelectedDependencyMetricsApproach={setSelectedDependencyMetricsApproach}
                activeDependencyMetrics={activeDependencyMetrics}
                dependencyMetrics={dependencyMetrics}
              />
            </div>
            {showConformitySection && (
              <div id="dashboard-conformity" className="dashboard-anchor">
                <ConformitySection
                  ecosystem={activeEcosystem}
                  ecosystemBase={ecosystem}
                  selectedSourceIds={orderedSelectedSourceIds}
                  perSourceDashboardData={perSourceDashboardData}
                  dependencyProposalOptions={dependencyProposalOptions}
                  highlightedConformityProposal={highlightedConformityProposal}
                  setHighlightedConformityProposal={setHighlightedConformityProposal}
                  conformityRows={conformityRows}
                  conformityFailedChecks={conformityFailedChecks}
                />
              </div>
            )}
          </div>
        )}
      </div>
      )}
          </div>
        </main>
      </div>
      </section>
    </DashboardSnapshotProvider>
  );
}
