import * as d3 from 'd3'; 

export const RADIUS = 10;

// Define a color scale (using d3's scaleOrdinal with a color scheme)
const colorScale = d3.scaleOrdinal(d3.schemeCategory10); 

export const drawNetwork = (svg, width, height, nodes, links) => {
  // Clear any existing content in the SVG
  svg.selectAll("*").remove(); // Remove all existing SVG elements

  // Set the dimensions of the SVG container
  svg.attr("width", width)
     .attr("height", height);

  // Run the D3 force simulation to calculate node positions
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(100))  // Apply a link force
    .force('collide', d3.forceCollide().radius(RADIUS + 5))           // Apply collision force
    .force('charge', d3.forceManyBody())                              // Apply repulsion between nodes
    .force('center', d3.forceCenter(width / 2, height / 2))            // Center the graph
    .on('tick', ticked);                                               // Update the positions on each tick

  // Draw the links (lines between nodes)
  const link = svg.append("g")
    .attr("class", "links")
    .selectAll("line")
    .data(links)
    .enter()
    .append("line")
    .attr("stroke", "#999")
    .attr("stroke-opacity", 0.6)
    .attr("stroke-width", 1);

  // Draw the nodes (circles)
  const node = svg.append("g")
    .attr("class", "nodes")
    .selectAll("circle")
    .data(nodes)
    .enter()
    .append("circle")
    .attr("r", RADIUS)
    .attr("fill", d => colorScale(d.group));

  // Add titles to nodes (optional, shows the node id on hover)
  node.append("title")
    .text(d => d.id);

  // Define the tick function which is called on every tick of the simulation
  function ticked() {
    // Update the link positions
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);

    // Update the node positions
    node
      .attr("cx", d => d.x)
      .attr("cy", d => d.y);
  }
};
