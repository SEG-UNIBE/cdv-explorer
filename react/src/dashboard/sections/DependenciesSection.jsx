import { useEffect, useMemo, useState } from 'react';
import { Button } from 'primereact/button';
import { Card } from 'primereact/card';
import { Dropdown } from 'primereact/dropdown';
import { InputSwitch } from 'primereact/inputswitch';
import { RadioButton } from 'primereact/radiobutton';
import { Tag } from 'primereact/tag';
import { NetworkDiagram } from '../../NetworkDiagram';
import { ProposalGraphMetricsTable } from '../../ProposalGraphMetricsTable';
import { DependencyComparisonHeatmaps } from '../../DependencyComparisonHeatmaps';
import { DependencyGroundTruthEvaluationCharts } from '../../DependencyGroundTruthEvaluationCharts';
import { ProposalFilterControl } from '../../ProposalFilterControl';
import {
  buildDefaultTypeMapping,
  buildGroundTruthEvaluation,
  GROUND_TRUTH_MATCH_MODE_EDGE_ONLY,
  GROUND_TRUTH_MATCH_MODE_EXACT_TYPE,
  GROUND_TRUTH_MATCH_MODE_OPTIONS,
  GT_TYPE_ALL,
} from '../../dependencyGroundTruthEvaluation';
import { DEPENDENCY_SHORT_LABELS } from '../../dependencyApproaches';
import { resolveRelationOntology } from '../../dependencyRelationOntology';
import { useAnalysisMetricTooltip } from '../../useAnalysisMetricTooltip';
import { ExportableCard } from '../ExportableCard';
import { CollapsibleControls } from '../CollapsibleControls';
import { SectionSourceToggle } from './SectionSourceToggle';

const MATCH_MODE_TOOLTIP = '<strong>Edge Only</strong> matches directed source-target pairs regardless of relation type.'
  + '<br /><br /><strong>Exact Type</strong> additionally requires the relation type to match. Choose which extracted '
  + 'subtypes to score and how they map to a ground-truth type in the table below.';

const SCOPE_TOOLTIP = '<strong>GT source nodes only</strong>: scoring is limited to IPs that have curated outgoing GT links.'
  + '<br /><br /><strong>All IPs</strong>: every extracted edge is scored, so edges from IPs without curated ground '
  + 'truth count as false positives.';

