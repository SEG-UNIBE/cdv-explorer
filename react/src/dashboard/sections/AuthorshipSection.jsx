import { useMemo, useState } from 'react';
import { Button } from 'primereact/button';
import { InputSwitch } from 'primereact/inputswitch';
import { InputText } from 'primereact/inputtext';
import { Card } from 'primereact/card';
import { Tag } from 'primereact/tag';
import { ProposalTimelineChart } from '../../ProposalTimelineChart';
import { TopAuthorsChart } from '../../TopAuthorsChart';
import { AuthorContributionHistogram } from '../../AuthorContributionHistogram';
import { BipAuthorCountHistogram } from '../../BipAuthorCountHistogram';
import { AuthorCollaborationNetwork } from '../../AuthorCollaborationNetwork';
import { CollaborationClusterSizeDistribution } from '../../CollaborationClusterSizeDistribution';
import { CollaborationDegreeDistribution } from '../../CollaborationDegreeDistribution';
import { AuthorCentralityTable } from '../../AuthorCentralityTable';
import { WordCloud } from '../../WordCloud';
import { ProposalFilterControl } from '../../ProposalFilterControl';
import { useAnalysisMetricTooltip } from '../../useAnalysisMetricTooltip';
import { ExportableCard } from '../ExportableCard';
import { CollapsibleControls } from '../CollapsibleControls';
import { SectionSourceToggle } from './SectionSourceToggle';

// Section-wide terminology: an "Originator" is a person the proposal itself
// declares (preamble authors, or the initial committer where no preamble
// exists); a "Contributor" is anyone who committed changes to the proposal
// file per full git history.
const AUTHOR_BASIS_OPTIONS = [
  { value: 'declared', label: 'Originators' },
  { value: 'contributors', label: 'Contributors' },
];

function LogScaleToggle({ inputId, value, onChange }) {
  return (
    <div className="author-collaboration-switch-row">
      <label htmlFor={inputId}>Log scale</label>
      <InputSwitch
        inputId={inputId}
        checked={Boolean(value)}
        onChange={(event) => onChange(event.value)}
        aria-label="Toggle logarithmic y-axis"
        className="author-collaboration-switch"
      />
    </div>
  );
}

