import bitcoinEcosystem from './bitcoin';
import nostrEcosystem from './nostr';
import torEcosystem from './tor';

export const ecosystems = [bitcoinEcosystem, nostrEcosystem, torEcosystem];

export const ecosystemsById = Object.fromEntries(
  ecosystems.map((ecosystem) => [ecosystem.id, ecosystem]),
);
