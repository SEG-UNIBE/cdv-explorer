import { Button } from 'primereact/button';
import { Card } from 'primereact/card';
import { InputText } from 'primereact/inputtext';
import { Tag } from 'primereact/tag';
import { FormalConformitySwarmPlot } from '../../FormalConformitySwarmPlot';
import { ConformityFailedChecksHistogram } from '../../ConformityFailedChecksHistogram';
import { ExportableCard } from '../ExportableCard';

export function ConformitySection({
  ecosystem,
  dependencyProposalOptions,
  highlightedConformityProposal,
  setHighlightedConformityProposal,
  conformityRows,
  conformityFailedChecks,
}) {
  const standards = ecosystem.complianceStandards || [];

  return (
    <section className="dashboard-section">
      <div className="dashboard-section__header">
        <h2 className="dashboard-section__title">
          Formal Conformity
          <Tag
            className="dashboard-section__tag"
            severity="warning"
            value="Experimental"
          />
        </h2>
      </div>
      <Card className="mb-4">
        <h3>Definition</h3>
        <p>
          {ecosystem.conformityDescription || `Formal conformity of ${ecosystem.proposalShortPlural} according to the underlying specification process guidelines. Conformity score (0–100) is computed based on automated checks. For details on failed checks, hover over the bubbles.`}
        </p>
        <div className="network-finder">
          <div className="network-finder__copy">
            <strong>Find proposal:</strong>
          </div>
          <div className="network-finder__controls">
            <InputText
              value={highlightedConformityProposal}
              onChange={(event) => setHighlightedConformityProposal(event.target.value)}
              placeholder="Type a proposal ID"
              aria-label="Find proposal: type an ID to highlight it in the conformity chart"
              list="conformity-proposal-options"
            />
            <datalist id="conformity-proposal-options">
              {dependencyProposalOptions.map((proposalId) => (
                <option key={proposalId} value={proposalId} />
              ))}
            </datalist>
            <Button
              type="button"
              label="Clear"
              severity="secondary"
              text
              onClick={() => setHighlightedConformityProposal('')}
              disabled={!highlightedConformityProposal.trim()}
            />
          </div>
        </div>
      </Card>
      {standards.map((standard) => (
          <div key={standard.key} className="dashboard-grid dashboard-grid--two-up mb-4">
            <ExportableCard
              style={{ flex: 1 }}
              exportTitle={`${standard.label} Swarm Plot`}
            >
              <h3>{standard.label}</h3>
              <p>
                Distribution of proposal-level conformity scores under {standard.label}.
              </p>
              <div>
                <FormalConformitySwarmPlot
                  rows={conformityRows}
                  highlightProposal={highlightedConformityProposal}
                  standardKey={standard.key}
                  width={620}
                  height={420}
                />
              </div>
            </ExportableCard>
            <ExportableCard
              style={{ flex: 1 }}
              exportTitle={`Most Failed ${standard.label} Checks`}
            >
              <h3>Most Failed {standard.label} Checks</h3>
              <p>
                Frequency of failed formal checks under {standard.label} across the selected snapshot.
              </p>
              <div>
                <ConformityFailedChecksHistogram
                  data={conformityFailedChecks[standard.key] || []}
                  proposalShortLabel={ecosystem.acronym || 'IP'}
                  width={620}
                  height={390}
                  {...(standard.color && { barColor: standard.color })}
                  {...(standard.hoverColor && { barHoverColor: standard.hoverColor })}
                  ariaLabel={`Most failed ${standard.label} conformity checks`}
                />
              </div>
            </ExportableCard>
          </div>
      ))}
    </section>
  );
}
