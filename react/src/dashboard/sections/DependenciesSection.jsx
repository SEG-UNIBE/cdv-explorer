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
  GROUND_TRUTH_CUTOFF_MODE_BETWEEN,
  GROUND_TRUTH_CUTOFF_MODE_ON_OR_BEFORE,
  GROUND_TRUTH_CUTOFF_MODE_OPTIONS,
  GROUND_TRUTH_MATCH_MODE_EDGE_ONLY,
  GROUND_TRUTH_MATCH_MODE_EXACT_TYPE,
  GROUND_TRUTH_MATCH_MODE_OPTIONS,
  GT_TYPE_ALL,
} from '../../dependencyGroundTruthEvaluation';
import {
  buildDependencyLinkTypeOptions,
  DEFAULT_DEPENDENCY_APPROACH,
  getDependencyApproachLabel,
  GROUND_TRUTH_CURATED,
} from '../../dependencyApproaches';
import { resolveRelationOntology } from '../../dependencyRelationOntology';
import { renderTooltipCardHtml } from '../../tooltipHtml';
import { useAnalysisMetricTooltip } from '../../useAnalysisMetricTooltip';
import { ExportableCard } from '../ExportableCard';
import { CollapsibleControls } from '../CollapsibleControls';
import { SectionSourceToggle, SECTION_VIEW_MERGED } from './SectionSourceToggle';

const MATCH_MODE_TOOLTIP = '<strong>Edge Only</strong> matches directed source-target pairs regardless of relation type.'
  + '<br /><br /><strong>Exact Type</strong> additionally requires the relation type to match. Choose which extracted '
  + 'subtypes to score and how they map to a ground-truth type in the table below.';

const SCOPE_TOOLTIP = 'Reviewed scores only completed benchmark reviews from ips.csv, while All scores every extracted source IP in the dataset.';

const CROSS_SOURCE_TARGETS_TOOLTIP = 'When enabled (default), GT edges and extracted edges whose <em>target</em> belongs to a different IP source (e.g. a BIP referencing a SLIP) are included in the evaluation. '
  + 'Disable this to restrict scoring to same-source edges only. '
  + 'Only meaningful in a single-source view (e.g. BIPs only): in a merged multi-source view every source\'s nodes are already loaded, so this has no effect on the scored edges.';

const GT_CUTOFF_TOOLTIP = '<strong>All completed reviews</strong>: use the full reviewed benchmark scope and all curated GT edges.'
  + '<br /><br /><strong>Reviewed on or before</strong>: include only reviewed IPs and curated GT edges whose '
  + '<code>reviewed_at</code> date is on or before the selected cutoff. Review dates refer to the latest available proposal '
  + 'version at review time.'
  + '<br /><br /><strong>Reviewed on or later</strong>: include only reviewed IPs and curated GT edges whose '
  + '<code>reviewed_at</code> date is on or after the selected cutoff.'
  + '<br /><br /><strong>Reviewed between</strong>: include only reviewed IPs and curated GT edges whose '
  + '<code>reviewed_at</code> date falls within the selected date range.';

