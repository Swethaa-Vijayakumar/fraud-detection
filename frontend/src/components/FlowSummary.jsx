import React from 'react';
import { ArrowRight, AlertTriangle } from 'lucide-react';
import './FlowSummary.css';

export default function FlowSummary() {
  const flows = [
    { sender: "User_8821", receiver: "Mule_99", amount: "$4,500", time: "14:20:01", risk: "CRITICAL" },
    { sender: "Mule_99", receiver: "Offshore_X", amount: "$4,480", time: "14:20:45", risk: "CRITICAL" }
  ];

  return (
    <div className="flow-card card">
      <h3 className="card-title">Money Laundering Trail</h3>
      <div className="flow-list">
        {flows.map((f, i) => (
          <div key={i} className="flow-item">
            <div className="flow-top">
              <span className="node-id">{f.sender}</span>
              <ArrowRight size={14} className="flow-arrow" />
              <span className="node-id">{f.receiver}</span>
            </div>
            <div className="flow-details">
              <span className="flow-amt">{f.amount}</span>
              <span className="flow-time">{f.time}</span>
              <span className="flow-badge">{f.risk}</span>
            </div>
          </div>
        ))}
        <div className="alert-box">
          <AlertTriangle size={18} />
          <p>Potential Layering Pattern Detected</p>
        </div>
      </div>
    </div>
  );
}