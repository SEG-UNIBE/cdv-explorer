jest.mock('d3', () => ({}));

import { fireEvent, render, screen } from '@testing-library/react';
import {
  BODY_EXTRACTED_LLM,
  BODY_EXTRACTED_REGEX,
  DEFAULT_DEPENDENCY_APPROACH,
  GROUND_TRUTH_CURATED,
  LINK_TYPE_OPTIONS,
  PREAMBLE_EXTRACTED,
  normalizeDependencyLinks,
} from './dependencyApproaches';
import { getBipCommitUrl, getBipUrl } from './bipLinks';
import { getClassificationColorMap } from './classificationColors';
import { getNipCommitUrl, getNipUrl } from './nipLinks';
import { getSlipCommitUrl, getSlipUrl, normalizeSlipId } from './slipLinks';
import { getRepositoryCommitUrl, getRepositoryProposalUrl } from './proposalLinkResolver';
import { renderProposalListHtml } from './bipTooltipContent';
import {
  buildDefaultTypeMapping,
  buildGroundTruthEvaluation,
  GROUND_TRUTH_CUTOFF_MODE_ON_OR_BEFORE,
  GROUND_TRUTH_MATCH_MODE_EXACT_TYPE,
  GT_TYPE_ALL,
} from './dependencyGroundTruthEvaluation';
import { resolveRelationOntology } from './dependencyRelationOntology';
import { buildDashboardData, buildWordCloudData, parseProposalFilterExpression } from './dashboard/dashboardData';
import {
  buildProposalGraphId,
  fetchDatasetForSelection,
  getSourceCombinationKey,
  scopeDependencyLinksForSource,
} from './data';
import { filterCrossSourceAuthorNetwork } from './authorNetwork/authorNetworkUtils';
import { filterCrossSourceDependencyGraph } from './networkDiagram/networkDiagramUtils';
import {
  getDefaultExperimentalFeaturesEnabled,
  getEnvironmentBadge,
  getRuntimeEnvironment,
} from './runtimeEnvironment';
import {
  buildClassificationRelationProposalLabel,
  buildClassificationRelationProposalUrl,
} from './ClassificationRelationTable';
import { ProposalFilterControl } from './ProposalFilterControl';
import proposalLinkIndex from './generated/proposalLinkIndex.json';
import bitcoinEcosystem from './ecosystems/bitcoin';
import nostrEcosystem from './ecosystems/nostr';

test('dependency link options default to the canonical preamble approach', () => {
  expect(DEFAULT_DEPENDENCY_APPROACH).toBe(PREAMBLE_EXTRACTED);
  expect(LINK_TYPE_OPTIONS.map((option) => option.value)).toEqual([
    PREAMBLE_EXTRACTED,
    BODY_EXTRACTED_REGEX,
    BODY_EXTRACTED_LLM,
    GROUND_TRUTH_CURATED,
  ]);
});

test('normalizes canonical dependency edges into grouped dependency links', () => {
  const normalized = normalizeDependencyLinks({
    dependency_edges: [
      {
        source: 'bips:1',
        target: 'bips:2',
        extraction_method: PREAMBLE_EXTRACTED,
        relation_type: 'requires',
        value: 1,
      },
      {
        source: 'bips:2',
        target: 'bips:3',
        extraction_method: BODY_EXTRACTED_REGEX,
        relation_type: 'reference',
        value: 1,
      },
      {
        source: 'bips:3',
        target: 'bips:4',
        extraction_method: PREAMBLE_EXTRACTED,
        relation_type: 'depends_on',
        value: 1,
      },
      {
        source: 'bips:4',
        target: 'slips:44',
        extraction_method: GROUND_TRUTH_CURATED,
        relation_type: 'supersedes',
        confidence: 'high',
        evidence: 'Curated evidence',
        reviewer: 'rbo',
        reviewed_at: '2026-06-22',
        value: 1,
      },
    ],
  });

  expect(normalized[PREAMBLE_EXTRACTED].requires).toEqual([
    {
      source: 'bips:1',
      target: 'bips:2',
      extraction_method: PREAMBLE_EXTRACTED,
      relation_type: 'requires',
      value: 1,
    },
  ]);
  expect(normalized[BODY_EXTRACTED_REGEX][0]).toMatchObject({
    source: 'bips:2',
    target: 'bips:3',
    relation_type: 'reference',
  });
  expect(normalized[PREAMBLE_EXTRACTED].depends_on).toEqual([
    {
      source: 'bips:3',
      target: 'bips:4',
      extraction_method: PREAMBLE_EXTRACTED,
      relation_type: 'depends_on',
      value: 1,
    },
  ]);
  expect(normalized[GROUND_TRUTH_CURATED]).toEqual([
    {
      source: 'bips:4',
      target: 'slips:44',
      extraction_method: GROUND_TRUTH_CURATED,
      relation_type: 'supersedes',
      confidence: 'high',
      evidence: 'Curated evidence',
      reviewer: 'rbo',
      reviewed_at: '2026-06-22',
      value: 1,
    },
  ]);
});

test('does not synthesize legacy top-level preamble relation arrays', () => {
  const canonical = normalizeDependencyLinks({
    [PREAMBLE_EXTRACTED]: {
      depends_on: [{ source: 'xips:1', target: 'xips:7', value: 1 }],
    },
    requires: [{ source: 'xips:1', target: 'xips:99', value: 1 }],
  });

  expect(canonical[PREAMBLE_EXTRACTED]).toEqual({
    depends_on: [{ source: 'xips:1', target: 'xips:7', value: 1 }],
  });
  expect(canonical.requires).toBeUndefined();
});

