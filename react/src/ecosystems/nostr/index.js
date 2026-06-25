import logo from './logo.png';
import { getNipCommitUrl, getNipUrl, normalizeNipId } from '../../nipLinks';
import { attachGeneratedEcosystem } from '../buildGeneratedEcosystem';

const nostrEcosystem = attachGeneratedEcosystem('nostr', {
  logo,
  sourceAdapters: {
    nip: {
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
    },
  },
});

export default nostrEcosystem;
