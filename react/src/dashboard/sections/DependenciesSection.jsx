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
  GROUND_TRUTH_CUTOFF_MODE_ALL,
  GROUND_TRUTH_CUTOFF_MODE_ON_OR_BEFORE,
  GROUND_TRUTH_CUTOFF_MODE_OPTIONS,
  GROUND_TRUTH_MATCH_MODE_EDGE_ONLY,
  GROUND_TRUTH_MATCH_MODE_EXACT_TYPE,
  GROUND_TRUTH_MATCH_MODE_OPTIONS,
  GT_TYPE_ALL,
} from '../../dependencyGroundTruthEvaluation';
import { getDependencyApproachLabel, GROUND_TRUTH_CURATED } from '../../dependencyApproaches';
import { resolveRelationOntology } from '../../dependencyRelationOntology';
import { useAnalysisMetricTooltip } from '../../useAnalysisMetricTooltip';
import { ExportableCard } from '../ExportableCard';
import { CollapsibleControls } from '../CollapsibleControls';
import { SectionSourceToggle } from './SectionSourceToggle';

const MATCH_MODE_TOOLTIP = '<strong>Edge Only</strong> matches directed source-target pairs regardless of relation type.'
  + '<br /><br /><strong>Exact Type</strong> additionally requires the relation type to match. Choose which extracted '
  + 'subtypes to score and how they map to a ground-truth type in the table below.';

const SCOPE_TOOLTIP = 'Reviewed scores only completed benchmark reviews from ips.csv, while All scores every extracted source IP in the dataset.';

