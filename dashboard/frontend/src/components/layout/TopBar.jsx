import React, { useState, useEffect } from 'react';
import { Search, Bell, Clock, Activity, ShieldAlert } from 'lucide-react';

export default function TopBar({ onSearchAccount, highRiskCount = 233 }) {
  const [searchInput, setSearchInput] = useState('');
  const [timeString, setTimeString] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeString(now.toUTCString().replace('GMT', 'UTC'));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchInput.trim()) {
      onSearchAccount(searchInput.trim());
      setSearchInput('');
    }
  };

  return (
    <header className="h-14 bg-[#0B0F19]/90 backdrop-blur-md border-b border-[#1E293B] flex items-center justify-between px-6 fixed top-0 right-0 left-64 z-20">
      {/* Title and Active Status */}
      <div className="flex items-center gap-3">
        <h1 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-cyan-400" />
          Risk Operations Center
        </h1>
        <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/25 text-cyan-300 text-[10px] font-mono font-medium">
          <span>Synthetic Benchmark</span>
        </div>
        <div className="flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-status-pulse" />
          <span>Engine Operational</span>
        </div>
      </div>

      {/* Search and Metadata Controls */}
      <div className="flex items-center gap-4">
        {/* Global Search */}
        <form onSubmit={handleSearchSubmit} className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search Account ID (e.g. ACC_009937)..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-64 bg-[#111726] border border-[#1E293B] rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all font-mono"
          />
        </form>

        {/* Priority Review Alert Pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-mono font-medium">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>{highRiskCount} Escalated</span>
        </div>

        {/* Live Timestamp */}
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 border-l border-[#1E293B] pl-4">
          <Clock className="w-3 h-3 text-slate-400" />
          <span>{timeString || 'UTC Live'}</span>
        </div>
      </div>
    </header>
  );
}
