const context = require.context('../../../bips_json', false, /\.json$/); // Match all JSON files

const allFiles = context.keys();

const bipData = allFiles.map(filename => {
  const bip = context(filename); // Dynamically import the JSON data
  return bip;
});

console.log('Loaded BIP Data:', bipData);

let nodes = [];
let links = [];
let nodeIds = new Set(); // Track existing nodes

bipData.forEach(bip => {
  if (bip) {
    const normalizedBipId = bip.raw.preamble.bip; // Normalize the BIP ID
    // Add node to the nodes array if it doesn't exist
    if (!nodeIds.has(normalizedBipId)) {
      nodes.push({ id: normalizedBipId, group: bip.raw.preamble.layer, compliance:  bip.raw.preamble.comnpliance_score});
      nodeIds.add(normalizedBipId);
    }

    // Create edges based on the 'references' field in the preamble
    if (bip.raw.preamble && bip.insights.bip_references) {
      const referencesArray = typeof bip.insights.bip_references === 'string'
        ? bip.insights.bip_references.split(',').map(dep => dep.trim())  // Split and trim each dependency
        : bip.insights.bip_references;   // Leave it as-is if it's already an array
    
      // Now loop through the array
      referencesArray.forEach(dep => {
        const normalizedDepId = dep.replace(/^BIP /, ''); // Normalize the dependency ID
        // Only create edge if the dependency node exists
        if (nodeIds.has(normalizedDepId)) {
          links.push({ source: normalizedBipId, target: normalizedDepId, value: 1 });
        }
      });
    } else {
      console.warn('references field is empty');
    }
  } else {
    console.warn('Malformed or missing bip data:', bip);
  }
});

const data = { nodes, links };

console.log('Network Diagram Data:', data);

export default data;
