import { useEffect, useMemo, useState } from 'react';
import { Dropdown } from 'primereact/dropdown';
import { InputSwitch } from 'primereact/inputswitch';
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
  const availableSnapshots = useMemo(() => getAvailableSnapshots(ecosystemId), [ecosystemId]);
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
    if (!ecosystem || ecosystem.status !== 'available' || !selectedSnapshot) {
      setSelectedDataset(emptyDataset);
      setDataLoading(false);
      return undefined;
    }
    if (!isDatasetCached(ecosystemId, selectedSnapshot)) {
      setDataReady(false);
      setSkeletonActive(true);
      setContentEntered(false);
    }
    let cancelled = false;
    setDataLoading(true);
    fetchDatasetForSelection(ecosystemId, selectedSnapshot)
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
  }, [ecosystemId, selectedSnapshot, ecosystem, emptyDataset]);
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
  } = useMemo(() => buildDashboardData(selectedDataset, ecosystem), [selectedDataset, ecosystem]);
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
  const availableProposalIds = useMemo(
    () => (selectedDataset?.nodes || [])
      .map((node) => normalizeProposalFilterValue(node?.id))
      .filter(Boolean)
      .sort((left, right) => Number(left) - Number(right)),
    [selectedDataset]
  );
  const selectedWordCloudProposalIds = useMemo(
    () => parseProposalFilterExpression(wordCloudFilterText, availableProposalIds),
    [availableProposalIds, wordCloudFilterText]
  );
  const selectedDependencyProposalIds = useMemo(
    () => parseProposalFilterExpression(dependencyFilterText, availableProposalIds),
    [availableProposalIds, dependencyFilterText]
  );
  const filteredWordCloudData = useMemo(
    () => buildWordCloudData(selectedDataset?.nodes || [], selectedWordCloudProposalIds),
    [selectedDataset, selectedWordCloudProposalIds]
  );
  const hasWordCloudFilter = wordCloudFilterText.trim().length > 0;
  const hasDependencyFilter = dependencyFilterText.trim().length > 0;

  useEffect(() => {
    setWordCloudFilterText((current) => {
      if (!current.trim()) {
        return current;
      }

      const normalized = parseProposalFilterExpression(current, availableProposalIds);
      return normalized.length ? current : '';
    });
  }, [availableProposalIds]);

  useEffect(() => {
    setDependencyFilterText((current) => {
      if (!current.trim()) {
        return current;
      }

      const normalized = parseProposalFilterExpression(current, availableProposalIds);
      return normalized.length ? current : '';
    });
  }, [availableProposalIds]);

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
  const dependencyProposalOptions = availableProposalIds;
  const snapshotOptions = availableSnapshots.map((snapshot) => ({
    label: snapshot === 'current' ? 'Current' : snapshot,
    value: snapshot,
  }));
  const sourceRepositories = ecosystem.sourceRepositories || [];

  return (
    <DashboardSnapshotProvider
      snapshot={selectedDataset?.snapshot || selectedSnapshot}
      linkMode={linkMode}
      ecosystem={ecosystem}
    >
      <section className="content">
      {dataLoading && <div className="dashboard-loading-bar" />}
      <div className="dashboard-toolbar">
        <div className="dashboard-toolbar__copy">
          <div className="dashboard-title-row">
            <img className="dashboard-title-logo" src={ecosystem.logo} alt={`${ecosystem.name} logo`} />
            <h1>{ecosystem.proposalPlural}</h1>
          </div>
          {ecosystem.dashboardDescription && (
            <p>{ecosystem.dashboardDescription}</p>
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
              ecosystem={ecosystem}
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
              ecosystem={ecosystem}
              classificationCategoryDomains={classificationCategoryDomains}
              classificationDistributions={classificationDistributions}
              classificationTimeline={classificationTimeline}
              classificationChordData={classificationChordData}
              classificationRelationRows={classificationRelationRows}
            />
            <EvolutionSection
              ecosystem={ecosystem}
              evolutionPayload={evolutionPayload}
            />
            <DependenciesSection
              ecosystem={ecosystem}
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
              ecosystem={ecosystem}
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