test('source-scopes dependency links without changing display proposal ids', () => {
  const bipLinks = scopeDependencyLinksForSource({
    [BODY_EXTRACTED_REGEX]: [{ source: '32', target: '44', value: 1 }],
  }, 'bip', 'bips');
  const slipLinks = scopeDependencyLinksForSource({
    [BODY_EXTRACTED_REGEX]: [{ source: '32', target: '44', value: 1 }],
  }, 'slip', 'slips');

  expect(buildProposalGraphId('bips', '32')).toBe('bips:32');
  expect(buildProposalGraphId('slips', '32')).toBe('slips:32');
  expect(bipLinks[BODY_EXTRACTED_REGEX][0]).toMatchObject({
    source: '32',
    target: '44',
    sourceProposalId: '32',
    targetProposalId: '44',
    sourceSourceId: 'bip',
    targetSourceId: 'bip',
    sourceGraphSource: 'bips',
    targetGraphSource: 'bips',
    sourceKey: 'bips:32',
    targetKey: 'bips:44',
  });
  expect(bipLinks.requires).toBeUndefined();
  expect(slipLinks[BODY_EXTRACTED_REGEX][0]).toMatchObject({
    source: '32',
    target: '44',
    sourceSourceId: 'slip',
    targetSourceId: 'slip',
    sourceGraphSource: 'slips',
    targetGraphSource: 'slips',
    sourceKey: 'slips:32',
    targetKey: 'slips:44',
  });
  expect(slipLinks.requires).toBeUndefined();
});

test('builds stable combined source artifact keys', () => {
  const entries = [
    ['slip', { sourceSlug: 'slips' }],
    ['bip', { sourceSlug: 'bips' }],
  ];

  expect(getSourceCombinationKey(entries)).toBe('bips+slips');
  expect(getSourceCombinationKey(entries.slice().reverse())).toBe('bips+slips');
  expect(getSourceCombinationKey([entries[0]])).toBeNull();
});

test('multi-source fetch uses combined dependency metrics when combined artifacts exist', async () => {
  const metricPayload = (label, edgeCount) => ({
    by_approach: {
      [BODY_EXTRACTED_REGEX]: {
        summary: { edge_count: edgeCount },
        per_bip: [{ id: label, out_degree: edgeCount }],
      },
    },
    pairwise_comparisons: { label },
  });
  const networkPayload = (url) => {
    if (url.includes('/_combined/bips+slips/')) {
      return {
        nodes: [
          { id: '1', graph_key: 'bips:1' },
          { id: '32', graph_key: 'slips:32' },
        ],
        dependency_edges: [
          {
            source: 'bips:1',
            target: 'slips:32',
            extraction_method: BODY_EXTRACTED_REGEX,
            relation_type: 'reference',
            value: 1,
          },
        ],
      };
    }
    return { nodes: [{ id: '1' }], dependency_edges: [] };
  };
  const payloadForUrl = (url) => {
    if (url.endsWith('/dependencies/network_data.json')) return networkPayload(url);
    if (url.endsWith('/dependencies/dependency_metrics.json')) {
      if (url.includes('/_combined/bips+slips/')) return metricPayload('combined', 99);
      if (url.includes('/bips/')) return metricPayload('bips', 1);
      return metricPayload('slips', 2);
    }
    if (url.endsWith('/authorship/authorship_payload.json')) return {};
    if (url.endsWith('/classification/classification_payload.json')) return {};
    if (url.endsWith('/evolution/evolution_payload.json')) return {};
    if (url.endsWith('/conformity/conformity_metrics.json')) return {};
    throw new Error(`Unexpected fetch URL: ${url}`);
  };
  const previousFetch = global.fetch;
  global.fetch = jest.fn((url) => Promise.resolve({
    ok: true,
    json: () => Promise.resolve(payloadForUrl(url)),
  }));

  try {
    const dataset = await fetchDatasetForSelection('bitcoin', '2026-03-16', ['bip', 'slip']);

    expect(dataset.isMergedSelection).toBe(true);
    expect(dataset.combinationKey).toBe('bips+slips');
    expect(dataset.dependencyMetrics.by_approach[BODY_EXTRACTED_REGEX].summary.edge_count).toBe(99);
    expect(dataset.bySource.bip.dependencyMetrics.by_approach[BODY_EXTRACTED_REGEX].summary.edge_count).toBe(1);
    expect(dataset.bySource.slip.dependencyMetrics.by_approach[BODY_EXTRACTED_REGEX].summary.edge_count).toBe(2);
    expect(dataset.links[BODY_EXTRACTED_REGEX][0]).toMatchObject({
      sourceKey: 'bips:1',
      targetKey: 'slips:32',
      sourceSourceId: 'bip',
      targetSourceId: 'slip',
    });
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/_combined/bips+slips/03_analysis/2026-03-16/dependencies/dependency_metrics.json'));
  } finally {
    global.fetch = previousFetch;
  }
});

test('ground-truth evaluation scores directed edge recovery on curated source proposals', () => {
  const evaluation = buildGroundTruthEvaluation({
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
        { sourceKey: 'bips:1', targetKey: 'bips:3', relation_type: 'depends_on' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
        { sourceKey: 'bips:1', targetKey: 'bips:9', relation_type: 'reference' },
        { sourceKey: 'bips:5', targetKey: 'bips:6', relation_type: 'reference' },
      ],
      [BODY_EXTRACTED_LLM]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
        { sourceKey: 'bips:1', targetKey: 'bips:3', relation_type: 'depends_on' },
      ],
      [PREAMBLE_EXTRACTED]: {
        requires: [
          { sourceKey: 'bips:1', targetKey: 'bips:3', relation_type: 'requires' },
        ],
      },
    },
  });

  expect(evaluation.reviewedProposalCount).toBe(1);
  expect(evaluation.goldEdgeCount).toBe(2);
  expect(evaluation.approaches).toEqual([
    expect.objectContaining({
      approach: PREAMBLE_EXTRACTED,
      tp: 1,
      fp: 0,
      fn: 1,
      precision: 1,
      recall: 0.5,
    }),
    expect.objectContaining({
      approach: BODY_EXTRACTED_REGEX,
      tp: 1,
      fp: 1,
      fn: 1,
      precision: 0.5,
      recall: 0.5,
      f1: 0.5,
    }),
    expect.objectContaining({
      approach: BODY_EXTRACTED_LLM,
      tp: 2,
      fp: 0,
      fn: 0,
      precision: 1,
      recall: 1,
      f1: 1,
    }),
  ]);
});

