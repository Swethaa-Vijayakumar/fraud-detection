import { Upload, FileText } from 'lucide-react';

export default function UploadPanel() {
  return (
    <div className="bg-white p-6 rounded-xl border-2 border-dashed border-gray-200 flex flex-col items-center justify-center text-center">
      <div className="bg-blue-50 p-4 rounded-full mb-4">
        <Upload className="text-blue-600" size={32} />
      </div>
      <h3 className="font-bold text-gray-800">Analyze Transaction Batch</h3>
      <p className="text-sm text-gray-500 mb-4">Upload .CSV or .JSON files for instant AI scanning</p>
      <button className="bg-blue-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-blue-700 transition">
        Choose File
      </button>
    </div>
  );
}