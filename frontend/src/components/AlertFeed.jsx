import { Link } from 'react-router-dom';

export default function AlertFeed({ alerts }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="p-4 border-b border-gray-50 bg-gray-50/50">
        <h3 className="font-bold text-gray-700">Recent Fraud Alerts</h3>
      </div>
      <div className="divide-y divide-gray-100">
        {alerts.map((alert) => (
          <Link key={alert.id} to={`/account/${alert.account}`} className="block p-4 hover:bg-gray-50 transition">
            <div className="flex justify-between items-center">
              <div>
                <p className="font-medium text-gray-900">{alert.type}</p>
                <p className="text-xs text-gray-500">{alert.account} • {alert.time}</p>
              </div>
              <div className="text-right">
                <p className="font-bold text-red-600">{alert.amount}</p>
                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                  {alert.status}
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}