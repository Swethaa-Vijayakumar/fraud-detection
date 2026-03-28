import React from 'react';
import './MetricCards.css';

const Card = ({ title, value, sub, color }) => (
  <div className={`metric-card ${color}`}>
    <p className="card-title">{title}</p>
    <h2 className="card-value">{value}</h2>
    <p className="card-sub">{sub}</p>
  </div>
);

export default function MetricCards() {
  return (
    <div className="metrics-row">
      <Card title="Flagged Nodes" value="1,284" sub="+12% Critical" color="red" />
      <Card title="Active Scans" value="45.2k" sub="Real-time" color="blue" />
      <Card title="Neural Matches" value="84" sub="GNN Predicted" color="purple" />
      <Card title="Blocked Volume" value="₹14.2M" sub="Recovered" color="green" />
    </div>
  );
}