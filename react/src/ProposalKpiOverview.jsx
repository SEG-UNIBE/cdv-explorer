import React from 'react';
import { Card } from 'primereact/card';
import {
  FaFileAlt,
  FaCogs,
  FaLock,
  FaHandshake,
  FaNetworkWired,
  FaBolt
} from 'react-icons/fa';

import 'primeicons/primeicons.css';

export const ProposalKpiOverview = ({ data, totalLabel = 'Total Proposals' }) => {
  if (!data || !data.nodes || data.nodes.length === 0) {
    return <p>No proposal data available.</p>;
  }

  const nodes = data.nodes;
  const totalCount = nodes.length;
  const maxLayerCards = 5;

  const iconSize = '6em';
  const valueStyle = { fontSize: '4rem', fontWeight: 'bold', marginTop: '0.5rem' };
  const labelStyle = { fontSize: '2rem', color: '#555' };
  const cardStyle = { flex: '1 1 200px', textAlign: 'center' };

  const layerCountMap = nodes.reduce((acc, node) => {
    const layer = (node.layer || 'Unknown').trim() || 'Unknown';
    acc[layer] = (acc[layer] || 0) + 1;
    return acc;
  }, {});

  const topLayers = Object.entries(layerCountMap)
    .map(([layer, count]) => ({ layer, count }))
    .sort((a, b) => b.count - a.count || a.layer.localeCompare(b.layer))
    .slice(0, maxLayerCards);

  const layerIcons = [FaCogs, FaLock, FaHandshake, FaNetworkWired, FaBolt];

  return (
    <div>
      <div className="kpi" style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem', alignItems: 'center' }}>
        <Card style={cardStyle}>
          <FaFileAlt size={iconSize} />
          <div className="value" style={valueStyle}>{totalCount}</div>
          <div className="label" style={labelStyle}>{totalLabel}</div>
        </Card>
        {topLayers.map((entry, index) => {
          const Icon = layerIcons[index % layerIcons.length];
          return (
            <Card key={entry.layer} style={cardStyle}>
              <Icon size={iconSize} />
              <div className="value" style={valueStyle}>{entry.count}</div>
              <div className="label" style={labelStyle}>{entry.layer}</div>
            </Card>
          );
        })}
      </div>

      <br /><br />
    </div>
  );
};
