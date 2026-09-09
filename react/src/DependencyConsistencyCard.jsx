import { useEffect, useRef, useState } from 'react';
import { Column } from 'primereact/column';
import { DataTable } from 'primereact/datatable';
import { formatProposalReference, getProposalUrl } from './proposalLinks';
import {
  BODY_EXTRACTED_LLM,
  getDependencyApproachLabel,
} from './dependencyApproaches';
import {
  useDashboardEcosystem,
  useDashboardLinkMode,
  useDashboardSnapshot,
} from './dashboard/DashboardSnapshotContext';
import { ExportableCard } from './dashboard/ExportableCard';
import { useAnalysisMetricTooltip } from './useAnalysisMetricTooltip';

const CYCLIC_GROUPS_EXPLANATION = 'A cyclic group is a strongly connected component (SCC) containing at least two IPs, each reachable from every other through directed edges.';

function ProposalAnchor({ node, ecosystem, snapshot, linkMode }) {
  const graphKey = String(node?.id || '');
  return (
    <a
      href={getProposalUrl(graphKey, snapshot, { linkMode }, ecosystem)}
      target="_blank"
      rel="noreferrer"
      title={node?.title || undefined}
    >
      {formatProposalReference(graphKey, ecosystem)}
    </a>
  );
}

async function writeClipboardText(value) {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // Fall through to the legacy copy path when browser permissions reject the API.
    }
  }

  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  textarea.remove();
}

function MetricLabel({ metric, showTooltip, moveTooltip, hideTooltip }) {
  if (metric !== 'Cyclic groups (SCCs)') return metric;
  return (
    <span className="dependency-consistency-metric-label">
      <span>{metric}</span>
      <span
        className="dependency-consistency-info"
        role="img"
        aria-label={CYCLIC_GROUPS_EXPLANATION}
        title={CYCLIC_GROUPS_EXPLANATION}
        onMouseEnter={(event) => showTooltip(event, CYCLIC_GROUPS_EXPLANATION)}
        onMouseMove={moveTooltip}
        onMouseLeave={hideTooltip}
      >
        <i className="pi pi-info-circle" aria-hidden="true" />
      </span>
    </span>
  );
}

function CopyProposalFilterButton({ nodes, ecosystem }) {
  const [copied, setCopied] = useState(false);
  const resetTimer = useRef(null);
  const value = (nodes || [])
    .map((node) => formatProposalReference(node?.id, ecosystem))
    .filter(Boolean)
    .join(',');

  useEffect(() => () => clearTimeout(resetTimer.current), []);

  const handleCopy = async () => {
    if (!value) return;
    await writeClipboardText(value);
    setCopied(true);
    clearTimeout(resetTimer.current);
    resetTimer.current = setTimeout(() => setCopied(false), 1600);
  };

  return (
    <button
      type="button"
      className="dependency-consistency-copy-button"
      onClick={handleCopy}
      aria-label={`Copy ${value} for proposal filtering`}
      title={copied ? 'Copied' : 'Copy proposal filter'}
    >
      <i className={`pi ${copied ? 'pi-check' : 'pi-copy'}`} aria-hidden="true" />
    </button>
  );
}

function CyclicGroupList({ groups, ecosystem, snapshot, linkMode }) {
  if (!groups?.length) return null;
  return (
    <details className="dependency-consistency-details">
      <summary>Cyclic dependency groups</summary>
      <ul>
        {groups.map((group) => (
          <li key={(group.nodes || []).map((node) => node.id).join('|')}>
            <span>
              {(group.nodes || []).map((node, index) => (
                <span key={node.id}>
                  {index > 0 ? ', ' : ''}
                  <ProposalAnchor node={node} ecosystem={ecosystem} snapshot={snapshot} linkMode={linkMode} />
                </span>
              ))}
            </span>
            <CopyProposalFilterButton nodes={group.nodes} ecosystem={ecosystem} />
          </li>
        ))}
      </ul>
    </details>
  );
}

function OneSidedFactList({ facts, ecosystem, snapshot, linkMode }) {
  if (!facts?.length) return null;
  return (
    <details className="dependency-consistency-details">
      <summary>One-sided supersession declarations</summary>
      <ul>
        {facts.map((fact) => (
          <li key={`${fact.successor?.id}|${fact.predecessor?.id}`}>
            <span>
              <ProposalAnchor node={fact.successor} ecosystem={ecosystem} snapshot={snapshot} linkMode={linkMode} />
              <span aria-hidden="true"> supersedes </span>
              <ProposalAnchor node={fact.predecessor} ecosystem={ecosystem} snapshot={snapshot} linkMode={linkMode} />
            </span>
            <CopyProposalFilterButton
              nodes={[fact.successor, fact.predecessor]}
              ecosystem={ecosystem}
            />
          </li>
        ))}
      </ul>
    </details>
  );
}

