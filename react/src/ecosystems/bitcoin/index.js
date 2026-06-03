import logo from './logo.png';
import { getBipCommitUrl, getBipUrl, normalizeBipId } from '../../bipLinks';
import { getSlipCommitUrl, getSlipUrl, normalizeSlipId } from '../../slipLinks';

const bipSource = {
  sourceId: 'bip',
  sourceSlug: 'bips',
  acronym: 'BIP',
  label: 'Bitcoin Improvement Proposals',
  shortLabel: 'BIPs',
  proposalPlural: 'Bitcoin Improvement Proposals (BIPs)',
  proposalShortPlural: 'BIPs',
  sourceRepositories: ['github/bitcoin/bips'],
  dataPath: 'ip_data/bitcoin/bips/03_analysis',
  classificationDimensions: [
    { field: 'status', label: 'Status' },
    { field: 'type', label: 'Type' },
    { field: 'layer', label: 'Layer' },
  ],
  complianceStandards: [
    { key: 'bip2', label: 'BIP2 Conformity', color: '#e45756', hoverColor: '#b63f3e' },
    { key: 'bip3', label: 'BIP3 Conformity', color: '#f08c00', hoverColor: '#e67700' },
  ],
  normalizeProposalId: (id, options) => normalizeBipId(id, options),
  formatProposalReference: (id) => {
    const normalized = normalizeBipId(id, { lowercaseFallback: true });
    return normalized ? `BIP${normalized}` : String(id ?? '');
  },
  formatProposalLabel: (id) => {
    const normalized = normalizeBipId(id, { lowercaseFallback: true });
    return normalized ? `BIP ${normalized}` : String(id ?? '');
  },
  getProposalUrl: (id, snapshotLabel, options) => getBipUrl(id, snapshotLabel, options),
  getProposalCommitUrl: (commitHash, options) => getBipCommitUrl(commitHash, options),
};

const slipSource = {
  sourceId: 'slip',
  sourceSlug: 'slips',
  acronym: 'SLIP',
  label: 'SatoshiLabs Improvement Proposals',
  shortLabel: 'SLIPs',
  proposalPlural: 'SatoshiLabs Improvement Proposals (SLIPs)',
  proposalShortPlural: 'SLIPs',
  sourceRepositories: ['github/satoshilabs/slips'],
  dataPath: 'ip_data/bitcoin/slips/03_analysis',
  classificationDimensions: [
    { field: 'status', label: 'Status' },
    { field: 'type', label: 'Type' },
  ],
  complianceStandards: [],
  normalizeProposalId: (id, options) => normalizeSlipId(id, options),
  formatProposalReference: (id) => {
    const normalized = normalizeSlipId(id, { lowercaseFallback: true });
    return normalized ? `SLIP${normalized}` : String(id ?? '');
  },
  formatProposalLabel: (id) => {
    const normalized = normalizeSlipId(id, { lowercaseFallback: true });
    return normalized ? `SLIP ${normalized}` : String(id ?? '');
  },
  getProposalUrl: (id, snapshotLabel, options) => getSlipUrl(id, snapshotLabel, options),
  getProposalCommitUrl: (commitHash, options) => getSlipCommitUrl(commitHash, options),
};

const bitcoinEcosystem = {
  id: 'bitcoin',
  name: 'Bitcoin',
  logo,
  status: 'available',
  description: 'Improvement proposals across the Bitcoin ecosystem',
  ecosystemDescription: 'The Bitcoin ecosystem maintains two complementary series of improvement proposals: BIPs (Bitcoin Improvement Proposals) for core protocol changes and SLIPs (SatoshiLabs Improvement Proposals) for wallet-layer standards. Use the source picker to focus on one series, or analyze both together.',
  sources: { bip: bipSource, slip: slipSource },
  sourceOrder: ['bip', 'slip'],
  defaultSourceId: 'bip',
  ...bipSource,
};

export default bitcoinEcosystem;
