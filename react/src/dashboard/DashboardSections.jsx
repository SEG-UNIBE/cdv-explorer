import { Suspense, lazy, useEffect, useRef, useState } from 'react';

const AuthorshipSection = lazy(() => import('./sections/AuthorshipSection').then((module) => ({
  default: module.AuthorshipSection,
})));
const ClassificationSection = lazy(() => import('./sections/ClassificationSection').then((module) => ({
  default: module.ClassificationSection,
})));
const DependenciesSection = lazy(() => import('./sections/DependenciesSection').then((module) => ({
  default: module.DependenciesSection,
})));
const ConformitySection = lazy(() => import('./sections/ConformitySection').then((module) => ({
  default: module.ConformitySection,
})));
const EvolutionSection = lazy(() => import('./sections/EvolutionSection').then((module) => ({
  default: module.EvolutionSection,
})));

function DashboardSectionFallback({ label }) {
  return (
    <div className="dashboard-section" aria-busy="true">
      <p>Loading {label}...</p>
    </div>
  );
}

function LazyDashboardSection({
  id,
  label,
  Component,
  componentProps,
  eager = false,
  minHeight = 220,
}) {
  const containerRef = useRef(null);
  const [isActive, setIsActive] = useState(eager);

  useEffect(() => {
    if (isActive || eager || typeof IntersectionObserver === 'undefined') {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setIsActive(true);
          observer.disconnect();
        }
      },
      { rootMargin: '600px 0px' },
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, [eager, isActive]);

  return (
    <div id={id} className="dashboard-anchor" ref={containerRef}>
      {isActive ? (
        <Suspense fallback={<DashboardSectionFallback label={label} />}>
          <Component {...componentProps} />
        </Suspense>
      ) : (
        <div className="dashboard-section" aria-busy="true" style={{ minHeight }}>
          <p>Loading {label}...</p>
        </div>
      )}
    </div>
  );
}

