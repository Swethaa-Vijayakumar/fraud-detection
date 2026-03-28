import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function GraphView({ data }) {
  return (
    <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm h-80">
      <h3 className="font-bold text-gray-700 mb-4">Transaction vs. Fraud Trends</h3>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="transactions" stroke="#3b82f6" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="fraud" stroke="#ef4444" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}