test('ground-truth evaluation can require exact relation-type matches', () => {
  const evaluation = buildGroundTruthEvaluation({
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
      ],
      [BODY_EXTRACTED_LLM]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
      ],
      [PREAMBLE_EXTRACTED]: {
        requires: [
          { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'requires' },
        ],
      },
    },
  }, { matchMode: GROUND_TRUTH_MATCH_MODE_EXACT_TYPE });

  expect(evaluation.approaches).toEqual([
    // Preamble `requires` maps to GT `depends_on` by default, so it matches.
    expect.objectContaining({
      approach: PREAMBLE_EXTRACTED,
      evaluated: true,
      tp: 1,
      fp: 0,
      fn: 0,
    }),
    // Regex and LLM have no included subtype by default: not scored in Exact Type.
    expect.objectContaining({
      approach: BODY_EXTRACTED_REGEX,
      evaluated: false,
      tp: 0,
      fp: 0,
      fn: 0,
    }),
    expect.objectContaining({
      approach: BODY_EXTRACTED_LLM,
      evaluated: false,
      tp: 0,
      fp: 0,
      fn: 0,
    }),
  ]);
});

test('default type mapping is discovered from data and prefilled from the ontology', () => {
  const dataset = {
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
      { ip: 'bips:3', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
        { sourceKey: 'bips:3', targetKey: 'bips:4', relation_type: 'supersedes' },
        { sourceKey: 'bips:5', targetKey: 'bips:6', relation_type: 'superseded_by' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
      ],
      [BODY_EXTRACTED_LLM]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'implicit_dependency' },
      ],
      [PREAMBLE_EXTRACTED]: {
        requires: [{ sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'requires' }],
        replaces: [{ sourceKey: 'bips:3', targetKey: 'bips:4', relation_type: 'replaces' }],
        proposed_replacement: [{ sourceKey: 'bips:5', targetKey: 'bips:6', relation_type: 'proposed_replacement' }],
      },
    },
  };

  const mapping = buildDefaultTypeMapping(dataset, resolveRelationOntology('bitcoin'));
  expect(mapping.gtTypes).toEqual(['depends_on', 'supersedes', 'superseded_by']);
  expect(mapping.rows).toEqual([
    { approach: PREAMBLE_EXTRACTED, subtype: 'requires', include: true, target: 'depends_on' },
    { approach: PREAMBLE_EXTRACTED, subtype: 'replaces', include: true, target: 'supersedes' },
    { approach: PREAMBLE_EXTRACTED, subtype: 'proposed_replacement', include: true, target: 'superseded_by' },
    { approach: BODY_EXTRACTED_REGEX, subtype: 'reference', include: false, target: null },
    { approach: BODY_EXTRACTED_LLM, subtype: 'implicit_dependency', include: false, target: null },
  ]);
});

test('default type mapping keeps a placeholder row for approaches with no extracted relations', () => {
  const dataset = {
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
      ],
      // No PREAMBLE_EXTRACTED and no BODY_EXTRACTED_LLM edges in this dataset.
    },
  };

  const mapping = buildDefaultTypeMapping(dataset, resolveRelationOntology('bitcoin'));
  const preambleRow = mapping.rows.find((row) => row.approach === PREAMBLE_EXTRACTED);
  const llmRow = mapping.rows.find((row) => row.approach === BODY_EXTRACTED_LLM);
  expect(preambleRow).toEqual({ approach: PREAMBLE_EXTRACTED, subtype: null, include: false, target: null, empty: true });
  expect(llmRow).toEqual({ approach: BODY_EXTRACTED_LLM, subtype: null, include: false, target: null, empty: true });
});

test('default type mapping does not auto-map a subtype when the GT slice lacks its canonical class', () => {
  const dataset = {
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
      ],
      [PREAMBLE_EXTRACTED]: {
        replaces: [{ sourceKey: 'bips:3', targetKey: 'bips:4', relation_type: 'replaces' }],
      },
    },
  };

  const mapping = buildDefaultTypeMapping(dataset, resolveRelationOntology('bitcoin'));
  expect(mapping.rows).toEqual([
    { approach: PREAMBLE_EXTRACTED, subtype: 'replaces', include: false, target: null },
    { approach: BODY_EXTRACTED_REGEX, subtype: null, include: false, target: null, empty: true },
    { approach: BODY_EXTRACTED_LLM, subtype: null, include: false, target: null, empty: true },
  ]);
});

