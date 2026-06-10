import logo from './logo.png';
import { getBipCommitUrl, getBipUrl, normalizeBipId } from '../../bipLinks';
import { getSlipCommitUrl, getSlipUrl, normalizeSlipId } from '../../slipLinks';
import { attachGeneratedEcosystem } from '../buildGeneratedEcosystem';

const bitcoinEcosystem = attachGeneratedEcosystem('bitcoin', {
  logo,
  sourceAdapters: {
    bip: {
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
    },
    slip: {
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
    },
  },
});

export default bitcoinEcosystem;
