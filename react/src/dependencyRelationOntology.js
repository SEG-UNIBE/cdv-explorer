// Ecosystem- and IP-source-aware relation-type ontology.
//
// Ground-truth curated labels (depends_on / supersedes / references) and the
// generic Regex (`reference`) and LLM (`implicit_dependency`) labels are the same
// across every ecosystem, so they live in a single universal map. Only the
// preamble vocabulary is IP-source specific (e.g. the BIP preamble headers
// `requires` / `replaces` / `proposed_replacement`), so it is declared per
// ecosystem and per source and merged in on demand.

const CANONICAL_TYPE_ORDER = ['DEPENDS_ON', 'SUPERSEDES', 'SUPERSEDED_BY', 'REFERENCES'];

// Curated ground-truth labels per canonical type (ecosystem-independent).
const GROUND_TRUTH_CANONICAL = {
  DEPENDS_ON: ['depends_on'],
  SUPERSEDES: ['supersedes'],
  SUPERSEDED_BY: ['superseded_by'],
  REFERENCES: ['references'],
};

// Labels shared across all ecosystems and sources.
const UNIVERSAL_RELATION_TYPE_MAP = {
  // ground truth
  depends_on: 'DEPENDS_ON',
  supersedes: 'SUPERSEDES',
  superseded_by: 'SUPERSEDED_BY',
  references: 'REFERENCES',
  // generic extraction approaches
  reference: 'REFERENCES', // Regex
  implicit_dependency: 'REFERENCES', // LLM
};

// IP-source-specific preamble vocabularies, keyed by ecosystem id then source id.
// `map` aligns native preamble labels onto the canonical taxonomy; `excluded`
// lists labels intentionally dropped from the evaluation.
const SOURCE_PREAMBLE_ONTOLOGY = {
  bitcoin: {
    bip: {
      map: {
        requires: 'DEPENDS_ON',
        replaces: 'SUPERSEDES',
        proposed_replacement: 'SUPERSEDED_BY',
      },
    },
    // slip: no preamble dependency headers
  },
  // nostr.nip, tor.*: no preamble dependency headers
};

// Resolve the ontology for a given ecosystem and (optionally) a subset of IP
// sources. Passing no ecosystem merges every known source vocabulary, which is
// the safe default for callers without ecosystem context.
export function resolveRelationOntology(ecosystemId = null, { sourceIds = null } = {}) {
  const canonicalMap = { ...UNIVERSAL_RELATION_TYPE_MAP };
  const excludedTypes = new Set();
  const preambleByCanonical = {};

  const ecosystemEntries = ecosystemId
    ? [SOURCE_PREAMBLE_ONTOLOGY[ecosystemId]].filter(Boolean)
    : Object.values(SOURCE_PREAMBLE_ONTOLOGY);

  ecosystemEntries.forEach((sources) => {
    Object.entries(sources).forEach(([sourceId, def]) => {
      if (sourceIds && !sourceIds.includes(sourceId)) {
        return;
      }
      Object.entries(def.map || {}).forEach(([label, canonical]) => {
        const key = String(label).toLowerCase();
        canonicalMap[key] = canonical;
        if (!preambleByCanonical[canonical]) {
          preambleByCanonical[canonical] = [];
        }
        if (!preambleByCanonical[canonical].includes(key)) {
          preambleByCanonical[canonical].push(key);
        }
      });
      (def.excluded || []).forEach((label) => excludedTypes.add(String(label).toLowerCase()));
    });
  });

  const alignment = CANONICAL_TYPE_ORDER.map((canonical) => ({
    canonical,
    groundTruth: GROUND_TRUTH_CANONICAL[canonical] || [],
    preamble: preambleByCanonical[canonical] || [],
  }));

  const hasPreambleTypes = alignment.some((entry) => entry.preamble.length > 0);

  return {
    ecosystemId,
    canonicalMap,
    excludedTypes,
    alignment,
    hasPreambleTypes,
  };
}

// Merged ontology over every known ecosystem/source. Used as the default when a
// caller does not supply ecosystem context (e.g. tests).
export const DEFAULT_RELATION_ONTOLOGY = resolveRelationOntology();