const GT_CUTOFF_TOOLTIP = '<strong>All completed reviews</strong>: use the full reviewed benchmark scope and all curated GT edges.'
  + '<br /><br /><strong>Reviewed on or before</strong>: include only reviewed IPs and curated GT edges whose '
  + '<code>reviewed_at</code> date is on or before the selected cutoff. Review dates refer to the latest available proposal '
  + 'version at review time.';

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
  activeDependencyLlmModel,
  dependencyMetricsApproachOptions,
  activeDependencyMetricsApproach,
  setSelectedDependencyMetricsApproach,
  activeDependencyMetrics,
  dependencyMetrics,
  showExperimentalFeatures,
}) {
  const [groundTruthMatchMode, setGroundTruthMatchMode] = useState(GROUND_TRUTH_MATCH_MODE_EDGE_ONLY);
  const [restrictToReviewedSources, setRestrictToReviewedSources] = useState(true);
  const [groundTruthCutoffMode, setGroundTruthCutoffMode] = useState(GROUND_TRUTH_CUTOFF_MODE_ALL);
  const [groundTruthCutoffDate, setGroundTruthCutoffDate] = useState('');
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
  const availableGroundTruthReviewDates = useMemo(() => {
    const seen = new Set();
    const values = [
      ...(selectedDataset?.links?.[GROUND_TRUTH_CURATED] || []).map((edge) => String(edge?.reviewed_at || '').trim()),
      ...(selectedDataset?.groundTruthReviewedIps || []).map((entry) => String(entry?.reviewed_at || '').trim()),
    ];
    return values
      .filter((value) => /^\d{4}-\d{2}-\d{2}$/.test(value))
      .filter((value) => {
        if (seen.has(value)) {
          return false;
        }
        seen.add(value);
        return true;
      })
      .sort();
  }, [selectedDataset]);
  const latestGroundTruthReviewDate = availableGroundTruthReviewDates[availableGroundTruthReviewDates.length - 1] || '';
  useEffect(() => {
    if (!availableGroundTruthReviewDates.length) {
      if (groundTruthCutoffDate) {
        setGroundTruthCutoffDate('');
      }
      return;
    }
    if (!groundTruthCutoffDate || !availableGroundTruthReviewDates.includes(groundTruthCutoffDate)) {
      setGroundTruthCutoffDate(latestGroundTruthReviewDate);
    }
  }, [availableGroundTruthReviewDates, groundTruthCutoffDate, latestGroundTruthReviewDate]);
  const groundTruthEvaluation = useMemo(
    () => buildGroundTruthEvaluation(selectedDataset, {
      matchMode: groundTruthMatchMode,
      ontology: relationOntology,
      typeMapping,
      restrictToReviewedSources,
      gtCutoffMode: groundTruthCutoffMode,
      gtCutoffDate: groundTruthCutoffDate,
    }),
    [groundTruthMatchMode, selectedDataset, relationOntology, typeMapping, restrictToReviewedSources, groundTruthCutoffMode, groundTruthCutoffDate],
  );
  const groundTruthSummaryCards = useMemo(() => (
    groundTruthEvaluation
      ? [
        {
          label: 'GT Nodes',
          value: groundTruthEvaluation.reviewedProposalCount,
          description: 'Number of distinct reviewed IPs included in the curated benchmark scope. This comes from completed reviewed entries, including IPs with no documented GT edge.',
        },
        {
          label: 'GT Edges',
          value: groundTruthEvaluation.goldEdgeCount,
          description: 'Number of unique documented ground-truth interrelations used as the reference edge set.',
        },
        {
          label: 'Coverage',
          value: groundTruthEvaluation.totalProposalCount
            ? `${((groundTruthEvaluation.reviewedProposalCount / groundTruthEvaluation.totalProposalCount) * 100).toFixed(1)}%`
            : '—',
          description: 'Share of all IPs in the dataset that are explicitly covered by the reviewed benchmark scope. Lower coverage means the evaluation reflects only a small curated slice of the ecosystem.',
        },
      ]
      : []
  ), [groundTruthEvaluation]);
  const groundTruthMethodologyText = useMemo(() => {
    const reviewedIps = Array.isArray(selectedDataset?.groundTruthReviewedIps)
      ? selectedDataset.groundTruthReviewedIps.filter(Boolean)
      : [];
    if (!reviewedIps.length) {
      return 'This benchmark compares Preamble, Regex, and LLM against manually reviewed source IPs and their documented interrelations.';
    }

    const sourceSlugLabels = new Map(
      Object.values(ecosystemBase?.sources || {}).map((source) => [
        String(source?.sourceSlug || '').trim(),
        String(source?.acronym || source?.shortLabel || source?.label || source?.sourceSlug || '').trim(),
      ]),
    );
    const sourceLabels = Array.from(new Set(
      reviewedIps
        .map((entry) => String(entry?.source_slug || String(entry?.ip || '').split(':', 1)[0] || '').trim())
        .filter(Boolean)
        .map((slug) => sourceSlugLabels.get(slug) || slug.toUpperCase()),
    ));
    const reviewedTypes = Array.from(new Set(
      reviewedIps
        .map((entry) => String(entry?.type || '').trim())
        .filter(Boolean),
    ));
    const densityBases = Array.from(new Set(
      reviewedIps
        .map((entry) => String(entry?.density_basis || '').trim())
        .filter((value) => value && value !== '-'),
    ));

    const sourceText = sourceLabels.length === 1
      ? `reviewed source IPs are sampled from the ${sourceLabels[0]} catalogue only`
      : `reviewed source IPs are sampled from the ${sourceLabels.join(' + ')} catalogues only`;
    const typeText = reviewedTypes.length === 1
      ? ` and restricted to proposals of type ${reviewedTypes[0]}`
      : '';
    const densityText = densityBases.length === 1 && densityBases[0] === 'llm_only'
      ? 'an approximate dependency-density signal derived from LLM-mined interdependencies'
      : 'an approximate extracted dependency-density signal';

    return `This benchmark compares Preamble, Regex, and LLM against a curated ground truth (GT) built from manually reviewed source IPs and their documented interrelations. For the current benchmark, ${sourceText}${typeText}. The reviewed IPs are then randomly sampled across stratified buckets defined by (i) proposal era based on creation date (early, middle, recent) and (ii) ${densityText} (none, low, high).`;
  }, [ecosystemBase?.sources, selectedDataset]);
  const groundTruthScopeStats = useMemo(() => {
    if (!groundTruthEvaluation) {
      return '';
    }
    const nodeCount = restrictToReviewedSources
      ? groundTruthEvaluation.reviewedProposalCount
      : groundTruthEvaluation.totalProposalCount;
    return `Nodes=${nodeCount}`;
  }, [groundTruthEvaluation, restrictToReviewedSources]);

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
          activeLlmModel={activeDependencyLlmModel}
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
              <div className="dependency-metrics-toolbar__dropdown-row">
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
          activeLlmModel={activeDependencyLlmModel}
        />
      </ExportableCard>
      {showExperimentalFeatures && groundTruthEvaluation ? (
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
            {groundTruthMethodologyText}
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
                                <td>{getDependencyApproachLabel(row.approach, activeDependencyLlmModel)}</td>
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
                                <td>{getDependencyApproachLabel(row.approach, activeDependencyLlmModel)}</td>
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
                    <span className={`ground-truth-scope__label${restrictToReviewedSources ? '' : ' is-muted'}`}>
                      Reviewed
                    </span>
                    <InputSwitch
                      inputId="ground-truth-scope-toggle"
                      checked={!restrictToReviewedSources}
                      onChange={(event) => setRestrictToReviewedSources(!event.value)}
                    />
                    <span className={`ground-truth-scope__label${restrictToReviewedSources ? ' is-muted' : ''}`}>
                      All
                    </span>
                    <span className="ground-truth-scope__stats">{groundTruthScopeStats}</span>
                  </div>
                </div>
                <div className="network-layout-picker">
                  <div
                    className="network-layout-picker__label gt-help-label"
                    onMouseEnter={(event) => showHtmlMetricTooltip(event, GT_CUTOFF_TOOLTIP)}
                    onMouseMove={moveMetricTooltip}
                    onMouseLeave={hideMetricTooltip}
                  >
                    GT Cutoff
                  </div>
                  <div className="ground-truth-cutoff">
                    <Dropdown
                      value={groundTruthCutoffMode}
                      options={GROUND_TRUTH_CUTOFF_MODE_OPTIONS}
                      optionLabel="label"
                      optionValue="value"
                      onChange={(event) => setGroundTruthCutoffMode(event.value)}
                      aria-label="Ground-truth cutoff mode"
                      className="ground-truth-cutoff__mode"
                    />
                    <input
                      type="date"
                      className="p-inputtext ground-truth-cutoff__date"
                      value={groundTruthCutoffDate}
                      onChange={(event) => setGroundTruthCutoffDate(event.target.value)}
                      disabled={groundTruthCutoffMode !== GROUND_TRUTH_CUTOFF_MODE_ON_OR_BEFORE || !availableGroundTruthReviewDates.length}
                      max={latestGroundTruthReviewDate || undefined}
                      aria-label="Ground-truth cutoff date"
                    />
                  </div>
                </div>
              </div>
            </div>
          </CollapsibleControls>
          <DependencyGroundTruthEvaluationCharts
            evaluation={groundTruthEvaluation}
            activeLlmModel={activeDependencyLlmModel}
          />
        </ExportableCard>
      ) : null}
    </section>
  );
}
