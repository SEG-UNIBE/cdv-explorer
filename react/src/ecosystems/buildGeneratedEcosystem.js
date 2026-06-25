import generatedEcosystems from '../generated/ecosystems.json';

export function getGeneratedEcosystem(id) {
  return generatedEcosystems.find((ecosystem) => ecosystem.id === id) || null;
}

export function attachGeneratedEcosystem(id, { logo, sourceAdapters = {} } = {}) {
  const generated = getGeneratedEcosystem(id);
  if (!generated) {
    throw new Error(`Generated ecosystem config not found: ${id}`);
  }

  const sources = Object.fromEntries(
    Object.entries(generated.sources || {}).map(([sourceId, source]) => [
      sourceId,
      {
        ...source,
        ...(sourceAdapters[sourceId] || {}),
      },
    ])
  );
  const defaultSource = generated.defaultSourceId ? sources[generated.defaultSourceId] : {};

  return {
    ...generated,
    sources,
    ...defaultSource,
    logo,
  };
}
