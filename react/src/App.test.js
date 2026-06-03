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
import nipLinkIndex from './generated/nipLinkIndex.json';

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

test('uses the snapshot commit for historic BIP links when the file exists in that snapshot', () => {
  expect(getBipUrl(2, '2026-03-16', { linkMode: 'history' })).toBe(
    'https://github.com/bitcoin/bips/blob/351ceef2747e46078efaa073246fce54d52e665d/bip-0002.mediawiki'
  );
});

test('falls back to the latest repository file when a historic snapshot file lookup misses', () => {
  expect(getBipUrl(3, '2021-01-01', { linkMode: 'history' })).toBe(
    'https://github.com/bitcoin/bips/blob/master/bip-0003.md'
  );
});

test('builds GitHub commit links for proposal event timeline markers', () => {
  expect(getBipCommitUrl('76132ec28493c690034771c9b2289df1e37d99a6')).toBe(
    'https://github.com/bitcoin/bips/commit/76132ec28493c690034771c9b2289df1e37d99a6'
  );
});

test('uses the snapshot commit for historic NIP links when the file exists in that snapshot', () => {
  expect(getNipUrl('1', '2026-05-30', { linkMode: 'history' })).toBe(
    'https://github.com/nostr-protocol/nips/blob/0731968ee9f61de993e43f8bd865439e19a7b655/01.md'
  );
});

test('uses the repository default branch for current NIP links', () => {
  expect(getNipUrl('F4', '2026-05-30', { linkMode: 'current' })).toBe(
    `https://github.com/nostr-protocol/nips/blob/${nipLinkIndex.defaultBranch}/F4.md`
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
