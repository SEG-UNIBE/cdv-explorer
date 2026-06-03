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
import { getRepositoryCommitUrl, getRepositoryProposalUrl } from './proposalLinkResolver';
import proposalLinkIndex from './generated/proposalLinkIndex.json';

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