test('mapping a subtype to "(all)" matches any gold type without inflating false positives', () => {
  const dataset = {
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
      { ip: 'bips:3', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
        { sourceKey: 'bips:3', targetKey: 'bips:4', relation_type: 'supersedes' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        // matches the depends_on gold pair (any type)
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
        // matches the supersedes gold pair (any type)
        { sourceKey: 'bips:3', targetKey: 'bips:4', relation_type: 'reference' },
        // not in the gold set at all -> exactly one false positive
        { sourceKey: 'bips:1', targetKey: 'bips:9', relation_type: 'reference' },
      ],
    },
  };

  const typeMapping = {
    gtTypes: ['depends_on', 'supersedes'],
    rows: [
      { approach: BODY_EXTRACTED_REGEX, subtype: 'reference', include: true, target: GT_TYPE_ALL },
    ],
  };
  const evaluation = buildGroundTruthEvaluation(dataset, {
    matchMode: GROUND_TRUTH_MATCH_MODE_EXACT_TYPE,
    typeMapping,
  });
  const regex = evaluation.approaches.find((approach) => approach.approach === BODY_EXTRACTED_REGEX);
  // 2 gold pairs matched regardless of type, 1 unmatched edge -> single FP (not one per gold type).
  expect(regex).toEqual(expect.objectContaining({ evaluated: true, tp: 2, fp: 1, fn: 0 }));
});

test('non-restricted scope scores edges from proposals without curated ground truth', () => {
  const dataset = {
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
        // bips:7 has no curated GT outgoing link.
        { sourceKey: 'bips:7', targetKey: 'bips:8', relation_type: 'reference' },
      ],
    },
  };

  const restricted = buildGroundTruthEvaluation(dataset, { restrictToReviewedSources: true });
  const restrictedRegex = restricted.approaches.find((approach) => approach.approach === BODY_EXTRACTED_REGEX);
  // Edge from the non-curated source bips:7 is ignored.
  expect(restrictedRegex).toEqual(expect.objectContaining({ tp: 1, fp: 0, fn: 0 }));

  const open = buildGroundTruthEvaluation(dataset, { restrictToReviewedSources: false });
  const openRegex = open.approaches.find((approach) => approach.approach === BODY_EXTRACTED_REGEX);
  // Now the bips:7 edge is scored and, absent from the gold set, counts as a false positive.
  expect(openRegex).toEqual(expect.objectContaining({ tp: 1, fp: 1, fn: 0 }));
});

test('reviewed IP scope includes reviewed proposals with zero curated edges', () => {
  const dataset = {
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
      { ip: 'bips:7', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
        { sourceKey: 'bips:7', targetKey: 'bips:8', relation_type: 'reference' },
      ],
    },
  };

  const evaluation = buildGroundTruthEvaluation(dataset, { restrictToReviewedSources: true });
  const regex = evaluation.approaches.find((approach) => approach.approach === BODY_EXTRACTED_REGEX);

  expect(evaluation.reviewedProposalCount).toBe(2);
  expect(regex).toEqual(expect.objectContaining({ tp: 1, fp: 1, fn: 0 }));
});

test('ground-truth evaluation can filter curated edges by review-date cutoff', () => {
  const dataset = {
    nodes: [{ id: '1' }, { id: '2' }, { id: '3' }],
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-20' },
      { ip: 'bips:2', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on', reviewed_at: '2026-06-20' },
        { sourceKey: 'bips:1', targetKey: 'bips:3', relation_type: 'depends_on', reviewed_at: '2026-06-22' },
        { sourceKey: 'bips:2', targetKey: 'bips:3', relation_type: 'depends_on' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
        { sourceKey: 'bips:1', targetKey: 'bips:3', relation_type: 'reference' },
      ],
    },
  };

  const evaluation = buildGroundTruthEvaluation(dataset, {
    gtCutoffMode: GROUND_TRUTH_CUTOFF_MODE_ON_OR_BEFORE,
    gtCutoffDate: '2026-06-21',
  });
  const regex = evaluation.approaches.find((approach) => approach.approach === BODY_EXTRACTED_REGEX);

  expect(evaluation.goldEdgeCount).toBe(1);
  expect(evaluation.reviewedProposalCount).toBe(1);
  expect(regex).toEqual(expect.objectContaining({ tp: 1, fp: 1, fn: 0 }));
});

test('runtime environment detection distinguishes local dev and prod hosts', () => {
  expect(getRuntimeEnvironment('localhost')).toBe('local');
  expect(getRuntimeEnvironment('127.0.0.1')).toBe('local');
  expect(getRuntimeEnvironment('cdv-explorer.pages.dev')).toBe('dev');
  expect(getRuntimeEnvironment('seg-unibe.github.io')).toBe('prod');
});

test('environment badge is shown only for local and pages dev hosts', () => {
  expect(getEnvironmentBadge('localhost')).toBe('LOCAL');
  expect(getEnvironmentBadge('preview.pages.dev')).toBe('DEV');
  expect(getEnvironmentBadge('seg-unibe.github.io')).toBeNull();
});

test('experimental features default to enabled outside production only', () => {
  expect(getDefaultExperimentalFeaturesEnabled('localhost')).toBe(true);
  expect(getDefaultExperimentalFeaturesEnabled('preview.pages.dev')).toBe(true);
  expect(getDefaultExperimentalFeaturesEnabled('seg-unibe.github.io')).toBe(false);
});

test('ground-truth evaluation returns null when a cutoff excludes the reviewed benchmark scope', () => {
  const dataset = {
    nodes: [{ id: '1' }, { id: '2' }],
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on', reviewed_at: '2026-06-22' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
      ],
    },
  };

  const evaluation = buildGroundTruthEvaluation(dataset, {
    gtCutoffMode: GROUND_TRUTH_CUTOFF_MODE_ON_OR_BEFORE,
    gtCutoffDate: '2026-06-21',
  });

  expect(evaluation).toBeNull();
});

