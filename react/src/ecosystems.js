import bitcoinLogo from './bitcoin-logo.png';
import ethereumLogo from './ethereum-logo.svg';
import torLogo from './tor-logo.svg';

export const ecosystems = [
  {
    id: 'bitcoin',
    name: 'Bitcoin',
    acronym: 'BIP',
    logo: bitcoinLogo,
    proposalPlural: 'Bitcoin Improvement Proposals (BIPs)',
    proposalShortPlural: 'BIPs',
    status: 'available',
    description: 'The first implemented adapter in this repository, covering the Bitcoin proposal process and its linked metadata.',
  },
  {
    id: 'ethereum',
    name: 'Ethereum',
    acronym: 'EIP',
    logo: ethereumLogo,
    proposalPlural: 'Ethereum Improvement Proposals (EIPs)',
    proposalShortPlural: 'EIPs',
    status: 'coming-soon',
    description: 'Planned next: the same analysis pipeline shape with Ethereum-specific repository and schema rules.',
  },
  {
    id: 'tor',
    name: 'Tor',
    acronym: 'TP',
    logo: torLogo,
    proposalPlural: 'Tor Design Proposals (TORDP)',
    proposalShortPlural: 'Tor proposals',
    status: 'coming-soon',
    description: 'Also a strong fit for timeline, dependency, and authorship exploration once an adapter exists.',
  },
];

export const ecosystemsById = Object.fromEntries(
  ecosystems.map((ecosystem) => [ecosystem.id, ecosystem]),
);