export function DependenciesSection({
  ecosystem,
  ecosystemBase,
  selectedSourceIds = [],
  sectionSourceView,
  setSectionSourceView,
  selectedDataset,
  highlightedDependencyProposal,
  setHighlightedDependencyProposal,
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
  const [groundTruthMatchMode, setGroundTruthMatchMode] = useState(GROUND_TRUTH_MATCH_MODE_EDGE_ONLY);
  const [restrictToCuratedSources, setRestrictToCuratedSources] = useState(true);
  const {
    showTooltip: showMetricTooltip,
    showHtmlTooltip: showHtmlMetricTooltip,
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
      label: 'Circ. Deps.',
      value: activeDependencyMetrics.summary?.circular_dependency_count ?? 0,
      description: 'Number of dependency cycles detected in the selected interrelation graph.',
    },
    {
      label: 'Density',
      value: Number(activeDependencyMetrics.summary?.density || 0).toFixed(4).replace(/\.?0+$/, ''),
      description: 'Share of all possible directed proposal-to-proposal links that actually exist. Higher density means a more interconnected graph.',
    },
  ]), [activeDependencyMetrics.summary]);
  const relationOntology = useMemo(
    () => resolveRelationOntology(ecosystem?.id, {
      sourceIds: selectedSourceIds.length ? selectedSourceIds : null,
    }),
    [ecosystem?.id, selectedSourceIds],
  );
  // Default relation-type mapping, discovered from the dataset and prefilled from
  // the declared ontology. Editable user state resets to this whenever the
  // dataset, ecosystem, or source selection changes.
  const defaultTypeMapping = useMemo(
    () => buildDefaultTypeMapping(selectedDataset, relationOntology),
    [selectedDataset, relationOntology],
  );
  const [typeMapping, setTypeMapping] = useState(defaultTypeMapping);
  useEffect(() => {
    setTypeMapping(defaultTypeMapping);
  }, [defaultTypeMapping]);
  const updateTypeMappingRow = (index, patch) => {
    setTypeMapping((prev) => ({
      ...prev,
      rows: prev.rows.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    }));
  };
  const groundTruthEvaluation = useMemo(
    () => buildGroundTruthEvaluation(selectedDataset, {
      matchMode: groundTruthMatchMode,
      ontology: relationOntology,
      typeMapping,
      restrictToCuratedSources,
    }),
    [groundTruthMatchMode, selectedDataset, relationOntology, typeMapping, restrictToCuratedSources],
  );
  const groundTruthSummaryCards = useMemo(() => (
    groundTruthEvaluation
      ? [
        {
          label: 'GT Source Nodes',
          value: groundTruthEvaluation.curatedProposalCount,
          description: 'Number of distinct IPs with at least one curated ground-truth outgoing interrelation in the selected dataset.',
        },
        {
          label: 'GT Target Nodes',
          value: groundTruthEvaluation.curatedTargetCount,
          description: 'Number of distinct IPs referenced as targets by at least one curated ground-truth edge.',
        },
        {
          label: 'GT Edges',
          value: groundTruthEvaluation.goldEdgeCount,
          description: 'Number of unique directed ground-truth edges used as the reference set.',
        },
        {
          label: 'GT Coverage',
          value: groundTruthEvaluation.totalProposalCount
            ? `${((groundTruthEvaluation.curatedProposalCount / groundTruthEvaluation.totalProposalCount) * 100).toFixed(1)}%`
            : '—',
          description: 'Share of all IPs in the dataset that have at least one curated ground-truth outgoing interrelation. Lower coverage means the evaluation reflects only a small curated slice of the ecosystem.',
        },
      ]
      : []
  ), [groundTruthEvaluation]);

  return (
    <section className="dashboard-section">
      <div className="dashboard-section__header">
        <h2 className="dashboard-section__title">Dependencies</h2>
        <SectionSourceToggle
          ecosystemBase={ecosystemBase}
          selectedSourceIds={selectedSourceIds}
          value={sectionSourceView}
          onChange={setSectionSourceView}
          supportsMerged
        />
      </div>
      <ExportableCard className="mb-4" exportTitle="Proposal Interrelation Graph">
        <h3>Proposal Interrelation Graph</h3>
        <p>
          Three relationship-extraction approaches visualized as a directed graph. Node size reflects document length (word count) and edges represent relationships between proposals. <strong>Preamble</strong> extracts explicitly stated dependencies from the preamble. <strong>Regex</strong> captures explicit proposal references via pattern matching. <strong>LLM</strong> infers implicit dependencies using a language model.
        </p>
        <NetworkDiagram
          data={selectedDataset}
          width={1200}
          height={700}
          controlsClassName="dependency-graph-controls"
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
          extraControls={(
            <div className="dependency-graph-search-grid">
              <ProposalFilterControl
                value={highlightedDependencyProposal}
                onChange={setHighlightedDependencyProposal}
                ecosystem={ecosystem}
                ariaLabel="Find proposal: search by ID to highlight its node"
                singleSelect
                layout="split"
                entryLabel="Proposal Search"
                trailingControl={(
                  <Button
                    type="button"
                    label="Clear"
                    severity="secondary"
                    text
                    onClick={() => setHighlightedDependencyProposal('')}
                    disabled={!highlightedDependencyProposal.trim()}
                  />
                )}
                className="dependency-graph-search-control dependency-graph-search-control--find"
              />
              <ProposalFilterControl
                value={dependencyFilterText}
                onChange={setDependencyFilterText}
                ecosystem={ecosystem}
                ariaLabel="Filter proposals by ID (e.g. BIP32, SLIP44, BIP30-BIP35)"
                layout="split"
                entryLabel="Filter Proposals"
                trailingControl={(
                  <Button
                    type="button"
                    label="Clear"
                    severity="secondary"
                    text
                    onClick={() => setDependencyFilterText('')}
                    disabled={!hasDependencyFilter}
                  />
                )}
                className="dependency-graph-search-control dependency-graph-search-control--filter wordcloud-filter--chips-right"
              />
            </div>
          )}
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
        <div className="dependency-metrics-summary">
          {dependencyMetricCards.map((metric) => (
            <div
              key={metric.label}
              className="metric-badge"
              onMouseEnter={(event) => showMetricTooltip(event, metric.description)}
              onMouseMove={moveMetricTooltip}
              onMouseLeave={hideMetricTooltip}
            >
              <span className="metric-badge__label">{metric.label}</span>
              <span className="metric-badge__value">{metric.value}</span>
            </div>
          ))}
        </div>
        <CollapsibleControls>
          <div className="dependency-metrics-toolbar">
            <div className="dependency-metrics-toolbar__field">
              <label className="dependency-metrics-toolbar__label" htmlFor="dependency-metrics-approach">
                Approach
              </label>
              <Dropdown
                inputId="dependency-metrics-approach"
                value={activeDependencyMetricsApproach}
                options={dependencyMetricsApproachOptions}
                onChange={(event) => setSelectedDependencyMetricsApproach(event.value)}
                placeholder="Select approach"
                aria-label="Approach for dependency metrics"
                className="dependency-metrics-toolbar__dropdown"
              />
            </div>
            <ProposalFilterControl
              value={dependencyFilterText}
              onChange={setDependencyFilterText}
              ecosystem={ecosystem}
              ariaLabel="Filter proposals for dependency metrics"
              layout="split"
              entryLabel="Filter Proposals"
              trailingControl={(
                <Button
                  type="button"
                  label="Clear"
                  severity="secondary"
                  text
                  onClick={() => setDependencyFilterText('')}
                  disabled={!hasDependencyFilter}
                />
              )}
              className="dependency-metrics-toolbar__filter"
            />
          </div>
        </CollapsibleControls>
        <ProposalGraphMetricsTable
          rows={activeDependencyMetrics.per_bip || []}
          proposalFilterIds={selectedDependencyProposalIds}
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
      {groundTruthEvaluation ? (
        <ExportableCard className="mb-4" exportTitle="Experimental Ground Truth Evaluation">
          <h3 className="card-title-with-badge">
            Ground Truth Evaluation
            <Tag
              className="dashboard-section__tag card-title-with-badge__tag"
              severity="warning"
              value="Experimental"
            />
          </h3>
          <p>
            Compares Preamble, Regex, and LLM against the curated Ground Truth (GT) interrelations in the selected dataset.
            Use the controls to choose the match mode and whether to restrict scoring to proposals with curated GT links.
          </p>
          <div className="dependency-metrics-summary">
            {groundTruthSummaryCards.map((metric) => (
              <div
                key={metric.label}
                className="metric-badge"
                onMouseEnter={(event) => showMetricTooltip(event, metric.description)}
                onMouseMove={moveMetricTooltip}
                onMouseLeave={hideMetricTooltip}
              >
                <span className="metric-badge__label">{metric.label}</span>
                <span className="metric-badge__value">{metric.value}</span>
              </div>
            ))}
          </div>
          <CollapsibleControls>
            <div className="ground-truth-evaluation-controls">
              <div className="ground-truth-evaluation-controls__column">
                <div className="network-layout-picker">
                  <div
                    className="network-layout-picker__label gt-help-label"
                    onMouseEnter={(event) => showHtmlMetricTooltip(event, MATCH_MODE_TOOLTIP)}
                    onMouseMove={moveMetricTooltip}
                    onMouseLeave={hideMetricTooltip}
                  >
                    Match Mode
                  </div>
                  <div className="network-layout-picker__options">
                    {GROUND_TRUTH_MATCH_MODE_OPTIONS.map((option) => (
                      <label key={option.value} className="network-layout-picker__option">
                        <RadioButton
                          inputId={`ground-truth-match-mode-${option.value}`}
                          name="ground-truth-match-mode"
                          value={option.value}
                          onChange={(event) => setGroundTruthMatchMode(event.value)}
                          checked={groundTruthMatchMode === option.value}
                        />
                        <span>{option.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
                {groundTruthMatchMode === GROUND_TRUTH_MATCH_MODE_EXACT_TYPE ? (
                  <div className="gt-type-mapping">
                    <div className="gt-type-mapping__header">
                      <span className="gt-type-mapping__title">Relation-type mapping</span>
                      <Button
                        type="button"
                        label="Reset to default"
                        severity="secondary"
                        text
                        onClick={() => setTypeMapping(defaultTypeMapping)}
                      />
                    </div>
                    {typeMapping.rows.length ? (
                      <table className="gt-type-mapping__table">
                        <thead>
                          <tr>
                            <th>Use</th>
                            <th>Approach</th>
                            <th>Extracted subtype</th>
                            <th>Treat as GT type</th>
                          </tr>
                        </thead>
                        <tbody>
                          {typeMapping.rows.map((row, index) => (
                            row.empty ? (
                              <tr key={`${row.approach}:::empty`} className="gt-type-mapping__row--empty">
                                <td>
                                  <input type="checkbox" checked={false} disabled aria-label="No relations extracted" />
                                </td>
                                <td>{DEPENDENCY_SHORT_LABELS[row.approach] || row.approach}</td>
                                <td colSpan={2}><span className="gt-type-mapping__muted">no relations extracted</span></td>
                              </tr>
                            ) : (
                              <tr key={`${row.approach}:::${row.subtype}`}>
                                <td>
                                  <input
                                    type="checkbox"
                                    checked={row.include}
                                    aria-label={`Include ${row.subtype}`}
                                    onChange={(event) => updateTypeMappingRow(index, { include: event.target.checked })}
                                  />
                                </td>
                                <td>{DEPENDENCY_SHORT_LABELS[row.approach] || row.approach}</td>
                                <td><code>{row.subtype}</code></td>
                                <td>
                                  <select
                                    className="gt-type-mapping__select"
                                    value={row.target || ''}
                                    disabled={!row.include || !typeMapping.gtTypes.length}
                                    onChange={(event) => updateTypeMappingRow(index, { target: event.target.value })}
                                  >
                                    <option value="" disabled>
                                      No default GT type
                                    </option>
                                    {typeMapping.gtTypes.map((gtType) => (
                                      <option key={gtType} value={gtType}>{gtType}</option>
                                    ))}
                                    <option value={GT_TYPE_ALL}>(all types)</option>
                                  </select>
                                </td>
                              </tr>
                            )
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <p className="ground-truth-evaluation-controls__note">
                        The selected dataset has no extracted relation subtypes to map.
                      </p>
                    )}
                  </div>
                ) : null}
              </div>
              <div className="ground-truth-evaluation-controls__column">
                <div className="network-layout-picker">
                  <div
                    className="network-layout-picker__label gt-help-label"
                    onMouseEnter={(event) => showHtmlMetricTooltip(event, SCOPE_TOOLTIP)}
                    onMouseMove={moveMetricTooltip}
                    onMouseLeave={hideMetricTooltip}
                  >
                    Scope
                  </div>
                  <div className="ground-truth-scope">
                    <span className={`ground-truth-scope__label${restrictToCuratedSources ? '' : ' is-muted'}`}>
                      GT source nodes only
                    </span>
                    <InputSwitch
                      inputId="ground-truth-scope-toggle"
                      checked={!restrictToCuratedSources}
                      onChange={(event) => setRestrictToCuratedSources(!event.value)}
                    />
                    <span className={`ground-truth-scope__label${restrictToCuratedSources ? ' is-muted' : ''}`}>
                      All IPs
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </CollapsibleControls>
          <DependencyGroundTruthEvaluationCharts evaluation={groundTruthEvaluation} />
        </ExportableCard>
      ) : null}
    </section>
  );
}
