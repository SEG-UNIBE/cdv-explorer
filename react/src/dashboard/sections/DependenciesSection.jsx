import { useMemo } from 'react';
import { Button } from 'primereact/button';
import { Card } from 'primereact/card';
import { Dropdown } from 'primereact/dropdown';
import { InputText } from 'primereact/inputtext';
import { NetworkDiagram } from '../../NetworkDiagram';
import { ProposalGraphMetricsTable } from '../../ProposalGraphMetricsTable';
import { DependencyComparisonHeatmaps } from '../../DependencyComparisonHeatmaps';
import { ProposalFilterControl } from '../../ProposalFilterControl';
import { useAnalysisMetricTooltip } from '../../useAnalysisMetricTooltip';
import { ExportableCard } from '../ExportableCard';

export function DependenciesSection({
  ecosystem,
  selectedDataset,
  highlightedDependencyProposal,
  setHighlightedDependencyProposal,
  dependencyProposalOptions,
  dependencyMinRelations,
  setDependencyMinRelations,
  dependencyMinRelationsIncludeConnections,
  setDependencyMinRelationsIncludeConnections,
  dependencyFilterText,
  setDependencyFilterText,
  dependencyIncludeConnections,
  setDependencyIncludeConnections,
  hasDependencyFilter,
  selectedDependencyProposalIds,
  dependencyMetricsApproachOptions,
  activeDependencyMetricsApproach,
  setSelectedDependencyMetricsApproach,
  activeDependencyMetrics,
  dependencyMetrics,
}) {
  const {
    showTooltip: showMetricTooltip,
    moveTooltip: moveMetricTooltip,
    hideTooltip: hideMetricTooltip,
  } = useAnalysisMetricTooltip();

  const dependencyMetricCards = useMemo(() => ([
    {
      label: 'Nodes',
      value: activeDependencyMetrics.summary?.node_count ?? 0,
      description: 'Total number of distinct proposals represented as nodes in the selected interrelation graph.',
    },
    {
      label: 'Edges',
      value: activeDependencyMetrics.summary?.edge_count ?? 0,
      description: 'Total number of directed relationships between proposals in the selected extraction approach.',
    },
    {
      label: 'Isolated Nodes',
      value: activeDependencyMetrics.summary?.isolated_node_count ?? 0,
      description: 'Number of proposals with neither incoming nor outgoing relationships in the selected graph.',
    },
    {
      label: 'Circular Dependencies',
      value: activeDependencyMetrics.summary?.circular_dependency_count ?? 0,
      description: 'Number of dependency cycles detected in the selected interrelation graph.',
    },
    {
      label: 'Density',
      value: Number(activeDependencyMetrics.summary?.density || 0).toFixed(4).replace(/\.?0+$/, ''),
      description: 'Share of all possible directed proposal-to-proposal links that actually exist. Higher density means a more interconnected graph.',
    },
  ]), [activeDependencyMetrics.summary]);

  return (
    <section className="dashboard-section">
      <div className="dashboard-section__header">
        <h2 className="dashboard-section__title">Dependencies</h2>
      </div>
      <ExportableCard className="mb-4" exportTitle="Proposal Interrelation Graph">
        <h3>Proposal Interrelation Graph</h3>
        <p>
          Three relationship-extraction approaches visualized as a directed graph. Node size reflects document length (word count) and edges represent relationships between proposals. <strong>Preamble</strong> extracts explicitly stated dependencies from the preamble. <strong>Regex</strong> captures explicit proposal references via pattern matching. <strong>LLM</strong> infers implicit dependencies using a language model.
        </p>
        <div className="network-finder">
          <div className="network-finder__copy">
            <strong>Find proposal.</strong>
            <span>Search a proposal ID to highlight and center its node in the network.</span>
          </div>
          <div className="network-finder__controls">
            <InputText
              value={highlightedDependencyProposal}
              onChange={(event) => setHighlightedDependencyProposal(event.target.value)}
              placeholder="Type a proposal ID, e.g. BIP32"
              aria-label="Find proposal: search by ID to highlight its node"
              list="dependency-proposal-options"
            />
            <datalist id="dependency-proposal-options">
              {dependencyProposalOptions.map((proposalId) => (
                <option key={proposalId} value={proposalId} />
              ))}
            </datalist>
            <Button
              type="button"
              label="Clear"
              severity="secondary"
              text
              onClick={() => setHighlightedDependencyProposal('')}
              disabled={!highlightedDependencyProposal.trim()}
            />
          </div>
        </div>
        <div className="wordcloud-filter">
          <div className="wordcloud-filter__copy">
            <strong>Filter proposals.</strong>
          </div>
          <div className="wordcloud-filter__controls">
            <ProposalFilterControl
              value={dependencyFilterText}
              onChange={setDependencyFilterText}
              ecosystem={ecosystem}
              placeholder="Type BIP, then 2,3-5 and press Enter"
              aria-label="Filter proposals by ID (e.g. BIP32, SLIP44, BIP30-BIP35)"
            />
            <label className="dependency-filter-checkbox">
              <input
                type="checkbox"
                checked={dependencyIncludeConnections}
                onChange={(event) => setDependencyIncludeConnections(event.target.checked)}
              />
              <span>transient</span>
            </label>
            <Button
              type="button"
              label="Clear"
              severity="secondary"
              text
              onClick={() => setDependencyFilterText('')}
              disabled={!hasDependencyFilter}
            />
          </div>
        </div>
        <NetworkDiagram
          data={selectedDataset}
          width={1200}
          height={700}
          highlightProposal={highlightedDependencyProposal}
          proposalShortPlural={ecosystem.proposalShortPlural}
          minRelations={dependencyMinRelations}
          setMinRelations={setDependencyMinRelations}
          proposalFilterIds={selectedDependencyProposalIds}
          setProposalFilterText={setDependencyFilterText}
          includeConnections={dependencyIncludeConnections}
          setIncludeConnections={setDependencyIncludeConnections}
          includeThresholdConnections={dependencyMinRelationsIncludeConnections}
          setIncludeThresholdConnections={setDependencyMinRelationsIncludeConnections}
        />
      </ExportableCard>
      <Card className="mb-4">
        <h3>Proposal Interrelation Metrics</h3>
        <p>
          Compare simple graph-level structure and per-proposal centrality measures across
          {' '}Preamble, Regex, and LLM.{' '}
          <strong>In Degree</strong> measures how many other proposals refer to a given one (incoming relation).{' '}
          <strong>Out Degree</strong> measures how many other proposals a given one refers to (outgoing relation).{' '}
          <strong>Weighted Eigenvector</strong> measures how central a proposal is by considering how well-connected the ones it is linked to are.{' '}
          <strong>PageRank</strong> is similar, but additionally accounts for direction and distributes importance across outgoing links.{' '}
          <strong>Betweenness</strong> measures how often a proposal lies on the shortest paths between others, indicating its role in connecting otherwise separate parts of the dependency graph. 
        </p>
        <div className="dependency-metrics-toolbar">
          <div className="dependency-metrics-toolbar__copy">
            <strong>Reference approach.</strong>
            <span>Select which extracted relationship set, Preamble, Regex, or LLM, should drive the metrics below.</span>
          </div>
          <Dropdown
            value={activeDependencyMetricsApproach}
            options={dependencyMetricsApproachOptions}
            onChange={(event) => setSelectedDependencyMetricsApproach(event.value)}
            placeholder="Select approach"
            aria-label="Reference approach for dependency metrics"
            className="dependency-metrics-toolbar__dropdown"
          />
        </div>
        <div className="analysis-grid dependency-metrics-summary">
          {dependencyMetricCards.map((metric) => (
            <div
              key={metric.label}
              className="analysis-stat analysis-stat--interactive"
              onMouseEnter={(event) => showMetricTooltip(event, metric.description)}
              onMouseMove={moveMetricTooltip}
              onMouseLeave={hideMetricTooltip}
            >
              <h4>{metric.label}</h4>
              <p>{metric.value}</p>
            </div>
          ))}
        </div>
        <ProposalGraphMetricsTable
          rows={activeDependencyMetrics.per_bip || []}
          proposalShortLabel={ecosystem.acronym || 'IP'}
          defaultSortField="pagerank"
          defaultSortOrder={-1}
        />
      </Card>
      <ExportableCard className="mb-4" exportTitle="Comparison of Pairwise Interrelation Extraction Approach">
        <h3>Comparison of Pairwise Interrelation Extraction Approach</h3>
        <p>
          This matrix compares Preamble, Regex, and LLM pairwise. Each cell splits into
          three clickable shares: same, missing from the selected approach, and only in the selected approach.
        </p>
        <DependencyComparisonHeatmaps
          pairwiseComparisons={dependencyMetrics?.pairwise_comparisons || {}}
          proposalShortLabel={ecosystem.acronym || 'BIP'}
        />
      </ExportableCard>
    </section>
  );
}
