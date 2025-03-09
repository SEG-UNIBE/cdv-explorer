function initialize_bar_chart(){
  var margin = {top: 30, right: 30, bottom: 70, left: -11},
  width = 750 - margin.left - margin.right,
  height = 425 - margin.top - margin.bottom;

// append the svg object to the body of the page
var svg = d3.select("#bip-plot")
.append("svg")
  .attr("width", width + margin.left + margin.right)
  .attr("height", height + margin.top + margin.bottom)
.append("g")
  .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

// Parse the Data
d3.csv("sample.csv", function(data) {
// sort data
data.sort(function(a, b) { return b.Anteil_Elektroautos - a.Anteil_Elektroautos; });

// X axis
var x = d3.scale.ordinal()
  .rangeRoundBands([0, width], 0.2)
  .domain(data.map(function(d) { return d.Kanton; }));

svg.append("g")
  .attr("class", "x axis")
  .attr("transform", "translate(0," + height + ")")
  .call(d3.svg.axis()
    .scale(x)
    .orient("bottom"))
  .selectAll("text")
    .style("text-anchor", "middle")
    .style("font-size","16px")


// Add Y axis
var y = d3.scale.linear()
  .domain([0, 5])
  .range([height, 0]);

svg.append("g")
  .attr("class", "y axis")
  .call(d3.svg.axis()
    .scale(y)
    .orient("left"));

// Bars
var bar = svg.selectAll(".bar")
  .data(data)
  .enter().append("rect")
    .attr("class", "bar")
    .attr("x", function(d) { return x(d.Kanton); })
    .attr("width", x.rangeBand())
    .attr("y", function(d) { return y(d.Anteil_Elektroautos); })
    .attr("height", function(d) { return height - y(d.Anteil_Elektroautos); })
    .style("fill", "#0096FF")
    .on('mouseover', function (d, i){
      d3.selectAll(".bar").transition()
      .duration('50')
      .attr('opacity', '0.5')
      d3.select(this).transition()
          .duration('50')
          .attr('opacity', '1')
        })     
    .on('mouseout', function (d, i) {
    d3.selectAll(".bar").transition()
          .duration('50')
          .attr('opacity', '1')
        })
    

svg.selectAll(".barText")
    .data(data)                                 
    .enter().append("text")
    .attr("class", "barlabel")
    .attr("x", function(d) { return x(d.Kanton) + x.rangeBand()/7  })
    .attr("y", function(d) { return y(d.Anteil_Elektroautos) - 5 })
    .text(function(d) { return d.Anteil_Elektroautos; })
    .style("font-size","13px")
         //Our new hover effects
    
    
  })
}