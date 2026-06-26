import { CLASSIFICATION_DIMENSIONS } from './constants';
import {
  buildProposalRefKeySet,
  nodeRefKey,
  normalizeProposalFilterValue,
  parseProposalFilterExpression,
} from './data/proposalFilters';
import { buildWordCloudData } from './data/wordCloudData';
import {
  buildClassificationChordData,
  buildClassificationRelationRows,
  buildFacetDistribution,
  buildFacetTimeline,
} from './data/classificationData';
import { buildAuthorshipDashboardData } from './data/authorshipData';
import { buildConformityDashboardData } from './data/conformityData';

export {
  buildProposalRefKeySet,
  nodeRefKey,
  normalizeProposalFilterValue,
  parseProposalFilterExpression,
  buildWordCloudData,
};

export function buildDashboardData(dataset, ecosystem = {}) {
  const dimensions = ecosystem.classificationDimensions || CLASSIFICATION_DIMENSIONS;
  const complianceStandards = ecosystem.complianceStandards || [{ key: 'bip2' }, { key: 'bip3' }];
  const authorship = dataset.authorship || {};
  const dependencyMetrics = dataset.dependencyMetrics || { by_approach: {} };
  const conformity = dataset.conformity || {};

  const classificationDistributions = Object.fromEntries(
    dimensions.map(({ field }) => [field, buildFacetDistribution(dataset.nodes, field)])
  );
  const classificationTimeline = Object.fromEntries(
    dimensions.map(({ field }) => [field, buildFacetTimeline(dataset.nodes, field)])
  );
  const classificationCategoryDomains = Object.fromEntries(
    dimensions.map(({ field }) => [
      field,
      [
        ...classificationDistributions[field].map((entry) => entry.id),
        ...classificationTimeline[field].categories.filter(
          (category) => !classificationDistributions[field].some((entry) => entry.id === category)
        ),
      ],
    ])
  );
  const classificationRelationRows = buildClassificationRelationRows(dataset.nodes, dimensions);
  const evolutionPayload = dataset.evolution || { meta: {}, status_evolution: { categories: [], rows: [] } };

  return {
    ...buildAuthorshipDashboardData(dataset, authorship),
    wordCloudData: buildWordCloudData(dataset.nodes),
    ...buildConformityDashboardData(dataset, conformity, complianceStandards),
    classificationDistributions,
    classificationTimeline,
    classificationCategoryDomains,
    classificationChordData: buildClassificationChordData(dataset.nodes, classificationCategoryDomains, dimensions),
    classificationRelationRows,
    evolutionPayload,
    dependencyMetrics,
  };
}
