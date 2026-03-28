import React, { useState } from 'react';
import { 
  LayoutDashboard, Share2, Activity, ShieldAlert, 
  Landmark, Smartphone, Wallet, CreditCard, 
  FileText, Briefcase, Settings 
} from 'lucide-react';
import './Sidebar.css';

const Sidebar = () => {
  const [activeItem, setActiveItem] = useState('Dashboard');

  const menuItems = [
    { id: 'Dashboard', label: 'Dashboard', icon: LayoutDashboard, section: 'MAIN' },
    { id: 'Graph', label: 'Graph Network', icon: Share2, section: 'MAIN' },
    { id: 'Neural', label: 'Neural Networks', icon: Activity, section: 'MAIN' },
    { id: 'Risk', label: 'Risk Scoring Panel', icon: ShieldAlert, section: 'MAIN' },
    
    { id: 'Bank', label: 'Bank Transactions', icon: Landmark, section: 'CHANNELS' },
    { id: 'UPI', label: 'UPI Payments', icon: Smartphone, section: 'CHANNELS' },
    { id: 'Wallets', label: 'Digital Wallets', icon: Wallet, section: 'CHANNELS' },
    { id: 'Online', label: 'Online Payments', icon: CreditCard, section: 'CHANNELS' },
    
    { id: 'AML', label: 'AML Reports', icon: FileText, section: 'COMPLIANCE' },
    { id: 'Case', label: 'Case Management', icon: Briefcase, section: 'COMPLIANCE' },
    { id: 'Settings', label: 'Settings', icon: Settings, section: 'COMPLIANCE' },
  ];

  const renderSection = (sectionName) => (
    <div className="sidebar-section">
      <p className="section-title">{sectionName}</p>
      {menuItems
        .filter((item) => item.section === sectionName || (sectionName === "INVESTIGATION" && item.section === "MAIN"))
        .map((item) => {
          const Icon = item.icon;
          const isActive = activeItem === item.id;
          return (
            <div 
              key={item.id} 
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => setActiveItem(item.id)}
            >
              <Icon size={18} className="nav-icon" />
              <span>{item.label}</span>
              {isActive && <div className="active-glow" />}
            </div>
          );
        })}
    </div>
  );

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo-container">
          <div className="logo-hex">🕸️</div>
          <h1 className="logo-text">FraudLink <span className="text-cyan">AI</span></h1>
        </div>
      </div>

      <div className="sidebar-content">
        {renderSection('INVESTIGATION')}
        {renderSection('CHANNELS')}
        {renderSection('COMPLIANCE')}
      </div>

      <div className="sidebar-footer">
        <div className="status-box">
          <div className="status-dot animate-pulse"></div>
          <span>ENGINE LIVE · V2.4.1</span>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;