test('an approach is only scored against the gold types it is mapped to', () => {
  const dataset = {
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
      { ip: 'bips:3', reviewed_at: '2026-06-22' },
      { ip: 'bips:5', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
        { sourceKey: 'bips:3', targetKey: 'bips:4', relation_type: 'supersedes' },
        { sourceKey: 'bips:5', targetKey: 'bips:6', relation_type: 'references' },
      ],
      [BODY_EXTRACTED_REGEX]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'reference' },
      ],
    },
  };

  // Map Regex only to depends_on -> supersedes/references gold edges are out of scope.
  const typeMapping = {
    gtTypes: ['depends_on', 'supersedes', 'references'],
    rows: [
      { approach: BODY_EXTRACTED_REGEX, subtype: 'reference', include: true, target: 'depends_on' },
    ],
  };
  const evaluation = buildGroundTruthEvaluation(dataset, {
    matchMode: GROUND_TRUTH_MATCH_MODE_EXACT_TYPE,
    typeMapping,
  });
  const regex = evaluation.approaches.find((approach) => approach.approach === BODY_EXTRACTED_REGEX);
  // Only the depends_on gold edge counts: 1 TP, 0 FP, 0 FN (not 2 FN for the other types).
  expect(regex).toEqual(expect.objectContaining({ tp: 1, fp: 0, fn: 0 }));
  expect(regex.falseNegativeEdges).toEqual([]);
});

test('editing the type mapping changes which edges are scored', () => {
  const dataset = {
    groundTruthReviewedIps: [
      { ip: 'bips:1', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'depends_on' },
      ],
      [BODY_EXTRACTED_LLM]: [
        { sourceKey: 'bips:1', targetKey: 'bips:2', relation_type: 'implicit_dependency' },
      ],
    },
  };

  // By default the LLM subtype is excluded -> LLM is not scored.
  const baseline = buildGroundTruthEvaluation(dataset, { matchMode: GROUND_TRUTH_MATCH_MODE_EXACT_TYPE });
  const llmBaseline = baseline.approaches.find((approach) => approach.approach === BODY_EXTRACTED_LLM);
  expect(llmBaseline.evaluated).toBe(false);

  // Opt the LLM subtype in and map it to depends_on -> it now matches the gold edge.
  const typeMapping = {
    gtTypes: ['depends_on'],
    rows: [
      { approach: BODY_EXTRACTED_LLM, subtype: 'implicit_dependency', include: true, target: 'depends_on' },
    ],
  };
  const edited = buildGroundTruthEvaluation(dataset, {
    matchMode: GROUND_TRUTH_MATCH_MODE_EXACT_TYPE,
    typeMapping,
  });
  const llmEdited = edited.approaches.find((approach) => approach.approach === BODY_EXTRACTED_LLM);
  expect(llmEdited).toEqual(expect.objectContaining({ evaluated: true, tp: 1, fp: 0, fn: 0 }));
});

test('ground-truth evaluation can match proposed_replacement against superseded_by', () => {
  const evaluation = buildGroundTruthEvaluation({
    groundTruthReviewedIps: [
      { ip: 'bips:9', reviewed_at: '2026-06-22' },
    ],
    links: {
      [GROUND_TRUTH_CURATED]: [
        { sourceKey: 'bips:9', targetKey: 'bips:10', relation_type: 'superseded_by' },
      ],
      [PREAMBLE_EXTRACTED]: {
        proposed_replacement: [
          { sourceKey: 'bips:9', targetKey: 'bips:10', relation_type: 'proposed_replacement' },
        ],
      },
    },
  }, { matchMode: GROUND_TRUTH_MATCH_MODE_EXACT_TYPE });

  const preamble = evaluation.approaches.find((approach) => approach.approach === PREAMBLE_EXTRACTED);
  expect(preamble).toEqual(expect.objectContaining({ tp: 1, fp: 0, fn: 0 }));
});

test('relation ontology is ecosystem- and source-aware', () => {
  const bitcoin = resolveRelationOntology('bitcoin');
  expect(bitcoin.hasPreambleTypes).toBe(true);
  expect(bitcoin.canonicalMap.requires).toBe('DEPENDS_ON');
  expect(bitcoin.canonicalMap.replaces).toBe('SUPERSEDES');
  expect(bitcoin.canonicalMap.proposed_replacement).toBe('SUPERSEDED_BY');
  expect(bitcoin.alignment).toEqual([
    expect.objectContaining({ canonical: 'DEPENDS_ON', preamble: ['requires'] }),
    expect.objectContaining({ canonical: 'SUPERSEDES', preamble: ['replaces'] }),
    expect.objectContaining({ canonical: 'SUPERSEDED_BY', preamble: ['proposed_replacement'] }),
    expect.objectContaining({ canonical: 'REFERENCES', preamble: [] }),
  ]);

  // Nostr has no preamble dependency headers.
  const nostr = resolveRelationOntology('nostr');
  expect(nostr.hasPreambleTypes).toBe(false);
  expect(nostr.canonicalMap.requires).toBeUndefined();
  expect(nostr.alignment.every((entry) => entry.preamble.length === 0)).toBe(true);

  // Narrowing bitcoin to the slip source drops the BIP preamble vocabulary.
  const slipOnly = resolveRelationOntology('bitcoin', { sourceIds: ['slip'] });
  expect(slipOnly.hasPreambleTypes).toBe(false);
  expect(slipOnly.canonicalMap.requires).toBeUndefined();
});

test('source-scopes canonical dependency edge graph keys for display', () => {
  const links = scopeDependencyLinksForSource({
    dependency_edges: [
      {
        source: 'bips:32',
        target: 'slips:44',
        extraction_method: BODY_EXTRACTED_LLM,
        relation_type: 'implicit_dependency',
        value: 1,
      },
    ],
  }, 'bip', 'bips', { bips: 'bip', slips: 'slip' });

  expect(links[BODY_EXTRACTED_LLM][0]).toMatchObject({
    source: '32',
    target: '44',
    sourceProposalId: '32',
    targetProposalId: '44',
    sourceSourceId: 'bip',
    targetSourceId: 'slip',
    sourceGraphSource: 'bips',
    targetGraphSource: 'slips',
    sourceKey: 'bips:32',
    targetKey: 'slips:44',
  });
});

