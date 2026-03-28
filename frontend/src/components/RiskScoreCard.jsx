export default function RiskScoreCard({ score }) {
  const getColor = (s) => s > 70 ? 'text-red-600' : s > 40 ? 'text-orange-500' : 'text-green-500';
  const getBg = (s) => s > 70 ? 'bg-red-50' : s > 40 ? 'bg-orange-50' : 'bg-green-50';

  return (
    <div className={`p-6 rounded-xl border ${getBg(score)} flex flex-col items-center justify-center text-center`}>
      <h4 className="text-gray-600 font-semibold mb-2">Account Risk Score</h4>
      <div className={`text-5xl font-black ${getColor(score)}`}>{score}%</div>
      <p className="mt-2 text-sm text-gray-500 italic">
        {score > 70 ? "High probability of fraudulent activity" : "Account appears stable"}
      </p>
    </div>
  );
}