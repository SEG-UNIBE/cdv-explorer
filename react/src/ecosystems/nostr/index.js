import logo from './logo.png';
import { getNipCommitUrl, getNipUrl, normalizeNipId } from '../../nipLinks';

const nostrEcosystem = {
  id: 'nostr',
  name: 'Nostr',
  acronym: 'NIP',
  logo,
  proposalPlural: 'Nostr Implementation Possibilities (NIPs)',
  proposalShortPlural: 'NIPs',
  status: 'available',
  description: 'Nostr Implementation Possibilities (NIPs)',
  dashboardDescription: 'Nostr is a decentralized messaging protocol built on relays and clients — together forming a social layer analogous to an OSI layer. Nostr Implementation Possibilities (NIPs) define the rules of this protocol, specifying message formats, event kinds, and relay behaviors. The NIPs are maintained as a collection of Markdown documents on GitHub.',
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

export default nostrEcosystem;