test('filters dependency graph to cross-source edges and their endpoint nodes', () => {
  const nodes = [
    { id: '32', source: 'bip', graphSource: 'bips' },
    { id: '44', source: 'slip', graphSource: 'slips' },
    { id: '45', source: 'slip', graphSource: 'slips' },
  ];
  const links = [
    { sourceKey: 'bips:32', targetKey: 'slips:44', sourceGraphSource: 'bips', targetGraphSource: 'slips' },
    { sourceKey: 'slips:44', targetKey: 'slips:45', sourceGraphSource: 'slips', targetGraphSource: 'slips' },
  ];

  const filtered = filterCrossSourceDependencyGraph(nodes, links);

  expect(filtered.nodes.map((node) => `${node.graphSource}:${node.id}`)).toEqual(['bips:32', 'slips:44']);
  expect(filtered.links).toEqual([links[0]]);
});

test('filters authorship graph to cross-source proposal refs', () => {
  const data = {
    nodes: [
      { id: 'Ada', bips: [{ source: 'bip', id: '1' }, { source: 'slip', id: '44' }] },
      { id: 'Bob', bips: [{ source: 'bip', id: '2' }] },
      { id: 'Chen', bips: [{ source: 'nip', id: '1' }] },
      { id: 'Drew', bips: [{ source: 'bip', id: '3' }] },
    ],
    edges: [
      { source: 'Ada', target: 'Bob', bips: [{ source: 'bip', id: '1' }] },
      { source: 'Bob', target: 'Chen', bips: [{ source: 'bip', id: '2' }, { source: 'slip', id: '44' }] },
    ],
  };

  const filtered = filterCrossSourceAuthorNetwork(data);

  expect(filtered.nodes.map((node) => node.id)).toEqual(['Ada', 'Bob', 'Chen']);
  expect(filtered.edges).toEqual([data.edges[1]]);
});

test('classification chord uses normalized category labels for SLIP Standard types', () => {
  const dashboardData = buildDashboardData({
    nodes: [
      { id: '10', source: 'slip', type: 'Standard', status: 'Final' },
      { id: '12', source: 'slip', type: 'Standard', status: 'Draft' },
      { id: '16', source: 'slip', type: 'Informational', status: 'Active' },
    ],
    authorship: { bips_per_year: [{ year: 2026, count: 3 }] },
    conformity: {},
  }, bitcoinEcosystem.sources.slip);

  const groups = dashboardData.classificationChordData.groups;
  const indexByKey = new Map(groups.map((group, index) => [group.id, index]));
  const standardIndex = indexByKey.get('type|||Standards Track');
  const finalIndex = indexByKey.get('status|||Final');
  const draftIndex = indexByKey.get('status|||Draft');

  expect(standardIndex).not.toBeUndefined();
  expect(finalIndex).not.toBeUndefined();
  expect(draftIndex).not.toBeUndefined();
  expect(dashboardData.classificationChordData.matrix[standardIndex][finalIndex]).toBe(1);
  expect(dashboardData.classificationChordData.matrix[standardIndex][draftIndex]).toBe(1);
});

describe('proposal link resolution', () => {
  test('uses the snapshot commit and .mediawiki extension for historic BIP links', () => {
    expect(getBipUrl(2, '2026-03-16', { linkMode: 'history' })).toBe(
      'https://github.com/bitcoin/bips/blob/351ceef2747e46078efaa073246fce54d52e665d/bip-0002.mediawiki'
    );
  });

  test('uses the snapshot commit and .md extension for historic BIP links when the BIP file is Markdown', () => {
    expect(getBipUrl(379, '2026-05-28', { linkMode: 'history' })).toBe(
      'https://github.com/bitcoin/bips/blob/7f9434c9c81bb49825200a5be5ddb1ae53fd6dcc/bip-0379.md'
    );
  });

  test('falls back to the latest known BIP file extension when a historic snapshot file lookup misses', () => {
    expect(getBipUrl(3, '2021-01-01', { linkMode: 'history' })).toBe(
      'https://github.com/bitcoin/bips/blob/master/bip-0003.md'
    );
  });

  test('uses bips.dev for current BIP links', () => {
    expect(getBipUrl('BIP-0379', '2026-05-28', { linkMode: 'current' })).toBe(
      'https://bips.dev/379/'
    );
  });

  test('uses the snapshot commit and .md extension for historic SLIP links', () => {
    expect(getRepositoryProposalUrl('bitcoin', 32, '2026-05-28', {
      linkMode: 'history',
      sourceSlug: 'slips',
    })).toBe(
      'https://github.com/satoshilabs/slips/blob/a83ecb73bca0a0837e701664bdcbbb803023eab1/slip-0032.md'
    );
  });

  test('normalizes prefixed SLIP ids for historic links', () => {
    expect(getRepositoryProposalUrl('bitcoin', 'SLIP-0032', '2026-05-28', {
      linkMode: 'history',
      sourceSlug: 'slips',
    })).toBe(
      'https://github.com/satoshilabs/slips/blob/a83ecb73bca0a0837e701664bdcbbb803023eab1/slip-0032.md'
    );
  });

  test('uses the repository default branch for current SLIP links without bips.dev', () => {
    expect(getRepositoryProposalUrl('bitcoin', 'SLIP-0032', '2026-05-28', {
      linkMode: 'current',
      sourceSlug: 'slips',
    })).toBe(
      `https://github.com/satoshilabs/slips/blob/${proposalLinkIndex.bitcoin.sources.slips.defaultBranch}/slip-0032.md`
    );
  });

  test('falls back to the latest known SLIP file when a historic snapshot file lookup misses', () => {
    expect(getRepositoryProposalUrl('bitcoin', 24, '2021-01-01', {
      linkMode: 'history',
      sourceSlug: 'slips',
    })).toBe(
      `https://github.com/satoshilabs/slips/blob/${proposalLinkIndex.bitcoin.sources.slips.defaultBranch}/slip-0024.md`
    );
  });

  test('builds SLIP commit links against the SLIP repository', () => {
    expect(getRepositoryCommitUrl('bitcoin', 'a83ecb73bca0a0837e701664bdcbbb803023eab1', '#', 'slips')).toBe(
      'https://github.com/satoshilabs/slips/commit/a83ecb73bca0a0837e701664bdcbbb803023eab1'
    );
  });

  test('uses the snapshot commit for historic NIP links and normalizes numeric NIP ids', () => {
    expect(getNipUrl('1', '2026-05-30', { linkMode: 'history' })).toBe(
      'https://github.com/nostr-protocol/nips/blob/4f494afd7fdca049bf2e307cc547ee512f48266a/01.md'
    );
  });

  test('uses the snapshot commit for historic hex NIP links', () => {
    expect(getNipUrl('nip-f4', '2026-05-30', { linkMode: 'history' })).toBe(
      'https://github.com/nostr-protocol/nips/blob/4f494afd7fdca049bf2e307cc547ee512f48266a/F4.md'
    );
  });

  test('uses the repository default branch for current NIP links', () => {
    expect(getNipUrl('F4', '2026-05-30', { linkMode: 'current' })).toBe(
      `https://github.com/nostr-protocol/nips/blob/${proposalLinkIndex.nostr.sources.nips.defaultBranch}/F4.md`
    );
  });
});