function DependencyMetricsCard({
  ecosystem,
  activeDependencyLlmModel,
  dependencyMetrics,
  dependencyFilterText,
  setDependencyFilterText,
  hasDependencyFilter,
  selectedDependencyProposalIds,
  showMetricTooltip,
  moveMetricTooltip,
  hideMetricTooltip,
}) {
  const [selectedApproach, setSelectedApproach] = useState(DEFAULT_DEPENDENCY_APPROACH);
  const dependencyMetricsApproachOptions = useMemo(
    () => buildDependencyLinkTypeOptions(activeDependencyLlmModel).filter(
      (option) => dependencyMetrics?.by_approach?.[option.value]
    ),
    [activeDependencyLlmModel, dependencyMetrics],
  );
  const activeDependencyMetricsApproach = dependencyMetricsApproachOptions.some(
    (option) => option.value === selectedApproach
  )
    ? selectedApproach
    : (dependencyMetricsApproachOptions[0]?.value || DEFAULT_DEPENDENCY_APPROACH);

  useEffect(() => {
    if (!dependencyMetricsApproachOptions.some((option) => option.value === selectedApproach)) {
      setSelectedApproach(dependencyMetricsApproachOptions[0]?.value || DEFAULT_DEPENDENCY_APPROACH);
    }
  }, [dependencyMetricsApproachOptions, selectedApproach]);

  const activeDependencyMetrics = dependencyMetrics?.by_approach?.[activeDependencyMetricsApproach] || {
    summary: {},
    per_bip: [],
  };
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

  return (
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
                onChange={(event) => setSelectedApproach(event.value)}
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
  );
}

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
  dependencyMetrics,
  showExperimentalFeatures,
}) {
  const [groundTruthMatchMode, setGroundTruthMatchMode] = useState(GROUND_TRUTH_MATCH_MODE_EDGE_ONLY);
  const [restrictToReviewedSources, setRestrictToReviewedSources] = useState(true);
  const [allowCrossSourceTargets, setAllowCrossSourceTargets] = useState(true);
  const [groundTruthCutoffMode, setGroundTruthCutoffMode] = useState(GROUND_TRUTH_CUTOFF_MODE_ALL);
  const [groundTruthCutoffStartDate, setGroundTruthCutoffStartDate] = useState('');
  const [groundTruthCutoffEndDate, setGroundTruthCutoffEndDate] = useState('');
  const {
    showTooltip: showMetricTooltip,
    showHtmlTooltip: showHtmlMetricTooltip,
    moveTooltip: moveMetricTooltip,
    hideTooltip: hideMetricTooltip,
  } = useAnalysisMetricTooltip();

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
      if (groundTruthCutoffStartDate) {
        setGroundTruthCutoffStartDate('');
      }
      if (groundTruthCutoffEndDate) {
        setGroundTruthCutoffEndDate('');
      }
      return;
    }
    if (!groundTruthCutoffStartDate) {
      setGroundTruthCutoffStartDate(latestGroundTruthReviewDate);
    }
    if (!groundTruthCutoffEndDate) {
      setGroundTruthCutoffEndDate(latestGroundTruthReviewDate);
    }
  }, [availableGroundTruthReviewDates, groundTruthCutoffStartDate, groundTruthCutoffEndDate, latestGroundTruthReviewDate]);
  const groundTruthEvaluation = useMemo(
    () => buildGroundTruthEvaluation(selectedDataset, {
      matchMode: groundTruthMatchMode,
      ontology: relationOntology,
      typeMapping,
      restrictToReviewedSources,
      allowCrossSourceTargets,
      gtCutoffMode: groundTruthCutoffMode,
      gtCutoffDate: groundTruthCutoffStartDate,
      gtCutoffStartDate: groundTruthCutoffStartDate,
      gtCutoffEndDate: groundTruthCutoffEndDate,
    }),
    [
      groundTruthMatchMode,
      selectedDataset,
      relationOntology,
      typeMapping,
      restrictToReviewedSources,
      allowCrossSourceTargets,
      groundTruthCutoffMode,
      groundTruthCutoffStartDate,
      groundTruthCutoffEndDate,
    ],
  );
  const groundTruthSummaryCards = useMemo(() => {
    if (!groundTruthEvaluation) {
      return [];
    }

    const sourceLabel = (slug) => {
      const src = Object.values(ecosystemBase?.sources || {}).find(
        (s) => String(s?.sourceSlug || '').trim() === slug,
      );
      return String(src?.acronym || src?.shortLabel || src?.label || slug || '').trim().toUpperCase() || slug;
    };

    const nodeRows = Object.entries(groundTruthEvaluation.reviewedBySource || {})
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([slug, count]) => [sourceLabel(slug), String(count)]);

    const edgeRows = Object.entries(groundTruthEvaluation.goldEdgesBySourcePair || {})
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([pair, count]) => {
        const [src, tgt] = pair.split('->');
        return [`${sourceLabel(src)} → ${sourceLabel(tgt)}`, String(count)];
      });

    return [
      {
        label: 'GT Nodes',
        value: groundTruthEvaluation.reviewedProposalCount,
        tooltipHtml: renderTooltipCardHtml({
          titleHtml: '<strong>GT Nodes by source</strong>',
          rows: [
            ['Info', 'Distinct reviewed IPs in the curated benchmark scope, including IPs with no documented GT edge.'],
            ...nodeRows,
          ],
        }),
      },
      {
        label: 'GT Edges',
        value: groundTruthEvaluation.goldEdgeCount,
        tooltipHtml: renderTooltipCardHtml({
          titleHtml: '<strong>GT Edges by source pair</strong>',
          rows: [
            ['Info', 'Unique documented ground-truth interrelations used as the reference edge set.'],
            ...edgeRows,
          ],
        }),
      },
      {
        label: 'Coverage',
        value: groundTruthEvaluation.totalProposalCount
          ? `${((groundTruthEvaluation.reviewedProposalCount / groundTruthEvaluation.totalProposalCount) * 100).toFixed(1)}%`
          : '—',
        tooltipHtml: renderTooltipCardHtml({
          titleHtml: '<strong>Coverage by source</strong>',
          rows: [
            ['Info', 'Per-source coverage; the overall badge value is the size-weighted average across sources.'],
            ...Object.entries(groundTruthEvaluation.totalBySource || {})
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([slug, total]) => {
                const reviewed = (groundTruthEvaluation.reviewedBySource || {})[slug] || 0;
                const pct = total ? ((reviewed / total) * 100).toFixed(1) : '0.0';
                return [sourceLabel(slug), `${reviewed} / ${total} (${pct}%)`];
              }),
            groundTruthEvaluation.totalProposalCount > 0
              ? ['Total', `${groundTruthEvaluation.reviewedProposalCount} / ${groundTruthEvaluation.totalProposalCount} (${((groundTruthEvaluation.reviewedProposalCount / groundTruthEvaluation.totalProposalCount) * 100).toFixed(1)}%)`]
              : null,
          ],
        }),
      },
    ];
  }, [ecosystemBase?.sources, groundTruthEvaluation]);
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

  // The toggle filters GT edges by whether their target node is loaded in the
  // current network. In a merged multi-source view every selected source's
  // nodes are already loaded, so the filter never removes anything there —
  // it only has a real effect when viewing a single source (e.g. BIPs only).
  const isCrossSourceToggleInert = sectionSourceView === SECTION_VIEW_MERGED
    && selectedSourceIds.length > 1;

  const crossSourceTargetsStats = useMemo(() => {
    if (!groundTruthEvaluation || isCrossSourceToggleInert) {
      return '';
    }
    const pairs = groundTruthEvaluation.goldEdgesBySourcePair || {};
    const crossCount = Object.entries(pairs)
      .filter(([pair]) => {
        const [src, tgt] = pair.split('->');
        return src !== tgt;
      })
      .reduce((sum, [, count]) => sum + count, 0);
    return `Edges=${allowCrossSourceTargets ? groundTruthEvaluation.goldEdgeCount : groundTruthEvaluation.goldEdgeCount - crossCount}`;
  }, [allowCrossSourceTargets, groundTruthEvaluation, isCrossSourceToggleInert]);

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
          Three relationship-extraction approaches visualized as a directed graph. Node size reflects document length (word count) and edges represent relationships between proposals. <strong>Preamble</strong> extracts explicitly stated dependencies from the preamble. <strong>Regex</strong> captures explicit proposal references via pattern matching. <strong>LLM</strong> applies LLM-assisted semantic dependency extraction to proposal body text.
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
      <DependencyMetricsCard
        ecosystem={ecosystem}
        activeDependencyLlmModel={activeDependencyLlmModel}
        dependencyMetrics={dependencyMetrics}
        dependencyFilterText={dependencyFilterText}
        setDependencyFilterText={setDependencyFilterText}
        hasDependencyFilter={hasDependencyFilter}
        selectedDependencyProposalIds={selectedDependencyProposalIds}
        showMetricTooltip={showMetricTooltip}
        moveMetricTooltip={moveMetricTooltip}
        hideMetricTooltip={hideMetricTooltip}
      />
      <ExportableCard className="mb-4" exportTitle="Comparison of Pairwise Interrelation Extraction Approach">
        <h3>Comparison of Pairwise Interrelation Extraction Approach</h3>
        <p>
          This matrix compares Preamble, Regex, and LLM pairwise. Each cell splits into
          three clickable shares: same, missing from the selected approach, and only in the selected approach.
          The κ value below each cell is Cohen&apos;s kappa, a measure of inter-rater reliability:
          both approaches are treated as raters giving a yes/no verdict on every possible directed
          proposal pair, and their raw agreement is corrected for the agreement expected by chance.
          κ&nbsp;=&nbsp;1 means perfect agreement, 0 no better than chance, and below 0 worse than chance.
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
                onMouseEnter={(event) => showHtmlMetricTooltip(event, metric.tooltipHtml)}
                onMouseMove={moveMetricTooltip}
                onMouseLeave={hideMetricTooltip}
              >
                <span className="metric-badge__label">{metric.label}</span>
                <span className="metric-badge__value">{metric.value}</span>
              </div>
            ))}
          </div>
          <DependencyGroundTruthEvaluationCharts
            evaluation={groundTruthEvaluation}
            activeLlmModel={activeDependencyLlmModel}
          />
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
                    onMouseEnter={(event) => showHtmlMetricTooltip(event, CROSS_SOURCE_TARGETS_TOOLTIP)}
                    onMouseMove={moveMetricTooltip}
                    onMouseLeave={hideMetricTooltip}
                  >
                    Cross-source Targets
                  </div>
                  <div className="ground-truth-scope">
                    <InputSwitch
                      inputId="ground-truth-cross-source-toggle"
                      checked={allowCrossSourceTargets}
                      disabled={isCrossSourceToggleInert}
                      onChange={(event) => setAllowCrossSourceTargets(event.value)}
                    />
                    <span className={`ground-truth-scope__label${allowCrossSourceTargets && !isCrossSourceToggleInert ? '' : ' is-muted'}`}>
                      {allowCrossSourceTargets ? 'Allowed' : 'Same source only'}
                    </span>
                    {isCrossSourceToggleInert ? (
                      <span className="ground-truth-scope__stats">No effect in merged view</span>
                    ) : (
                      crossSourceTargetsStats ? <span className="ground-truth-scope__stats">{crossSourceTargetsStats}</span> : null
                    )}
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
                    <div className="ground-truth-cutoff__dates">
                      <input
                        type="date"
                        className="p-inputtext ground-truth-cutoff__date"
                        value={groundTruthCutoffStartDate}
                        onChange={(event) => setGroundTruthCutoffStartDate(event.target.value)}
                        disabled={groundTruthCutoffMode === GROUND_TRUTH_CUTOFF_MODE_ALL || !availableGroundTruthReviewDates.length}
                        aria-label={
                          groundTruthCutoffMode === GROUND_TRUTH_CUTOFF_MODE_BETWEEN
                            ? 'Ground-truth cutoff start date'
                            : 'Ground-truth cutoff date'
                        }
                      />
                      {groundTruthCutoffMode === GROUND_TRUTH_CUTOFF_MODE_BETWEEN ? (
                        <input
                          type="date"
                          className="p-inputtext ground-truth-cutoff__date"
                          value={groundTruthCutoffEndDate}
                          onChange={(event) => setGroundTruthCutoffEndDate(event.target.value)}
                          disabled={!availableGroundTruthReviewDates.length}
                          aria-label="Ground-truth cutoff end date"
                        />
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CollapsibleControls>
        </ExportableCard>
      ) : null}
    </section>
  );
}
