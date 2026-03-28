const mockData = {
  stats: { totalTransactions: "12,450", fraudAlerts: 24, flaggedVolume: "$45,200", avgRisk: "12%" },
  alerts: [
    { id: 1, type: 'High Risk', account: 'ACC-9921', amount: '$4,200', time: '2 mins ago', status: 'Pending' },
    { id: 2, type: 'Suspicious Login', account: 'ACC-4410', amount: '$0', time: '15 mins ago', status: 'Reviewing' },
    { id: 3, type: 'Large Transfer', account: 'ACC-1209', amount: '$12,000', time: '1 hour ago', status: 'Resolved' },
  ],
  graphData: [
    { name: 'Mon', transactions: 400, fraud: 24 },
    { name: 'Tue', transactions: 300, fraud: 13 },
    { name: 'Wed', transactions: 500, fraud: 35 },
    { name: 'Thu', transactions: 280, fraud: 10 },
    { name: 'Fri', transactions: 590, fraud: 40 },
  ]
};

export const api = {
  getStats: () => Promise.resolve(mockData.stats),
  getAlerts: () => Promise.resolve(mockData.alerts),
  getGraphData: () => Promise.resolve(mockData.graphData),
  getAccountDetail: (id) => Promise.resolve({
    id,
    name: "Alex Thompson",
    email: "alex.t@example.com",
    riskScore: 72,
    history: [
      { id: 101, date: '2026-03-20', merchant: 'Global Tech Store', amount: '$2,500', status: 'Flagged' },
      { id: 102, date: '2026-03-19', merchant: 'Coffee House', amount: '$12.50', status: 'Cleared' },
    ]
  })
};