function getDashboardTableRows(payload, approachOrder) {
  if (payload?.dashboard_table_rows?.length) return payload.dashboard_table_rows;

  const paperRows = (payload?.table_rows || []).filter(
    (row) => row.group === 'Dependency' || row.group === 'Supersession',
  );
  const structuralRows = Object.fromEntries(
    (payload?.structural_check_rows || []).map((row) => [row.metric, row]),
  );
  const checkRow = (group, metric) => ({
    group,
    metric,
    values: Object.fromEntries(
      approachOrder.map((approachKey) => [
        approachKey,
        String(structuralRows[metric]?.values?.[approachKey] ?? 0),
      ]),
    ),
  });

  return [
    ...paperRows.filter((row) => row.group === 'Dependency'),
    checkRow('Dependency', 'Self-relations'),
    ...paperRows.filter((row) => row.group === 'Supersession'),
    checkRow('Supersession', 'Cyclic groups (SCCs)'),
  ];
}

export function DependencyConsistencyCard({ payload }) {
  const ecosystem = useDashboardEcosystem();
  const snapshot = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const { showTooltip, moveTooltip, hideTooltip } = useAnalysisMetricTooltip();
  const approachOrder = payload?.meta?.approach_order || [];
  const byApproach = payload?.by_approach || {};
  const tableRows = getDashboardTableRows(payload, approachOrder);
  const llmModel = payload?.meta?.llm_model || '';
  const relationGroups = Array.from(new Set(tableRows.map((row) => row.group)));

  if (!approachOrder.length || !tableRows.length) return null;

  return (
    <ExportableCard className="mb-4" exportTitle="Interrelation Consistency">
      <h3>Interrelation Consistency</h3>
      <p>
        This analysis checks the typed Preamble and LLM networks separately for cyclic
        dependencies and incomplete supersession declarations. Dependency cycles are
        strongly connected components (SCCs) containing at least two IPs. Supersession
        declarations are normalized to successor-predecessor relations and are considered
        reciprocal only when both declaration directions occur.
      </p>
      <div className="dependency-consistency-table-grid">
        {relationGroups.map((group) => (
          <section key={group} className="dependency-consistency-table-panel">
            <h4>{group}</h4>
            <div className="dependency-consistency-table-wrap">
              <DataTable
                value={tableRows.filter((row) => row.group === group)}
                dataKey="metric"
                size="small"
                className="dependency-consistency-table"
                tableStyle={{ minWidth: '25rem' }}
              >
                <Column
                  field="metric"
                  header="Measure"
                  body={(row) => (
                    <MetricLabel
                      metric={row.metric}
                      showTooltip={showTooltip}
                      moveTooltip={moveTooltip}
                      hideTooltip={hideTooltip}
                    />
                  )}
                />
                {approachOrder.map((approachKey) => (
                  <Column
                    key={approachKey}
                    field={`values.${approachKey}`}
                    header={getDependencyApproachLabel(
                      approachKey,
                      approachKey === BODY_EXTRACTED_LLM ? llmModel : '',
                    )}
                    body={(row) => row.values?.[approachKey] ?? '—'}
                  />
                ))}
              </DataTable>
            </div>
          </section>
        ))}
      </div>
      <div className="dependency-consistency-case-grid">
        {approachOrder.map((approachKey) => {
          const analysis = byApproach[approachKey];
          if (!analysis) return null;
          return (
            <section key={approachKey} className="dependency-consistency-case-column">
              <h4>{getDependencyApproachLabel(approachKey, approachKey === BODY_EXTRACTED_LLM ? llmModel : '')}</h4>
              <CyclicGroupList
                groups={analysis.dependency?.cyclic_groups}
                ecosystem={ecosystem}
                snapshot={snapshot}
                linkMode={linkMode}
              />
              <OneSidedFactList
                facts={analysis.supersession?.one_sided_facts}
                ecosystem={ecosystem}
                snapshot={snapshot}
                linkMode={linkMode}
              />
            </section>
          );
        })}
      </div>
    </ExportableCard>
  );
}
