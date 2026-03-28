import { ShieldAlert, BarChart3, CreditCard, Activity } from 'lucide-react';

const StatCard = ({ title, value, icon: Icon, color }) => (
  <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm flex items-center gap-4">
    <div className={`p-3 rounded-lg ${color}`}>
      <Icon size={24} className="text-white" />
    </div>
    <div>
      <p className="text-sm text-gray-500 font-medium">{title}</p>
      <h3 className="text-2xl font-bold text-gray-800">{value}</h3>
    </div>
  </div>
);

export default function StatsSummary({ stats }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <StatCard title="Total TXs" value={stats.totalTransactions} icon={Activity} color="bg-blue-500" />
      <StatCard title="Fraud Alerts" value={stats.fraudAlerts} icon={ShieldAlert} color="bg-red-500" />
      <StatCard title="Flagged Vol" value={stats.flaggedVolume} icon={CreditCard} color="bg-orange-500" />
      <StatCard title="Avg Risk" value={stats.avgRisk} icon={BarChart3} color="bg-purple-500" />
    </div>
  );
}