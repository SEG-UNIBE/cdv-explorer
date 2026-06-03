import logo from './logo.png';
import { getNipCommitUrl, getNipUrl, normalizeNipId } from '../../nipLinks';

const nipSource = {
  sourceId: 'nip',
  sourceSlug: 'nips',
  acronym: 'NIP',
  label: 'Nostr Implementation Possibilities',
  shortLabel: 'NIPs',
  proposalPlural: 'Nostr Implementation Possibilities (NIPs)',
  proposalShortPlural: 'NIPs',
  sourceRepositories: ['github/nostr-protocol/nips'],
  dataPath: 'ip_data/nostr/nips/03_analysis',
  classificationDimensions: [
    { field: 'status', label: 'Status' },
    { field: 'type', label: 'Type' },
    { field: 'layer', label: 'Layer' },
  ],
  classificationChordBadgeOffsets: {
    layer: { x: -20 },
  },
  complianceStandards: [
    { key: 'nip', label: 'NIP Conformity', color: '#4c72b0', hoverColor: '#3a5a8e' },
  ],
  normalizeProposalId: (id, options) => normalizeNipId(id, options),
  formatProposalReference: (id) => {
    const normalized = normalizeNipId(id);
    return normalized ? `NIP${normalized}` : String(id ?? '');
  },
  formatProposalLabel: (id) => {
    const normalized = normalizeNipId(id);
    return normalized ? `NIP ${normalized}` : String(id ?? '');
  },
  getProposalUrl: (id, snapshotLabel, options) => getNipUrl(id, snapshotLabel, options),
  getProposalCommitUrl: (commitHash, options) => getNipCommitUrl(commitHash, options),
};

const nostrEcosystem = {
  id: 'nostr',
  name: 'Nostr',
  logo,
  status: 'available',
  description: 'Improvement proposals across the Nostr ecosystem',
  ecosystemDescription: 'Nostr is a decentralized messaging protocol built on relays and clients. NIPs (Nostr Implementation Possibilities) define the rules of this protocol, specifying message formats, event kinds, and relay behaviors.',
  sources: { nip: nipSource },
  sourceOrder: ['nip'],
  defaultSourceId: 'nip',
  ...nipSource,
};

export default nostrEcosystem;
