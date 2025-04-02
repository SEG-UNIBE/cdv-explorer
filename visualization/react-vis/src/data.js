// Step 1: Create a context to load all the JSON files from the 'bips_json' folder
const context = require.context('../../../bips_json', false, /\.json$/); // Match all JSON files

// Step 2: Get all file names from the context
const allFiles = context.keys();

// Step 3: Load the data for all files dynamically
const bipData = allFiles.map(filename => {
  const bip = context(filename); // Dynamically import the JSON data
  return bip;
});

console.log('Loaded BIP Data:', bipData);

// Step 4: Initialize nodes and links (edges) for the network diagram
let nodes = [];
let links = [];

// Step 5: Create nodes and links based on the loaded BIP data
bipData.forEach(bip => {
  if (bip) {
    const normalizedBipId = bip.raw.bip; // Normalize the BIP ID
    
    // Add node to the nodes array
    nodes.push({ id: normalizedBipId, group: 'bipGroup' });

    // Create edges based on the 'requires' field in the preamble
    if (bip.raw.preamble && bip.raw.preamble.requires) {
      const requiresArray = typeof bip.raw.preamble.requires === 'string'
        ? bip.raw.preamble.requires.split(',').map(dep => dep.trim())  // Split and trim each dependency
        : bip.raw.preamble.requires;   // Leave it as-is if it's already an array
    
      // Now loop through the array
      requiresArray.forEach(dep => {
        const normalizedDepId = dep.replace(/^BIP-/, ''); // Normalize the dependency ID
        links.push({ source: normalizedBipId, target: normalizedDepId, value: 1 });
      });
    } else {
      console.warn('require field is empty');
    }
  } else {
    console.warn('Malformed or missing bip data:', bip);
  }
});

// Step 6: Return the network data for visualization
const data = { nodes, links };

console.log('Network Diagram Data:', data);

export default data;