test('builds GitHub commit links for proposal event timeline markers', () => {
  expect(getBipCommitUrl('76132ec28493c690034771c9b2289df1e37d99a6')).toBe(
    'https://github.com/bitcoin/bips/commit/76132ec28493c690034771c9b2289df1e37d99a6'
  );
});

describe('slipLinks convenience wrapper', () => {
  test('normalizeSlipId strips the SLIP- prefix and leading zeros', () => {
    expect(normalizeSlipId('SLIP-0032')).toBe('32');
    expect(normalizeSlipId('slip 44')).toBe('44');
    expect(normalizeSlipId(173)).toBe('173');
  });

  test('getSlipUrl resolves historic links via the slips source slug', () => {
    expect(getSlipUrl('SLIP-0032', '2026-05-28', { linkMode: 'history' })).toBe(
      'https://github.com/satoshilabs/slips/blob/a83ecb73bca0a0837e701664bdcbbb803023eab1/slip-0032.md'
    );
  });

  test('getSlipUrl resolves current links to the SLIP repository default branch', () => {
    expect(getSlipUrl(32, '2026-05-28', { linkMode: 'current' })).toBe(
      `https://github.com/satoshilabs/slips/blob/${proposalLinkIndex.bitcoin.sources.slips.defaultBranch}/slip-0032.md`
    );
  });

  test('getSlipCommitUrl targets the SLIP repository', () => {
    expect(getSlipCommitUrl('a83ecb73bca0a0837e701664bdcbbb803023eab1')).toBe(
      'https://github.com/satoshilabs/slips/commit/a83ecb73bca0a0837e701664bdcbbb803023eab1'
    );
  });
});

describe('proposal-list tooltip rendering', () => {
  test('legacy flat id list goes through ecosystem-level link helpers', () => {
    const html = renderProposalListHtml([32, 44], '2026-05-28', {
      ecosystem: bitcoinEcosystem,
      linkMode: 'current',
    });
    expect(html).toMatch(/BIP\s*32/);
    expect(html).toMatch(/href="https:\/\/bips\.dev\/32\/"/);
  });

  test('single-source refs render without source grouping', () => {
    const refs = [{ source: 'bip', id: '32' }, { source: 'bip', id: '44' }];
    const html = renderProposalListHtml(refs, '2026-05-28', {
      ecosystem: bitcoinEcosystem,
      linkMode: 'current',
    });
    expect(html).not.toMatch(/<strong>BIPs:<\/strong>/);
    expect(html).toMatch(/href="https:\/\/bips\.dev\/32\/"/);
    expect(html).toMatch(/href="https:\/\/bips\.dev\/44\/"/);
  });

  test('multi-source refs group by source with source-specific link builders', () => {
    const refs = [
      { source: 'bip', id: '32' },
      { source: 'slip', id: '32' },
      { source: 'bip', id: '44' },
    ];
    const html = renderProposalListHtml(refs, '2026-05-28', {
      ecosystem: bitcoinEcosystem,
      linkMode: 'history',
    });
    expect(html).toMatch(/<strong>BIPs:<\/strong>/);
    expect(html).toMatch(/<strong>SLIPs:<\/strong>/);
    expect(html).toMatch(/bitcoin\/bips\/blob\/[a-f0-9]+\/bip-0032/);
    expect(html).toMatch(/satoshilabs\/slips\/blob\/[a-f0-9]+\/slip-0032/);
  });

  test('empty list returns the configured empty text', () => {
    expect(renderProposalListHtml([], null, { emptyText: 'nothing here' })).toBe('nothing here');
  });
});

