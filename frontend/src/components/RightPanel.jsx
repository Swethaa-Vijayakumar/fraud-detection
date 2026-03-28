import React from 'react';
import './RightPanel.css';

export default function RightPanel() {
  return (
    <aside className="right-panel">
      <div className="risk-score-box card">
        <h3>Network Risk Score</h3>
        <div className="score-circle">
          <span className="score-val">84%</span>
          <svg viewBox="0 0 36 36" className="circular-chart red">
            <path className="circle" strokeDasharray="84, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
          </svg>
        </div>
        <p className="status-text">CRITICAL THREAT LEVEL</p>
      </div>

      <div className="velocity-box card">
        <div className="flex-row">
          <h3>Velocity</h3>
          <span className="val text-blue">142 TX/m</span>
        </div>
        <div className="flex-row">
          <h3>Anomalies</h3>
          <span className="val text-red">22 Det.</span>
        </div>
      </div>

      <div className="recent-alerts card">
        <h3 className="mb-10">Neural Log</h3>
        <div className="log-entry">
          <span className="time">14:02</span>
          <p>Heuristic match: Cluster-9 Dispersion</p>
        </div>
        <div className="log-entry">
          <span className="time">13:58</span>
          <p>IP Geolocation mismatch: ACC-221</p>
        </div>
        <div className="log-entry highlight">
          <span className="time">13:45</span>
          <p>Rapid fund exit detected ($12k)</p>
        </div>
      </div>
    </aside>
  );
}