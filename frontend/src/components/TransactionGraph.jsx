import React, { useEffect, useRef } from 'react';
import { Network } from 'vis-network';
import './TransactionGraph.css';

export default function TransactionGraph() {
  const container = useRef(null);

  useEffect(() => {
    const data = {
      nodes: [
        { id: 1, label: 'Target', color: '#ff3d6b', size: 30 },
        { id: 2, label: 'Mule-A', color: '#00d4ff' },
        { id: 3, label: 'Mule-B', color: '#00d4ff' },
        { id: 4, label: 'Safe', color: '#22c55e' }
      ],
      edges: [
        { from: 1, to: 2, label: '₹50k', color: '#ff3d6b' },
        { from: 1, to: 3, label: '₹20k', color: '#ff3d6b' },
        { from: 1, to: 4, label: '₹100', color: '#4a5a7a' }
      ]
    };
    const options = {
      physics: { enabled: true },
      nodes: { font: { color: '#fff', face: 'JetBrains Mono' } }
    };
    new Network(container.current, data, options);
  }, []);

  return (
    <div className="graph-box">
      <div className="graph-label">🕸️ LIVE TRANSACTION GRAPH</div>
      <div ref={container} className="vis-area" />
    </div>
  );
}