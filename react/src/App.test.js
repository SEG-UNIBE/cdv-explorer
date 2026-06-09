jest.mock('d3', () => ({}));

import { fireEvent, render, screen } from '@testing-library/react';
import {
  BODY_EXTRACTED_LLM,
  BODY_EXTRACTED_REGEX,
  DEFAULT_DEPENDENCY_APPROACH,
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
import { buildWordCloudData, parseProposalFilterExpression } from './dashboard/dashboardData';
import { buildProposalGraphId, scopeDependencyLinksForSource } from './data';
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
  ]);
});

test('normalizes legacy dependency link keys into canonical keys', () => {
  const normalized = normalizeDependencyLinks({
    explicit_references: [{ source: '1', target: '2', value: 1 }],
    explicit_dependencies: {
      requires: [{ source: '2', target: '1', value: 1 }],
      replaces: [],
      superseded_by: [],
    },
    implicit_dependencies: [{ source: '3', target: '2', value: 1 }],
  });

  expect(normalized[BODY_EXTRACTED_REGEX]).toHaveLength(1);
  expect(normalized[PREAMBLE_EXTRACTED].requires).toHaveLength(1);
  expect(normalized[PREAMBLE_EXTRACTED].proposed_replacement).toHaveLength(0);
  expect(normalized[BODY_EXTRACTED_LLM]).toHaveLength(1);
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
    expect(getRepositoryProposalUrl('bitcoin', 32, '2021-01-01', {
      linkMode: 'history',
      sourceSlug: 'slips',
    })).toBe(
      `https://github.com/satoshilabs/slips/blob/${proposalLinkIndex.bitcoin.sources.slips.defaultBranch}/slip-0032.md`
    );
  });

  test('builds SLIP commit links against the SLIP repository', () => {
    expect(getRepositoryCommitUrl('bitcoin', 'a83ecb73bca0a0837e701664bdcbbb803023eab1', '#', 'slips')).toBe(
      'https://github.com/satoshilabs/slips/commit/a83ecb73bca0a0837e701664bdcbbb803023eab1'
    );
  });

  test('uses the snapshot commit for historic NIP links and normalizes numeric NIP ids', () => {
    expect(getNipUrl('1', '2026-05-30', { linkMode: 'history' })).toBe(
      'https://github.com/nostr-protocol/nips/blob/0731968ee9f61de993e43f8bd865439e19a7b655/01.md'
    );
  });

  test('uses the snapshot commit for historic hex NIP links', () => {
    expect(getNipUrl('nip-f4', '2026-05-30', { linkMode: 'history' })).toBe(
      'https://github.com/nostr-protocol/nips/blob/0731968ee9f61de993e43f8bd865439e19a7b655/F4.md'
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
