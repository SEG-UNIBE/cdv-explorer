import { useEffect, useMemo, useState } from 'react';
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
  const [selectedSourceIds, setSelectedSourceIds] = useState(defaultSelectedSourceIds);
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
  const [selectedSnapshot, setSelectedSnapshot] = useState(availableSnapshots[0] ?? null);
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
  const [linkMode, setLinkMode] = useState('history');

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

  useEffect(() => {
    if (!ecosystem || ecosystem.status !== 'available' || !selectedSnapshot || orderedSelectedSourceIds.length === 0) {
      setSelectedDataset(emptyDataset);
      setDataLoading(false);
      return undefined;
    }
    if (!isDatasetCached(ecosystemId, selectedSnapshot, orderedSelectedSourceIds)) {
      setDataReady(false);
      setSkeletonActive(true);
      setContentEntered(false);
    }
    let cancelled = false;
    setDataLoading(true);
    fetchDatasetForSelection(ecosystemId, selectedSnapshot, orderedSelectedSourceIds)
      .then((dataset) => {
        if (!cancelled) {
          setSelectedDataset(dataset);
          setDataLoading(false);
          setDataReady(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSelectedDataset(emptyDataset);
          setDataLoading(false);
          setDataReady(true);
        }
      });
    return () => { cancelled = true; };
  }, [ecosystemId, orderedSelectedSourceIds, selectedSnapshot, ecosystem, emptyDataset]);
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

  return (
    <DashboardSnapshotProvider
      snapshot={selectedDataset?.snapshot || selectedSnapshot}
      linkMode={linkMode}
      ecosystem={activeEcosystem}
    >
      <section className="content">
      {dataLoading && <div className="dashboard-loading-bar" />}
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
      <div className="dashboard-sticky-controls">
        <span className="dashboard-sticky-controls__indicator" aria-hidden="true">
          <i className="pi pi-sliders-h" />
        </span>
        <div className="dashboard-sticky-controls__panel">
          {showSourcePicker && (
            <div className="dashboard-sticky-controls__source-row">
              <label htmlFor="source-select" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>
                SOURCES
              </label>
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
          <label htmlFor="snapshot-select" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>
            SNAPSHOT
          </label>
          <Dropdown
            inputId="snapshot-select"
            value={selectedSnapshot}
            options={snapshotOptions}
            onChange={(event) => setSelectedSnapshot(event.value)}
            placeholder="Select snapshot date"
            className="w-full"
          />
          {showMultiSourceSnapshotHelp && (
            <p className="dashboard-sticky-controls__help">
              Snapshot choices are limited to dates available for all selected sources.
            </p>
          )}
          <div className="dashboard-sticky-controls__link-row">
            <span className="dashboard-sticky-controls__label-inline">IP Links:</span>
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
      </div>

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
            <EvolutionSection
              ecosystem={activeEcosystem}
              ecosystemBase={ecosystem}
              selectedSourceIds={orderedSelectedSourceIds}
              perSourceDashboardData={perSourceDashboardData}
              evolutionPayload={evolutionPayload}
            />
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
      </section>
    </DashboardSnapshotProvider>
  );
}
