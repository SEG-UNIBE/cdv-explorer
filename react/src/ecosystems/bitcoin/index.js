import logo from './logo.png';
import { getBipCommitUrl, getBipUrl, normalizeBipId } from '../../bipLinks';

const bitcoinEcosystem = {
  id: 'bitcoin',
  name: 'Bitcoin',
  acronym: 'BIP',
  logo,
  proposalPlural: 'Bitcoin Improvement Proposals (BIPs)',
  proposalShortPlural: 'BIPs',
  status: 'available',
  description: 'Bitcoin Improvement Proposals (BIPs)',
  dashboardDescription: 'Bitcoin Improvement Proposals (BIPs) are the main specification documents of the Bitcoin ecosystem, defining features, behavior, and processual or informational aspects. The catalog is maintained on GitHub and serves as the primary data source for the analyses below.',
  sourceRepositories: ['github/bitcoin/bips'],
  dataPath: 'ip_data/bitcoin/03_analysis',
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

export default bitcoinEcosystem;