// Per-tile switch between the originator and contributor basis; rendered
// inside each tile's collapsible controls panel.
function AuthorBasisControl({ value, onChange }) {
  return (
    <div className="section-source-toggle" aria-label="Data basis">
      {AUTHOR_BASIS_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`section-source-toggle__button${value === option.value ? ' is-active' : ''}`}
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function AuthorshipSection({
  ecosystem,
  ecosystemBase,
  selectedSourceIds = [],
  sectionSourceView,
  setSectionSourceView,
  showExperimentalFeatures,
  yearData,
  topAuthors,
  authorContributionHistogram,
  bipAuthorCountHistogram,
  topContributors = [],
  contributorContributionHistogram = [],
  contributorsPerProposalHistogram = [],
  contributorCoverage = null,
  collaborationNetwork,
  collaborationMetricsSummary,
  collaborationMetricsRows,
  collaborationClusterSizeDistribution,
  collaborationDegreeDistribution,
  highlightedAuthor,
  setHighlightedAuthor,
  collaborationLayoutMode,
  setCollaborationLayoutMode,
  collaborationMinClusterCollaborations,
  setCollaborationMinClusterCollaborations,
  collaborationAuthorOptions,
  wordCloudFilterText,
  setWordCloudFilterText,
  hasWordCloudFilter,
  filteredWordCloudData,
  wordCloudData,
}) {
  const {
    showTooltip: showMetricTooltip,
    moveTooltip: moveMetricTooltip,
    hideTooltip: hideMetricTooltip,
  } = useAnalysisMetricTooltip();

  // Contributor variants exist only for snapshots whose payload carries the
  // pipeline-computed `contributors` block; without it the basis toggles are
  // hidden and every tile shows declared authorship.
  const hasContributorData = (contributorCoverage?.contributorCount ?? 0) > 0;
  const [topBasis, setTopBasis] = useState('declared');
  const [perPersonBasis, setPerPersonBasis] = useState('declared');
  const [perProposalBasis, setPerProposalBasis] = useState('declared');
  const [perPersonLogScale, setPerPersonLogScale] = useState(false);
  const [perProposalLogScale, setPerProposalLogScale] = useState(false);
  const topIsContributors = hasContributorData && topBasis === 'contributors';
  const perPersonIsContributors = hasContributorData && perPersonBasis === 'contributors';
  const perProposalIsContributors = hasContributorData && perProposalBasis === 'contributors';
  const formatShare = (count, total) => (
    total > 0 ? `${count} (${Math.round((count / total) * 100)}%)` : String(count)
  );
  const contributorCoverageCards = useMemo(() => {
    const coverage = contributorCoverage || {};
    return [
      {
        label: 'Contributors',
        area: 'contributors',
        value: coverage.contributorCount ?? 0,
        description: 'Distinct people (bots excluded) who committed at least one change to any proposal file, according to full git history.',
      },
      {
        label: 'Originators',
        area: 'originators',
        value: coverage.declaredAuthorCount ?? 0,
        description: 'Distinct people declared as originator of at least one proposal (preamble authors, or the initial committer where no preamble exists).',
      },
      {
        label: 'Also Originators',
        area: 'also-originators',
        value: formatShare(coverage.contributorsAlsoDeclared ?? 0, coverage.contributorCount ?? 0),
        description: 'Contributors who are also declared as originator of at least one proposal, as a share of all contributors.',
      },
      {
        label: 'Also Contributors',
        area: 'also-contributors',
        value: formatShare(coverage.contributorsAlsoDeclared ?? 0, coverage.declaredAuthorCount ?? 0),
        description: 'Originators who also appear as git contributors anywhere in the selected proposal corpus, as a share of all originators. These are the same people as in “Also Originators”, relative to the other total.',
      },
      {
        label: (<>Proposals with<br />Non-Originator Edits</>),
        area: 'proposals',
        value: formatShare(coverage.proposalsWithUncredited ?? 0, coverage.proposalsWithGitData ?? 0),
        description: 'Proposals where at least one contributor is not among that proposal’s originators, relative to all proposals with recorded git history.',
      },
    ];
  }, [contributorCoverage]);

  const collaborationMetricCards = useMemo(() => ([
    {
      label: 'Nodes',
      value: collaborationMetricsSummary?.nodeCount ?? 0,
      description: 'Total number of distinct originators, including solo-only originators with no collaboration links.',
    },
    {
      label: 'Edges',
      value: collaborationMetricsSummary?.edgeCount ?? 0,
      description: 'Number of distinct originator pairs that have co-originated at least one proposal together.',
    },
    {
      label: 'Isolated Nodes',
      value: collaborationMetricsSummary?.isolatedAuthorCount ?? 0,
      description: 'Originators with degree 0, meaning they appear in the corpus but never co-originate a proposal with anyone else. For readability, they are shown together in one shared display cluster.',
    },
    {
      label: 'Clusters',
      value: collaborationMetricsSummary?.clusterCount ?? 0,
      description: 'Number of display clusters in the collaboration graph and table. Originators with no collaboration links are grouped into one shared cluster for readability.',
    },
    {
      label: 'Density',
      value: Number(collaborationMetricsSummary?.density || 0).toFixed(4).replace(/\.?0+$/, ''),
      description: 'Share of all possible originator-to-originator links that actually exist. Higher density means collaboration is more broadly interconnected.',
    },
  ]), [collaborationMetricsSummary]);
  return (
    <section className="dashboard-section">
      <div className="dashboard-section__header">
        <h2 className="dashboard-section__title">Authorship Diversity</h2>
        <SectionSourceToggle
          ecosystemBase={ecosystemBase}
          selectedSourceIds={selectedSourceIds}
          value={sectionSourceView}
          onChange={setSectionSourceView}
          supportsMerged
        />
      </div>
      <div className="dashboard-grid dashboard-grid--wide-left">
        <ExportableCard className="mb-4" exportTitle="Creation Over Time">
          <h3>Creation Timeline</h3>
          <p>
            Creation date of proposals according to date provided in preamble.
          </p>
          <ProposalTimelineChart data={yearData} width={800} height={450} />
        </ExportableCard>
        <ExportableCard className="mb-4" exportTitle="Top 10 Authors">
          <h3>Top 10 Authors</h3>
          <p>
            Number of proposals attributed to the ten most active authors, either
            as <strong>originators</strong> or as <strong>(git) contributors</strong>.
          </p>
          {hasContributorData && (
            <CollapsibleControls>
              <AuthorBasisControl value={topBasis} onChange={setTopBasis} />
            </CollapsibleControls>
          )}
          <div>
            <TopAuthorsChart
              data={{ topAuthors: topIsContributors ? topContributors : topAuthors }}
              width={420}
              height={260}
            />
          </div>
        </ExportableCard>
      </div>
      <div className="dashboard-grid dashboard-grid--two-up">
        <ExportableCard className="mb-4" exportTitle="Proposals per Author">
          <h3>Proposals per Author</h3>
          <p>
            Number of authors (originators or contributors) with a given number of
            proposals.
          </p>
          <CollapsibleControls>
            <div className="authorship-tile-controls">
              {hasContributorData && (
                <AuthorBasisControl value={perPersonBasis} onChange={setPerPersonBasis} />
              )}
              <LogScaleToggle
                inputId="proposals-per-author-log-switch"
                value={perPersonLogScale}
                onChange={setPerPersonLogScale}
              />
            </div>
          </CollapsibleControls>
          <div>
            <AuthorContributionHistogram
              data={perPersonIsContributors ? contributorContributionHistogram : authorContributionHistogram}
              width={640}
              height={380}
              logScale={perPersonLogScale}
            />
          </div>
        </ExportableCard>
        <ExportableCard className="mb-4" exportTitle="Authors per Proposal">
          <h3>Authors per Proposal</h3>
          <p>
            Distribution of proposals by their number of authors (originators or
            contributors).
          </p>
          <CollapsibleControls>
            <div className="authorship-tile-controls">
              {hasContributorData && (
                <AuthorBasisControl value={perProposalBasis} onChange={setPerProposalBasis} />
              )}
              <LogScaleToggle
                inputId="authors-per-proposal-log-switch"
                value={perProposalLogScale}
                onChange={setPerProposalLogScale}
              />
            </div>
          </CollapsibleControls>
          <div>
            <BipAuthorCountHistogram
              data={perProposalIsContributors ? contributorsPerProposalHistogram : bipAuthorCountHistogram}
              width={640}
              height={380}
              logScale={perProposalLogScale}
            />
          </div>
        </ExportableCard>
      </div>

      {hasContributorData && (
          <Card className="mb-4">
            <h3>Originators vs. Contributors</h3>
            <p>
              How declared origination compares with actual git activity on the proposal files.
              {' '}<strong>Originators</strong> are the distinct people officially declared as
              authors of a proposal — or, where no authorship is declared, the committers that
              initially created the proposal. <strong>Contributors</strong> are the distinct
              people who ever committed changes to a proposal file according to its full git
              history, with bot accounts removed and known multiple commit identities of the
              same person merged into one. The two groups are matched by name: declared author
              names (with email addresses stripped) are compared against git commit author
              names, using a curated alias list to bridge known cases where the same person
              appears under different names.
            </p>
            <div className="contributor-coverage-grid">
              {contributorCoverageCards.map((metric) => (
                <div
                  key={metric.area}
                  className="metric-badge"
                  style={{ gridArea: metric.area }}
                  onMouseEnter={(event) => showMetricTooltip(event, metric.description)}
                  onMouseMove={moveMetricTooltip}
                  onMouseLeave={hideMetricTooltip}
                >
                  <span className="metric-badge__label">{metric.label}</span>
                  <span className="metric-badge__value">{metric.value}</span>
                </div>
              ))}
            </div>
          </Card>
      )}

      <ExportableCard className="mb-4" exportTitle="Originator Collaboration Graph">
        <h3>Originator Collaboration Graph</h3>
        <p>
          Co-authorship among originators across the selected proposal corpus, shown as a collaboration graph. Larger nodes indicate originators of more proposals, while thicker edges indicate more co-originated proposals. Colors encode connected components, while originators without collaborations are grouped into one shared component.
        </p>
        <div>
          <AuthorCollaborationNetwork
            data={collaborationNetwork}
            width={1200}
            height={700}
            highlightAuthor={highlightedAuthor}
            layoutMode={collaborationLayoutMode}
            setLayoutMode={setCollaborationLayoutMode}
            minClusterCollaborations={collaborationMinClusterCollaborations}
            setMinClusterCollaborations={setCollaborationMinClusterCollaborations}
            extraControls={(
              <div className="network-finder author-collaboration-search">
                <div className="network-finder__copy">
                  <strong>Originator Search</strong>
                </div>
                <div className="network-finder__controls">
                  <InputText
                    value={highlightedAuthor}
                    onChange={(event) => setHighlightedAuthor(event.target.value)}
                    placeholder="Type an originator name"
                    aria-label="Originator search: type a name to highlight in the collaboration graph"
                    list="author-collaboration-options"
                  />
                  <datalist id="author-collaboration-options">
                    {collaborationAuthorOptions.map((author) => (
                      <option key={author} value={author} />
                    ))}
                  </datalist>
                  <Button
                    type="button"
                    label="Clear"
                    severity="secondary"
                    text
                    onClick={() => setHighlightedAuthor('')}
                    disabled={!highlightedAuthor.trim()}
                  />
                </div>
              </div>
            )}
          />
        </div>
      </ExportableCard>
      <Card className="mb-4">
        <h3>Originator Collaboration Metrics</h3>
        <p>
          Co-authorship among originators according to preamble across the selected proposal corpus.
          Originator names marked with <strong><code>*</code></strong> are in the top 10 by originated proposals. <strong>Cluster</strong>
          {' '}and <strong>Cluster Size</strong> show the connected collaboration group an originator belongs to and how large
          that group is. Originators with no collaboration links are grouped into one shared display cluster for readability.{' '}
          <strong>Degree</strong> measures how many different co-originators an originator has.
          <strong>Weighted Degree</strong> captures how often an originator collaborates in total, including repeated collaborations.{' '}
          <strong>Weighted Eigenvector</strong> reflects how strongly an originator is connected to other well-connected originators.{' '}
          <strong>Betweenness</strong> measures how often an originator lies on the shortest paths between other originators, indicating their role in connecting otherwise separate groups.
          Each metric value is annotated with its rank among all originators in the network (e.g. <code>#1</code> = highest).
        </p>
        <div className="collaboration-metrics-summary">
          {collaborationMetricCards.map((metric) => (
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
        <AuthorCentralityTable
          rows={collaborationMetricsRows}
          defaultSortField="weightedEigenvector"
          columns={[
            { field: 'clusterId', header: 'Cluster', format: 'integer' },
            { field: 'clusterSize', header: 'Cluster Size', format: 'integer' },
            { field: 'rawDegree', header: 'Degree', format: 'integer', showRank: true },
            { field: 'weightedDegree', header: 'Weighted Degree', format: 'integer', showRank: true },
            { field: 'weightedEigenvector', header: 'Weighted Eigenvector', digits: 4, showRank: true },
            { field: 'betweenness', header: 'Betweenness', digits: 4, showRank: true },
          ]}
        />
      </Card>
      <div className="dashboard-grid dashboard-grid--two-up">
        <ExportableCard className="mb-4 dashboard-plot-card-shell" exportTitle="Collaboration Component Size Distribution">
          <div className="dashboard-plot-card">
            <div className="dashboard-plot-card__copy">
              <h3>Connected Component Size Distribution</h3>
              <p>
                Connected components in the originator collaboration graph, grouped by size.
              </p>
            </div>
            <div className="dashboard-plot-card__plot">
              <CollaborationClusterSizeDistribution
                data={collaborationClusterSizeDistribution}
                width={640}
                height={410}
              />
            </div>
          </div>
        </ExportableCard>
        <ExportableCard className="mb-4 dashboard-plot-card-shell" exportTitle="Collaboration Degree Distribution">
          <div className="dashboard-plot-card">
            <div className="dashboard-plot-card__copy">
              <h3>Co-Originator Degree Distribution</h3>
              <p>
                Distinct co-originators per originator.
              </p>
            </div>
            <div className="dashboard-plot-card__plot">
              <CollaborationDegreeDistribution
                data={collaborationDegreeDistribution}
                width={640}
                height={410}
              />
            </div>
          </div>
        </ExportableCard>
      </div>
      {showExperimentalFeatures ? (
        <ExportableCard className="mb-4" exportTitle="Word Cloud of Document Text">
          <h3 className="card-title-with-badge">
            Word Cloud of Document Text
            <Tag
              className="dashboard-section__tag card-title-with-badge__tag"
              severity="warning"
              value="Experimental"
            />
          </h3>
          <p>
            Highlighting the most frequent terms across the selected proposal corpus.
          </p>
          <CollapsibleControls>
            <ProposalFilterControl
              value={wordCloudFilterText}
              onChange={setWordCloudFilterText}
              ecosystem={ecosystem}
              aria-label="Filter proposals by ID for word cloud (e.g. BIP32, SLIP44, BIP30-BIP35)"
              layout="split"
              entryLabel="Filter proposals"
              className="wordcloud-filter--chips-right"
              trailingControl={(
                <Button
                  type="button"
                  label="Clear"
                  severity="secondary"
                  text
                  onClick={() => setWordCloudFilterText('')}
                  disabled={!hasWordCloudFilter}
                />
              )}
            />
          </CollapsibleControls>
          <div>
            <WordCloud words={hasWordCloudFilter ? filteredWordCloudData : wordCloudData} width={1250} height={500} />
          </div>
        </ExportableCard>
      ) : null}
    </section>
  );
}
