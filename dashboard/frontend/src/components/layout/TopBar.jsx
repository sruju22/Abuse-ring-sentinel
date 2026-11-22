import React, { useState, useEffect } from 'react';
import {
  Search,
  Clock,
  ShieldAlert,
  ChevronRight,
  LayoutDashboard,
  Network,
  ArrowLeftRight,
  BrainCircuit,
  Server,
} from 'lucide-react';

const PAGE_META = {
  overview: { label: 'Overview', icon: LayoutDashboard },
  investigations: { label: 'Investigations', icon: Search },
  clusters: { label: 'Risk Clusters', icon: Network },
  transactions: { label: 'Transactions', icon: ArrowLeftRight },
  models: { label: 'Model Intelligence', icon: BrainCircuit },
  system: { label: 'System Architecture', icon: Server },
};

export default function TopBar({
  currentPage = 'overview',
  selectedAccountId = null,
  selectedClusterId = null,
  onNavigate,
  onSearchAccount,
  highRiskCount = 436,
}) {
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

  const currentMeta = PAGE_META[currentPage] || PAGE_META.overview;
  const CurrentIcon = currentMeta.icon;

  return (
    <header className="h-14 bg-white/90 backdrop-blur-sm border-b border-[#E2E0D8] flex items-center justify-between px-6 fixed top-0 right-0 left-64 z-20">
      {/* Dynamic Breadcrumbs & Operational Status */}
      <div className="flex items-center gap-2.5">
        <button
          onClick={() => onNavigate && onNavigate('overview')}
          className="text-xs font-semibold text-[#737A76] hover:text-[#252B29] transition-colors flex items-center gap-1.5 font-sans"
        >
          <span>Ring Sentinel</span>
        </button>

        <ChevronRight className="w-3.5 h-3.5 text-[#9BA09D]" />

        <div className="flex items-center gap-1.5 text-xs font-bold text-[#252B29] font-sans">
          <CurrentIcon className="w-3.5 h-3.5 text-[#147D69]" />
          <span>{currentMeta.label}</span>
        </div>

        {currentPage === 'investigations' && selectedAccountId && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-[#9BA09D]" />
            <span className="font-mono text-xs font-bold text-[#147D69] px-2 py-0.5 rounded bg-[#147D69]/10 border border-[#147D69]/20">
              {selectedAccountId}
            </span>
          </>
        )}

        {currentPage === 'clusters' && selectedClusterId && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-[#9BA09D]" />
            <span className="font-mono text-xs font-bold text-[#147D69] px-2 py-0.5 rounded bg-[#147D69]/10 border border-[#147D69]/20">
              {selectedClusterId}
            </span>
          </>
        )}

        <div className="ml-2 hidden sm:flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-[#147D69]/10 border border-[#147D69]/25 text-[#147D69] text-[10px] font-medium font-sans">
          <span className="w-1.5 h-1.5 rounded-full bg-[#147D69] animate-status-pulse" />
          <span>Engine Operational</span>
        </div>
      </div>

      {/* Global Search and Metadata Controls */}
      <div className="flex items-center gap-4">
        {/* Global Search */}
        <form onSubmit={handleSearchSubmit} className="relative">
          <Search className="w-3.5 h-3.5 text-[#737A76] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search Account ID (e.g. ACC_009754)..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-60 md:w-64 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg pl-8 pr-3 py-1.5 text-xs text-[#252B29] placeholder-[#9BA09D] focus:outline-none focus:border-[#147D69] focus:ring-1 focus:ring-[#147D69] transition-all font-mono"
          />
        </form>

        {/* Priority Review Alert Pill (Clickable Shortcut) */}
        <button
          onClick={() => onNavigate && onNavigate('investigations')}
          title="Click to open escalated accounts in investigations workspace"
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#C64B43]/10 hover:bg-[#C64B43]/20 border border-[#C64B43]/25 text-[#C64B43] text-xs font-mono font-medium transition-colors cursor-pointer"
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>{highRiskCount} Escalated</span>
        </button>

        {/* Live Timestamp */}
        <div className="hidden lg:flex items-center gap-1.5 text-[11px] font-mono text-[#737A76] border-l border-[#E2E0D8] pl-4">
          <Clock className="w-3 h-3 text-[#737A76]" />
          <span>{timeString || 'UTC Live'}</span>
        </div>
      </div>
    </header>
  );
}
