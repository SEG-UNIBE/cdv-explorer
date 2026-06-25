import { useMemo } from 'react';
import { Button } from 'primereact/button';
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

  const collaborationMetricCards = useMemo(() => ([
    {
      label: 'Nodes',
      value: collaborationMetricsSummary?.nodeCount ?? 0,
      description: 'Total number of distinct authors, including solo-only authors with no co-authorship links.',
    },
    {
      label: 'Edges',
      value: collaborationMetricsSummary?.edgeCount ?? 0,
      description: 'Number of distinct author pairs that have co-authored at least one proposal together.',
    },
    {
      label: 'Isolated Nodes',
      value: collaborationMetricsSummary?.isolatedAuthorCount ?? 0,
      description: 'Authors with degree 0, meaning they appear in the corpus but never co-author a proposal with anyone else. For readability, they are shown together in one shared display cluster.',
    },
    {
      label: 'Clusters',
      value: collaborationMetricsSummary?.clusterCount ?? 0,
      description: 'Number of display clusters in the collaboration graph and table. Authors with no co-authorship links are grouped into one shared cluster for readability.',
    },
    {
      label: 'Density',
      value: Number(collaborationMetricsSummary?.density || 0).toFixed(4).replace(/\.?0+$/, ''),
      description: 'Share of all possible author-to-author links that actually exist. Higher density means collaboration is more broadly interconnected.',
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
          <ProposalTimelineChart data={yearData} width={800} height={380} />
        </ExportableCard>
        <ExportableCard className="mb-4" exportTitle="Top 10 Authors">
          <h3>Top 10 Authors</h3>
          <p>
            Preamble authorship counts for the most mentioned contributors.
          </p>
          <div>
            <TopAuthorsChart data={{ topAuthors }} width={340} height={325} />
          </div>
        </ExportableCard>
      </div>
      <div className="dashboard-grid dashboard-grid--two-up">
        <ExportableCard className="mb-4" exportTitle="Proposals per Author">
          <h3>Proposals per Author</h3>
          <p>
            Number of preamble authors who have written a given number of proposals.
          </p>
          <div>
            <AuthorContributionHistogram data={authorContributionHistogram} width={640} height={380} />
          </div>
        </ExportableCard>
        <ExportableCard className="mb-4" exportTitle="Authors per Proposal">
          <h3>Authors per Proposal</h3>
          <p>
            Distribution of proposals by their preamble author count.
          </p>
          <div>
            <BipAuthorCountHistogram data={bipAuthorCountHistogram} width={640} height={380} />
          </div>
        </ExportableCard>
      </div>

      <ExportableCard className="mb-4" exportTitle="Author Collaboration Graph">
        <h3>Author Collaboration Graph</h3>
        <p>
          Co-authorship across the selected proposal corpus, shown as a collaboration graph. Larger nodes indicate authors of more proposals, while thicker edges indicate more co-authored proposals. Colors encode connected components, while authors without collaborations are grouped into one shared component.
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
                  <strong>Author Search</strong>
                </div>
                <div className="network-finder__controls">
                  <InputText
                    value={highlightedAuthor}
                    onChange={(event) => setHighlightedAuthor(event.target.value)}
                    placeholder="Type an author name"
                    aria-label="Author search: type a name to highlight in the collaboration graph"
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
        <h3>Author Collaboration Metrics</h3>
        <p>
          Co-authorship according to preamble across the selected proposal corpus.
          Author names marked with <strong><code>*</code></strong> are in the top 10 by authored proposals. <strong>Cluster</strong>
          {' '}and <strong>Cluster Size</strong> show the connected co-authorship group an author belongs to and how large
          that group is. Authors with no co-authorship links are grouped into one shared display cluster for readability.{' '} 
          <strong>Degree</strong> measures how many different co-authors an author has. 
          <strong>Weighted Degree</strong> captures how often an author collaborates in total, including repeated collaborations.{' '}
          <strong>Weighted Eigenvector</strong> reflects how strongly an author is connected to other well-connected authors.{' '}
          <strong>Betweenness</strong> measures how often an author lies on the shortest paths between other authors, indicating their role in connecting otherwise separate groups.
          Each metric value is annotated with its rank among all authors in the network (e.g. <code>#1</code> = highest).
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
                Connected components in co-authorship graph, grouped by size.
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
              <h3>Co-Author Degree Distribution</h3>
              <p>
                Distinct co-authors per author.
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
