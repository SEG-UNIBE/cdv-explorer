import { collectProposalRefs, proposalRefKey } from './proposalRefs';

export function buildConformityDashboardData(dataset, conformity = {}, complianceStandards = []) {
  const conformityRows = (conformity.per_proposal || [])
    .filter((entry) => entry?.id != null)
    .map((entry) => ({
      ...entry,
      id: String(entry.id),
    }))
    .sort((left, right) => {
      const lNum = Number(left.id);
      const rNum = Number(right.id);
      if (Number.isFinite(lNum) && Number.isFinite(rNum)) return lNum - rNum;
      return left.id.localeCompare(right.id);
    });

  const datasetSource = Array.isArray(dataset.sourceIds) && dataset.sourceIds.length > 0
    ? dataset.sourceIds[0]
    : '';
  const buildFailedChecksSeries = (standardKey) => {
    const failuresByCheck = new Map();

    conformityRows.forEach((entry) => {
      const complianceDetails = entry?.formal_compliance || {};
      const checks = Array.isArray(complianceDetails?.[standardKey]?.checks)
        ? complianceDetails[standardKey].checks
        : [];

      const ref = { source: datasetSource, id: String(entry.id) };
      const refKey = proposalRefKey(ref);

      checks
        .filter((check) => check?.passed === false)
        .forEach((check) => {
          const id = String(check?.id || check?.label || 'unknown-check');
          const label = String(check?.label || check?.id || 'Unnamed check').trim();

          if (!failuresByCheck.has(id)) {
            failuresByCheck.set(id, {
              id,
              label,
              count: 0,
              proposals: new Map(),
            });
          }

          const current = failuresByCheck.get(id);
          current.count += 1;
          current.proposals.set(refKey, ref);
        });
    });

    return Array.from(failuresByCheck.values())
      .map((entry) => ({
        ...entry,
        proposals: collectProposalRefs(entry.proposals),
      }))
      .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
      .slice(0, 10);
  };

  return {
    conformityRows,
    conformityFailedChecks: Object.fromEntries(
      complianceStandards.map(({ key }) => [key, buildFailedChecksSeries(key)])
    ),
  };
}
