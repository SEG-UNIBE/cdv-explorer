import React from 'react';
import { Card } from 'primereact/card';
import {
  FaFileAlt,        // For "Total BIPs"
  FaCogs,           // For "Applications"
  FaLock,           // For "Consensus (soft fork)"
  FaHandshake,      // For "Peer Services"
  FaNetworkWired,   // For "API/RPC"
  FaBolt            // For "Consensus (hard fork)"
} from 'react-icons/fa';

import 'primeicons/primeicons.css';

export const BipKpiOverview = ({ data }) => {
  if (!data || !data.nodes || data.nodes.length === 0) {
    return <p>No BIP data available.</p>;
  }

  const nodes = data.nodes;
  const totalCount = nodes.length;

  const iconSize = "6em";
  const valueStyle = { fontSize: '4rem', fontWeight: 'bold', marginTop: '0.5rem' };
  const labelStyle = { fontSize: '2rem', color: '#555' };
  const cardStyle = { flex: '1 1 200px', textAlign: 'center' };

  const applicationCount = nodes.filter(node => node.group === 'Applications').length;
  const softForkCount = nodes.filter(node => node.group === 'Consensus (soft fork)').length;
const peerServicesCount = nodes.filter(node => node.group === 'Peer Services').length;
const apiRpcCount = nodes.filter(node => node.group === 'API/RPC').length;
const hardForkCount = nodes.filter(node => node.group === 'Consensus (hard fork)').length;


  return (
    <div>
      <div className="kpi" style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem', alignItems: 'center' }}>
        <Card style={cardStyle}>
          <FaFileAlt size={iconSize} />
          <div className="value" style={valueStyle}>{totalCount}</div>
          <div className="label" style={labelStyle}>Total BIPs</div>
        </Card>
        <Card style={cardStyle}>
          <FaCogs size={iconSize} />
          <div className="value" style={valueStyle}>{applicationCount}</div>
          <div className="label" style={labelStyle}>Applications</div>
        </Card>
        <Card style={cardStyle}>
          <FaLock size={iconSize} />
          <div className="value" style={valueStyle}>{softForkCount}</div>
          <div className="label" style={labelStyle}>Consensus (soft fork)</div>
        </Card>
      </div>

      <br /><br />

      <div className="kpi" style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem', alignItems: 'center' }}>
        <Card style={cardStyle}>
          <FaHandshake size={iconSize} />
          <div className="value" style={valueStyle}>{peerServicesCount}</div>
          <div className="label" style={labelStyle}>Peer Services</div>
        </Card>
        <Card style={cardStyle}>
          <FaNetworkWired size={iconSize} />
          <div className="value" style={valueStyle}>{apiRpcCount}</div>
          <div className="label" style={labelStyle}>API/RPC</div>
        </Card>
        <Card style={cardStyle}>
          <FaBolt size={iconSize} />
          <div className="value" style={valueStyle}>{hardForkCount}</div>
          <div className="label" style={labelStyle}>Consensus (hard fork)</div>
        </Card>
      </div>

      <br /><br />
    </div>
  );
};
