const context = require.context('../../../bips_json', false, /\.json$/); // Match all JSON files

const allFiles = context.keys();

const bipData = allFiles.map(filename => {
  const bip = context(filename); // Dynamically import the JSON data
  return bip;
});

console.log('Loaded BIP Data:', bipData);

let nodes = [];
let referenceLinks = [];
let dependencyLinks = [];
let nodeIds = new Set(); // Track existing nodes

bipData.forEach(bip => {
  if (bip) {
    const normalizedBipId = bip.raw.preamble.bip;

    // Create node
    if (!nodeIds.has(normalizedBipId)) {
      nodes.push({
        id: normalizedBipId,
        group: bip.raw.preamble.layer,
        compliance_score: bip.raw.preamble.compliance_score,
        created: bip.raw.preamble.created,
        author: bip.raw.preamble.author
      });
      nodeIds.add(normalizedBipId);
    }

    // --- Reference Links ---
    const referencesArray = Array.isArray(bip.insights?.bip_references)
      ? bip.insights.bip_references
      : [];

    referencesArray.forEach(dep => {
      const normalizedDepId = dep.replace(/^BIP /, '');
      if (nodeIds.has(normalizedDepId)) {
        referenceLinks.push({ source: normalizedBipId, target: normalizedDepId, value: 1 });
      }
    });

    // --- Dependency Links ---
    const dependenciesArray = Array.isArray(bip.insights?.dependencies)
      ? bip.insights.dependencies
      : [];

    dependenciesArray.forEach(dep => {
      const normalizedDepId = dep.replace(/^BIP /, '');
      if (nodeIds.has(normalizedDepId)) {
        dependencyLinks.push({ source: normalizedBipId, target: normalizedDepId, value: 1 });
      }
    });
  }
});


const data = {
  nodes,
  links: {
    references: referenceLinks,
    dependencies: dependencyLinks
  }
};

export default data;


console.log('Network Diagram Data:', data);
