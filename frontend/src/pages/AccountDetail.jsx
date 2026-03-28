import { useParams, Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { ArrowLeft, User, Mail, ShieldCheck } from 'lucide-react';

export default function AccountDetail() {
  const { id } = useParams();
  const [account, setAccount] = useState(null);

  useEffect(() => {
    api.getAccountDetail(id).then(setAccount);
  }, [id]);

  if (!account) return <div className="p-10">Loading account...</div>;

  return (
    <div className="max-w-4xl mx-auto">
      <Link to="/" className="flex items-center gap-2 text-blue-600 mb-6 font-medium">
        <ArrowLeft size={18} /> Back to Dashboard
      </Link>
      
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="p-8 bg-gradient-to-r from-slate-800 to-slate-900 text-white">
          <h2 className="text-3xl font-bold">{account.name}</h2>
          <p className="opacity-80">ID: {account.id}</p>
        </div>
        
        <div className="p-8 grid md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-gray-700">
              <Mail size={20} className="text-gray-400" /> {account.email}
            </div>
            <div className="flex items-center gap-3 text-gray-700">
              <ShieldCheck size={20} className="text-gray-400" /> 
              Security Status: <span className="font-bold text-red-500">Flagged</span>
            </div>
          </div>
          
          <div className="bg-gray-50 p-4 rounded-xl text-center">
            <p className="text-sm text-gray-500 font-bold uppercase">Risk Level</p>
            <p className="text-4xl font-black text-red-600">{account.riskScore}%</p>
          </div>
        </div>

        <div className="border-t border-gray-100 p-8">
          <h3 className="font-bold text-gray-800 mb-4">Transaction History</h3>
          <table className="w-full text-left">
            <thead>
              <tr className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                <th className="pb-4">Date</th>
                <th className="pb-4">Merchant</th>
                <th className="pb-4 text-right">Amount</th>
                <th className="pb-4 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {account.history.map(tx => (
                <tr key={tx.id} className="text-sm">
                  <td className="py-3 text-gray-600">{tx.date}</td>
                  <td className="py-3 font-medium text-gray-800">{tx.merchant}</td>
                  <td className="py-3 text-right font-bold">{tx.amount}</td>
                  <td className="py-3 text-right">
                    <span className={`px-2 py-1 rounded-md text-[10px] font-bold ${tx.status === 'Flagged' ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'}`}>
                      {tx.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}