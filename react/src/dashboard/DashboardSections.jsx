import { AuthorshipSection } from './sections/AuthorshipSection';
import { ClassificationSection } from './sections/ClassificationSection';
import { DependenciesSection } from './sections/DependenciesSection';
import { ConformitySection } from './sections/ConformitySection';
import { EvolutionSection } from './sections/EvolutionSection';

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
      <div id="dashboard-authorship" className="dashboard-anchor">
        <AuthorshipSection
          ecosystem={datasets.authorshipViewEcosystem}
          ecosystemBase={ecosystem}
          selectedSourceIds={selectedSourceIds}
          sectionSourceView={sectionViews.activeAuthorshipSourceView}
          setSectionSourceView={sectionViewState.setAuthorshipSourceView}
          showExperimentalFeatures={showExperimentalFeatures}
          yearData={dashboardData.authorship.yearData}
          topAuthors={dashboardData.authorship.topAuthors}
          authorContributionHistogram={dashboardData.authorship.authorContributionHistogram}
          bipAuthorCountHistogram={dashboardData.authorship.bipAuthorCountHistogram}
          collaborationNetwork={dashboardData.authorship.collaborationNetwork}
          collaborationMetricsSummary={dashboardData.authorship.collaborationMetricsSummary}
          collaborationMetricsRows={dashboardData.authorship.collaborationMetricsRows}
          collaborationClusterSizeDistribution={dashboardData.authorship.collaborationClusterSizeDistribution}
          collaborationDegreeDistribution={dashboardData.authorship.collaborationDegreeDistribution}
          highlightedAuthor={authorshipControls.highlightedAuthor}
          setHighlightedAuthor={authorshipControls.setHighlightedAuthor}
          collaborationLayoutMode={authorshipControls.collaborationLayoutMode}
          setCollaborationLayoutMode={authorshipControls.setCollaborationLayoutMode}
          collaborationMinClusterCollaborations={authorshipControls.collaborationMinClusterCollaborations}
          setCollaborationMinClusterCollaborations={authorshipControls.setCollaborationMinClusterCollaborations}
          collaborationAuthorOptions={collaborationAuthorOptions}
          wordCloudFilterText={authorshipControls.wordCloudFilterText}
          setWordCloudFilterText={authorshipControls.setWordCloudFilterText}
          hasWordCloudFilter={hasWordCloudFilter}
          filteredWordCloudData={filteredWordCloudData}
          wordCloudData={dashboardData.authorship.wordCloudData}
        />
      </div>
      <div id="dashboard-classification" className="dashboard-anchor">
        <ClassificationSection
          ecosystem={activeEcosystem}
          ecosystemBase={ecosystem}
          selectedSourceIds={selectedSourceIds}
          perSourceDashboardData={perSourceDashboardData}
          sectionSourceView={sectionViews.activeClassificationSourceView}
          setSectionSourceView={sectionViewState.setClassificationSourceView}
          classificationCategoryDomains={dashboardData.classificationCategoryDomains}
          classificationDistributions={dashboardData.classificationDistributions}
          classificationTimeline={dashboardData.classificationTimeline}
          classificationChordData={dashboardData.classificationChordData}
          classificationRelationRows={dashboardData.classificationRelationRows}
        />
      </div>
      <div id="dashboard-evolution" className="dashboard-anchor">
        <EvolutionSection
          ecosystem={activeEcosystem}
          ecosystemBase={ecosystem}
          selectedSourceIds={selectedSourceIds}
          perSourceDashboardData={perSourceDashboardData}
          sectionSourceView={sectionViews.activeEvolutionSourceView}
          setSectionSourceView={sectionViewState.setEvolutionSourceView}
          evolutionPayload={dashboardData.evolutionPayload}
        />
      </div>
      <div id="dashboard-dependencies" className="dashboard-anchor">
        <DependenciesSection
          ecosystem={datasets.dependencyViewEcosystem}
          ecosystemBase={ecosystem}
          selectedSourceIds={selectedSourceIds}
          sectionSourceView={sectionViews.activeDependenciesSourceView}
          setSectionSourceView={sectionViewState.setDependenciesSourceView}
          selectedDataset={datasets.dependencyViewDataset}
          highlightedDependencyProposal={dependencyControls.highlightedDependencyProposal}
          setHighlightedDependencyProposal={dependencyControls.setHighlightedDependencyProposal}
          dependencyMinRelations={dependencyControls.dependencyMinRelations}
          setDependencyMinRelations={dependencyControls.setDependencyMinRelations}
          dependencyMinRelationsIncludeConnections={dependencyControls.dependencyMinRelationsIncludeConnections}
          setDependencyMinRelationsIncludeConnections={dependencyControls.setDependencyMinRelationsIncludeConnections}
          dependencyFilterText={dependencyControls.dependencyFilterText}
          setDependencyFilterText={dependencyControls.setDependencyFilterText}
          dependencyIncludeConnections={dependencyControls.dependencyIncludeConnections}
          setDependencyIncludeConnections={dependencyControls.setDependencyIncludeConnections}
          hasDependencyFilter={hasDependencyFilter}
          selectedDependencyProposalIds={selectedDependencyProposalIds}
          dependencyMetricsApproachOptions={dependencyMetrics.dependencyMetricsApproachOptions}
          activeDependencyMetricsApproach={dependencyMetrics.activeDependencyMetricsApproach}
          setSelectedDependencyMetricsApproach={dependencyMetrics.setSelectedDependencyMetricsApproach}
          activeDependencyMetrics={dependencyMetrics.activeDependencyMetrics}
          dependencyMetrics={dependencyMetrics.dependencyViewMetrics}
          showExperimentalFeatures={showExperimentalFeatures}
        />
      </div>
      {showConformitySection && (
        <div id="dashboard-conformity" className="dashboard-anchor">
          <ConformitySection
            ecosystem={activeEcosystem}
            ecosystemBase={ecosystem}
            selectedSourceIds={selectedSourceIds}
            perSourceDashboardData={perSourceDashboardData}
            sectionSourceView={sectionViews.activeConformitySourceView}
            setSectionSourceView={sectionViewState.setConformitySourceView}
            showExperimentalFeatures={showExperimentalFeatures}
            highlightedConformityProposal={conformityControls.highlightedConformityProposal}
            setHighlightedConformityProposal={conformityControls.setHighlightedConformityProposal}
            conformityRows={dashboardData.conformity.conformityRows}
            conformityFailedChecks={dashboardData.conformity.conformityFailedChecks}
          />
        </div>
      )}
    </>
  );
}
