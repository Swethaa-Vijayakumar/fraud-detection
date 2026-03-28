// src/App.jsx

import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-[#04060f]">

        {/* ✅ Sidebar Component */}
        <Sidebar />

        {/* ✅ Main Content */}
        <main className="flex-1 p-8 overflow-y-auto">
          
          {/* Top Header */}
          <header className="mb-8 border-b border-[#1a2540] pb-4">
            <h2 className="text-[11px] text-[#4a5a7a] font-mono tracking-widest">
              FRAUD_LINK ENGINE // LIVE_MONITOR
            </h2>
          </header>

          {/* Routes */}
          <Routes>
            <Route path="/" element={<Dashboard />} />
          </Routes>

        </main>

      </div>
    </BrowserRouter>
  );
}