export function DashboardSections({
  ecosystem,
  activeEcosystem,
  selectedSourceIds,
  showExperimentalFeatures,
  showConformitySection,
  sectionViews,
  sectionViewState,
  datasets,
  dashboardData,
  perSourceDashboardData,
  authorshipControls,
  dependencyControls,
  conformityControls,
  dependencyMetrics,
  filteredWordCloudData,
  hasWordCloudFilter,
  hasDependencyFilter,
  selectedDependencyProposalIds,
}) {
  const collaborationAuthorOptions = (dashboardData.authorship.collaborationNetwork?.nodes || [])
    .map((node) => String(node.id || ''))
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right));

  return (
    <>
      <LazyDashboardSection
        id="dashboard-authorship"
        label="authorship"
        Component={AuthorshipSection}
        eager
        minHeight={320}
        componentProps={{
          ecosystem: datasets.authorshipViewEcosystem,
          ecosystemBase: ecosystem,
          selectedSourceIds,
          sectionSourceView: sectionViews.activeAuthorshipSourceView,
          setSectionSourceView: sectionViewState.setAuthorshipSourceView,
          showExperimentalFeatures,
          yearData: dashboardData.authorship.yearData,
          topAuthors: dashboardData.authorship.topAuthors,
          authorContributionHistogram: dashboardData.authorship.authorContributionHistogram,
          bipAuthorCountHistogram: dashboardData.authorship.bipAuthorCountHistogram,
          collaborationNetwork: dashboardData.authorship.collaborationNetwork,
          collaborationMetricsSummary: dashboardData.authorship.collaborationMetricsSummary,
          collaborationMetricsRows: dashboardData.authorship.collaborationMetricsRows,
          collaborationClusterSizeDistribution: dashboardData.authorship.collaborationClusterSizeDistribution,
          collaborationDegreeDistribution: dashboardData.authorship.collaborationDegreeDistribution,
          highlightedAuthor: authorshipControls.highlightedAuthor,
          setHighlightedAuthor: authorshipControls.setHighlightedAuthor,
          collaborationLayoutMode: authorshipControls.collaborationLayoutMode,
          setCollaborationLayoutMode: authorshipControls.setCollaborationLayoutMode,
          collaborationMinClusterCollaborations: authorshipControls.collaborationMinClusterCollaborations,
          setCollaborationMinClusterCollaborations: authorshipControls.setCollaborationMinClusterCollaborations,
          collaborationAuthorOptions,
          wordCloudFilterText: authorshipControls.wordCloudFilterText,
          setWordCloudFilterText: authorshipControls.setWordCloudFilterText,
          hasWordCloudFilter,
          filteredWordCloudData,
          wordCloudData: dashboardData.authorship.wordCloudData,
        }}
      />
      <LazyDashboardSection
        id="dashboard-classification"
        label="classification"
        Component={ClassificationSection}
        minHeight={260}
        componentProps={{
          ecosystem: activeEcosystem,
          ecosystemBase: ecosystem,
          selectedSourceIds,
          perSourceDashboardData,
          sectionSourceView: sectionViews.activeClassificationSourceView,
          setSectionSourceView: sectionViewState.setClassificationSourceView,
          classificationCategoryDomains: dashboardData.classificationCategoryDomains,
          classificationDistributions: dashboardData.classificationDistributions,
          classificationTimeline: dashboardData.classificationTimeline,
          classificationChordData: dashboardData.classificationChordData,
          classificationRelationRows: dashboardData.classificationRelationRows,
        }}
      />
      <LazyDashboardSection
        id="dashboard-evolution"
        label="evolution"
        Component={EvolutionSection}
        minHeight={240}
        componentProps={{
          ecosystem: activeEcosystem,
          ecosystemBase: ecosystem,
          selectedSourceIds,
          perSourceDashboardData,
          sectionSourceView: sectionViews.activeEvolutionSourceView,
          setSectionSourceView: sectionViewState.setEvolutionSourceView,
          evolutionPayload: dashboardData.evolutionPayload,
        }}
      />
      <LazyDashboardSection
        id="dashboard-dependencies"
        label="dependencies"
        Component={DependenciesSection}
        minHeight={320}
        componentProps={{
          ecosystem: datasets.dependencyViewEcosystem,
          ecosystemBase: ecosystem,
          selectedSourceIds,
          sectionSourceView: sectionViews.activeDependenciesSourceView,
          setSectionSourceView: sectionViewState.setDependenciesSourceView,
          selectedDataset: datasets.dependencyViewDataset,
          highlightedDependencyProposal: dependencyControls.highlightedDependencyProposal,
          setHighlightedDependencyProposal: dependencyControls.setHighlightedDependencyProposal,
          dependencyMinRelations: dependencyControls.dependencyMinRelations,
          setDependencyMinRelations: dependencyControls.setDependencyMinRelations,
          dependencyMinRelationsIncludeConnections: dependencyControls.dependencyMinRelationsIncludeConnections,
          setDependencyMinRelationsIncludeConnections: dependencyControls.setDependencyMinRelationsIncludeConnections,
          dependencyFilterText: dependencyControls.dependencyFilterText,
          setDependencyFilterText: dependencyControls.setDependencyFilterText,
          dependencyIncludeConnections: dependencyControls.dependencyIncludeConnections,
          setDependencyIncludeConnections: dependencyControls.setDependencyIncludeConnections,
          hasDependencyFilter,
          selectedDependencyProposalIds,
          activeDependencyLlmModel: dependencyMetrics.activeDependencyLlmModel,
          dependencyMetricsApproachOptions: dependencyMetrics.dependencyMetricsApproachOptions,
          activeDependencyMetricsApproach: dependencyMetrics.activeDependencyMetricsApproach,
          setSelectedDependencyMetricsApproach: dependencyMetrics.setSelectedDependencyMetricsApproach,
          activeDependencyMetrics: dependencyMetrics.activeDependencyMetrics,
          dependencyMetrics: dependencyMetrics.dependencyViewMetrics,
          showExperimentalFeatures,
        }}
      />
      {showConformitySection && (
        <LazyDashboardSection
          id="dashboard-conformity"
          label="conformity"
          Component={ConformitySection}
          minHeight={240}
          componentProps={{
            ecosystem: activeEcosystem,
            ecosystemBase: ecosystem,
            selectedSourceIds,
            perSourceDashboardData,
            sectionSourceView: sectionViews.activeConformitySourceView,
            setSectionSourceView: sectionViewState.setConformitySourceView,
            showExperimentalFeatures,
            highlightedConformityProposal: conformityControls.highlightedConformityProposal,
            setHighlightedConformityProposal: conformityControls.setHighlightedConformityProposal,
            conformityRows: dashboardData.conformity.conformityRows,
            conformityFailedChecks: dashboardData.conformity.conformityFailedChecks,
          }}
        />
      )}
    </>
  );
}