describe('ecosystem source map', () => {
  test('bitcoin ecosystem exposes BIP and SLIP sources with the BIP source hoisted as default', () => {
    expect(bitcoinEcosystem.defaultSourceId).toBe('bip');
    expect(bitcoinEcosystem.sourceOrder).toEqual(['bip', 'slip']);
    expect(Object.keys(bitcoinEcosystem.sources)).toEqual(['bip', 'slip']);
    expect(bitcoinEcosystem.acronym).toBe('BIP');
    expect(bitcoinEcosystem.dataPath).toBe(bitcoinEcosystem.sources.bip.dataPath);
  });

  test('SLIP source formats proposal labels with the SLIP prefix (no dash, no padding)', () => {
    expect(bitcoinEcosystem.sources.slip.formatProposalReference(32)).toBe('SLIP32');
    expect(bitcoinEcosystem.sources.slip.formatProposalLabel(44)).toBe('SLIP 44');
    // URL paths still use the 4-digit padded filename:
    expect(bitcoinEcosystem.sources.slip.getProposalUrl(32, '2026-05-28', { linkMode: 'current' }))
      .toMatch(/slip-0032\.md$/);
  });

  test('nostr ecosystem exposes a single nip source', () => {
    expect(nostrEcosystem.defaultSourceId).toBe('nip');
    expect(nostrEcosystem.sourceOrder).toEqual(['nip']);
    expect(nostrEcosystem.sources.nip.acronym).toBe('NIP');
  });
});

describe('proposal filter parsing', () => {
  const nodes = [
    { source: 'bip', id: '32', word_list: { bitcoin: 2 } },
    { source: 'bip', id: '44', word_list: { wallet: 3 } },
    { source: 'slip', id: '32', word_list: { trezor: 5 } },
    { source: 'slip', id: '44', word_list: { wallet: 7 } },
  ];

  test('source-prefixed ids and source-only tokens produce source-aware refs', () => {
    expect(parseProposalFilterExpression('bip32, slip', nodes, bitcoinEcosystem)).toEqual([
      { source: 'bip', id: '32' },
      { source: 'slip', id: '32' },
      { source: 'slip', id: '44' },
    ]);
  });

  test('source-prefixed ranges stay within their source', () => {
    expect(parseProposalFilterExpression('SLIP32-44', nodes, bitcoinEcosystem)).toEqual([
      { source: 'slip', id: '32' },
      { source: 'slip', id: '44' },
    ]);
  });

  test('word cloud filters distinguish proposals with the same numeric id', () => {
    const refs = parseProposalFilterExpression('SLIP32', nodes, bitcoinEcosystem);
    expect(buildWordCloudData(nodes, refs, bitcoinEcosystem)).toEqual([
      { word: 'trezor', count: 5 },
    ]);
  });

  test('legacy plain-id callers still receive plain ids', () => {
    expect(parseProposalFilterExpression('32, 40-45', ['32', '44'])).toEqual(['32', '44']);
  });
});

describe('proposal filter control', () => {
  test('builds grouped source-prefixed filter expressions via enter workflow', () => {
    const handleChange = jest.fn();
    const { rerender } = render(
      <ProposalFilterControl value="" onChange={handleChange} ecosystem={bitcoinEcosystem} />
    );

    const input = screen.getByLabelText('Filter proposals');
    fireEvent.change(input, { target: { value: 'bip' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.queryByText('adding BIPs')).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: '2,3-5' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(handleChange).toHaveBeenLastCalledWith('BIP2-5');

    rerender(<ProposalFilterControl value="BIP2-5" onChange={handleChange} ecosystem={bitcoinEcosystem} />);
    expect(screen.getByText('BIPs: 2-5')).toBeInTheDocument();
  });

  test('compacts numeric selections into succinct ranges', () => {
    const handleChange = jest.fn();
    render(
      <ProposalFilterControl value="BIP2-4,BIP11" onChange={handleChange} ecosystem={bitcoinEcosystem} />
    );

    const input = screen.getByLabelText('Filter proposals');
    fireEvent.click(screen.getByText('BIPs: 2-4,11'));
    fireEvent.change(input, { target: { value: '5' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(handleChange).toHaveBeenLastCalledWith('BIP2-5,BIP11');
  });
});

describe('classification relation table links', () => {
  test('source-aware proposal refs build source-specific labels and links', () => {
    expect(buildClassificationRelationProposalLabel({ source: 'bip', id: '32' }, bitcoinEcosystem))
      .toBe('BIP 32');
    expect(buildClassificationRelationProposalLabel({ source: 'slip', id: '32' }, bitcoinEcosystem))
      .toBe('SLIP 32');

    expect(buildClassificationRelationProposalUrl(
      { source: 'bip', id: '32' },
      '2026-05-28',
      'history',
      bitcoinEcosystem
    )).toMatch(
      /bitcoin\/bips\/blob\/[a-f0-9]+\/bip-0032/
    );
    expect(buildClassificationRelationProposalUrl(
      { source: 'slip', id: '32' },
      '2026-05-28',
      'history',
      bitcoinEcosystem
    )).toMatch(
      /satoshilabs\/slips\/blob\/[a-f0-9]+\/slip-0032/
    );
  });
});

test('builds GitHub commit links for NIP timeline markers', () => {
  expect(getNipCommitUrl('06cccbca3b190304650ac2efb0caff0325486348')).toBe(
    'https://github.com/nostr-protocol/nips/commit/06cccbca3b190304650ac2efb0caff0325486348'
  );
});

test('uses fixed status colors so evolution views stay aligned across subsets', () => {
  expect(getClassificationColorMap('status', ['Rejected', 'Proposed', 'Closed', 'Draft', 'Unknown'])).toEqual({
    Rejected: '#e15759',
    Proposed: '#59a14f',
    Closed: '#868e96',
    Draft: '#4e79a7',
    Unknown: '#bab0ab',
  });
});
