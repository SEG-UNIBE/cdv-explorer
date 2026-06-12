import { useEffect, useMemo, useState } from 'react';
import { Dropdown } from 'primereact/dropdown';
import { RadioButton } from 'primereact/radiobutton';
import { EvolutionStatusStackedBarChart } from '../../EvolutionStatusStackedBarChart';
import { ProposalEventTimeline } from '../../ProposalEventTimeline';
import { ExportableCard } from '../ExportableCard';
import { CollapsibleControls } from '../CollapsibleControls';
import { SectionSourceToggle } from './SectionSourceToggle';

function hasPositiveValues(series) {
  return Array.isArray(series?.rows) && series.rows.some((row) => (
    Object.values(row?.values || {}).some((value) => Number(value) > 0)
  ));
}

function EvolutionContent({ ecosystem, evolutionPayload }) {
  const [chartMode, setChartMode] = useState('absolute');
  const [selectedProposalId, setSelectedProposalId] = useState('');
  const overallEvolution = evolutionPayload?.status_evolution_segmented
    || evolutionPayload?.status_evolution
    || { categories: [], rows: [] };
  const proposalTimelines = useMemo(() => (
    Array.isArray(evolutionPayload?.proposal_timelines) ? evolutionPayload.proposal_timelines : []
  ), [evolutionPayload]);
  const milestoneLabel = evolutionPayload?.meta?.milestones?.[0]?.label || '';
  const milestoneDate = evolutionPayload?.meta?.milestones?.[0]?.date || '';
  const formattedMilestoneLabel = milestoneLabel === 'BIP3 Activation'
    ? 'BIP-3 activation'
    : (milestoneLabel || 'the process change');
  const hasData = hasPositiveValues(overallEvolution);
  const proposalTimelineOptions = useMemo(() => proposalTimelines.map((entry) => {
    const eventCount = Number(entry?.event_count ?? entry?.events?.length ?? 0);
    const baseLabel = entry?.title
      ? `${ecosystem.acronym} ${entry.proposal_id} - ${entry.title}`
      : `${ecosystem.acronym} ${entry?.proposal_id || ''}`;

    return {
      label: `${baseLabel} - [${eventCount} Events]`,
      value: entry?.proposal_id || '',
    };
  }), [ecosystem.acronym, proposalTimelines]);
  const selectedProposalTimeline = useMemo(() => (
    proposalTimelines.find((entry) => entry?.proposal_id === selectedProposalId) || null
  ), [proposalTimelines, selectedProposalId]);

  useEffect(() => {
    setSelectedProposalId((current) => (
      proposalTimelines.some((entry) => entry?.proposal_id === current)
        ? current
        : (proposalTimelines[0]?.proposal_id || '')
    ));
  }, [proposalTimelines]);

  if (!hasData) {
    return null;
  }

  return (
    <>
      <ExportableCard className="mb-4" exportTitle={`${ecosystem.acronym} Status Evolution`}>
        <h3>{ecosystem.acronym} Status Evolution</h3>
        <p>
          Stacked status counts reconstructed from proposal git history using commit dates.
          Each bar assigns a {ecosystem.acronym} to the status it had at the end of that quarter, not the status it held for the largest share of days within that quarter. {milestoneDate
            ? `If the selected snapshot extends beyond ${milestoneDate}, the chart also marks ${formattedMilestoneLabel} with a separate breakpoint inside that quarter.`
            : ''}
        </p>
        <CollapsibleControls>
          <div className="network-layout-controls">
            <div className="network-layout-picker">
              <div className="network-layout-picker__label">Mode</div>
              <div className="network-layout-picker__options">
                {[
                  { label: 'Absolute', value: 'absolute' },
                  { label: 'Relative', value: 'relative' },
                ].map((option) => (
                  <label key={option.value} className="network-layout-picker__option">
                    <RadioButton
                      inputId={`evolution-mode-${ecosystem.sourceId || 'default'}-${option.value}`}
                      name={`evolution-mode-${ecosystem.sourceId || 'default'}`}
                      value={option.value}
                      onChange={(event) => setChartMode(event.value)}
                      checked={chartMode === option.value}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </CollapsibleControls>
        <div>
          <EvolutionStatusStackedBarChart
            data={overallEvolution}
            title={`${ecosystem.acronym} Status Evolution`}
            mode={chartMode}
            width={600}
            height={500}
          />
        </div>
      </ExportableCard>
      {proposalTimelines.length ? (
        <ExportableCard className="mb-4" exportTitle={`${ecosystem.acronym} Event Timeline`}>
          <h3>{ecosystem.acronym} Status Changes Timeline</h3>
          <p>
            Visualizes the status changes of a specific {ecosystem.acronym}. Timeline markers open the historic repository version for the corresponding git commit.
          </p>
          <CollapsibleControls>
            <div className="dependency-metrics-toolbar">
              <div className="dependency-metrics-toolbar__copy">
                <strong>Select proposal.</strong>
                <span>Choose a {ecosystem.acronym} to inspect its event-level history.</span>
              </div>
              <Dropdown
                value={selectedProposalId}
                options={proposalTimelineOptions}
                onChange={(event) => setSelectedProposalId(event.value)}
                placeholder={`Select ${ecosystem.acronym}`}
                aria-label={`Select ${ecosystem.acronym} to inspect its event history`}
                filter
                className="dependency-metrics-toolbar__dropdown"
              />
            </div>
          </CollapsibleControls>
          <ProposalEventTimeline
            timeline={selectedProposalTimeline}
            proposalShortLabel={ecosystem.acronym}
            milestoneDate={milestoneDate}
            milestoneLabel={milestoneLabel}
          />
        </ExportableCard>
      ) : null}
    </>
  );
}

export function EvolutionSection({
  ecosystem,
  ecosystemBase,
  selectedSourceIds = [],
  perSourceDashboardData = {},
  sectionSourceView,
  setSectionSourceView,
  evolutionPayload,
}) {
  const isMultiSource = selectedSourceIds.length > 1;
  const activeSourceId = isMultiSource && selectedSourceIds.includes(sectionSourceView)
    ? sectionSourceView
    : selectedSourceIds[0];
  const activeSource = ecosystemBase?.sources?.[activeSourceId];
  const activeData = isMultiSource ? perSourceDashboardData?.[activeSourceId] : null;
  const activeEcosystem = isMultiSource && activeSource
    ? { ...ecosystemBase, ...activeSource }
    : ecosystem;

  if (!isMultiSource) {
    const overall = evolutionPayload?.status_evolution_segmented || evolutionPayload?.status_evolution;
    if (!hasPositiveValues(overall)) return null;
    return (
      <section className="dashboard-section">
        <div className="dashboard-section__header">
          <h2 className="dashboard-section__title">Evolution</h2>
        </div>
        <EvolutionContent ecosystem={ecosystem} evolutionPayload={evolutionPayload} />
      </section>
    );
  }

  return (
    <section className="dashboard-section">
      <div className="dashboard-section__header">
        <h2 className="dashboard-section__title">Evolution</h2>
        <SectionSourceToggle
          ecosystemBase={ecosystemBase}
          selectedSourceIds={selectedSourceIds}
          value={activeSourceId}
          onChange={setSectionSourceView}
          supportsMerged={false}
        />
      </div>
      {activeData && (
        <EvolutionContent
          ecosystem={activeEcosystem}
          evolutionPayload={activeData.evolutionPayload}
        />
      )}
    </section>
  );
}
