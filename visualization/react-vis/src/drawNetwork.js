import { data } from './data'; // Assuming data.js is exporting data
import * as d3 from 'd3'; 

export const RADIUS = 10;

// Define a color scale (using d3's scaleOrdinal with a color scheme)
const colorScale = d3.scaleOrdinal(d3.schemeCategory10); 

export const drawNetwork = (context, width, height, nodes, links) => {
  context.clearRect(0, 0, width, height);

  // Draw the links first
  links.forEach((link) => {
    context.beginPath();
    context.moveTo(link.source.x, link.source.y);
    context.lineTo(link.target.x, link.target.y);

    // Set the color and opacity for the links
    context.strokeStyle = '#999';  // Set link color to #999
    context.globalAlpha = 0.6;     // Set opacity to 0.6

    context.stroke();
  });
  context.globalAlpha = 1; // Reset opacity to fully opaque for nodes
  // Draw the nodes
  nodes.forEach((node) => {
    if (!node.x || !node.y) {
      return;
    }

    context.beginPath();
    context.moveTo(node.x + RADIUS, node.y);
    context.arc(node.x, node.y, RADIUS, 0, 2 * Math.PI);

    // Set color based on the node's layer using the color scale
    context.fillStyle = colorScale(node.group); // Color will be assigned based on the node's layer
    context.fill();
  });
};

