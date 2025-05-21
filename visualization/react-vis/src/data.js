const context = require.context('../../../bips_json', false, /\.json$/); // Match all JSON files

const allFiles = context.keys();

const bipData = allFiles.map(filename => {
  const bip = context(filename); // Dynamically import the JSON data
  return bip;
});

// Utility: Normalize "BIP 123", "BIP-123", "123, 124" => ["123", "124"]
function normalizeBipIds(field) {
  if (!field) return [];

  const rawItems = Array.isArray(field)
    ? field
    : String(field).split(',');

  return rawItems
    .map(item => String(item).trim())
    .filter(item => item.length > 0)
    .map(item => item.replace(/^BIP[-\s]*/i, ''))
    .filter(id => /^\d+$/.test(id)); // only numeric strings
}

// Main data structures
let nodes = [];
let referenceLinks = [];
let dependencyLinks = [];
let requiresLinks = [];
let replacesLinks = [];
let supersedesLinks = [];
let nodeIds = new Set(); // Track existing nodes

bipData.forEach(bip => {
  if (bip) {
    const preamble = bip.raw?.preamble;
    const insights = bip.insights || {};
    const normalizedBipId = preamble?.bip;

    // Skip if invalid
    if (!normalizedBipId) return;

    // --- Add Node ---
    if (!nodeIds.has(normalizedBipId)) {
      nodes.push({
        id: normalizedBipId,
        group: preamble.layer,
        compliance_score: preamble.compliance_score,
        created: preamble.created,
        author: preamble.author,
        word_list: insights.word_list,
        status: preamble.status,
        type: preamble.type
      });
      nodeIds.add(normalizedBipId);
    }

    // --- References (LLM / pattern matched) ---
    const referencesArray = normalizeBipIds(insights.bip_references);
    referencesArray.forEach(refId => {
      if (nodeIds.has(refId)) {
        referenceLinks.push({ source: normalizedBipId, target: refId, value: 1 });
      }
    });

    // --- Dependencies (LLM or other logic) ---
    const dependenciesArray = normalizeBipIds(insights.dependencies);
    dependenciesArray.forEach(depId => {
      if (nodeIds.has(depId)) {
        dependencyLinks.push({ source: normalizedBipId, target: depId, value: 1 });
      }
    });

    // --- Requires Links ---
    const requiresArray = normalizeBipIds(preamble.requires);
    requiresArray.forEach(reqId => {
      if (nodeIds.has(reqId)) {
        requiresLinks.push({ source: normalizedBipId, target: reqId, value: 1 });
      }
    });

    // --- Replaces Links ---
    const replacesArray = normalizeBipIds(preamble.replaces);
    replacesArray.forEach(repId => {
      if (nodeIds.has(repId)) {
        replacesLinks.push({ source: normalizedBipId, target: repId, value: 1 });
      }
    });

    // --- Superseded By Links ---
    const supersededArray = normalizeBipIds(preamble.superseded_by);
    supersededArray.forEach(supId => {
      if (nodeIds.has(supId)) {
        supersedesLinks.push({ source: normalizedBipId, target: supId, value: 1 });
      }
    });
  }
});

// Final network structure
const data = {
  nodes,
  links: {
    references: referenceLinks,
    dependencies: dependencyLinks,
    requires: requiresLinks,
    replaces: replacesLinks,
    superseded_by: supersedesLinks
  }
};

export default data;

console.log('✅ Network Diagram Data:', data);
