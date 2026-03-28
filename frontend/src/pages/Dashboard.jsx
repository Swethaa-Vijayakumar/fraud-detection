import "./dashboard.css";

const Dashboard = () => {
  return (
    <div className="app">
      
      {/* Sidebar */}
      <div className="sidebar">
        <h2>FraudLink AI</h2>
        <ul>
          <li className="active">Dashboard</li>
          <li>Settings</li>
        </ul>
      </div>

      {/* Main Content */}
      <div className="main">
        <h1>System Overview</h1>
        <p>Real-time fraud detection metrics.</p>

        {/* Stats */}
        <div className="stats">
          <div className="card">
            <h3>Total TXs</h3>
            <p>12,450</p>
          </div>

          <div className="card">
            <h3>Fraud Alerts</h3>
            <p>24</p>
          </div>

          <div className="card">
            <h3>Flagged Vol</h3>
            <p>$45,200</p>
          </div>

          <div className="card">
            <h3>Avg Risk</h3>
            <p>12%</p>
          </div>
        </div>

        {/* Upload */}
        <div className="card">
          <h3>Analyze Transaction Batch</h3>
          <p>Upload .CSV or .JSON files</p>
          <button>Choose File</button>
        </div>

        {/* Risk Score */}
        <div className="card">
          <h3>Account Risk Score</h3>
          <p className="low-risk">42% - Account appears stable</p>
        </div>

        {/* Alerts */}
        <div className="card">
          <h3>Recent Fraud Alerts</h3>
          <ul>
            <li>High Risk ACC-9921 - $4,200 (Pending)</li>
            <li>Suspicious Login ACC-4410 - $0 (Reviewing)</li>
            <li>Large Transfer ACC-1209 - $12,000 (Resolved)</li>
          </ul>
        </div>

      </div>
    </div>
  );
};

export default Dashboard;