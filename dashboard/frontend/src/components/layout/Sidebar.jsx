import React from 'react';
import {
  LayoutDashboard,
  Search,
  Network,
  ArrowLeftRight,
  BrainCircuit,
  Server,
  ShieldCheck,
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'investigations', label: 'Investigations', icon: Search },
  { id: 'clusters', label: 'Risk Clusters', icon: Network },
  { id: 'transactions', label: 'Transactions', icon: ArrowLeftRight },
  { id: 'models', label: 'Model Intelligence', icon: BrainCircuit },
  { id: 'system', label: 'System', icon: Server },
];

export default function Sidebar({ currentPage, onNavigate }) {
  return (
    <aside className="w-64 bg-[#EAE8E0] border-r border-[#E2E0D8] flex flex-col justify-between h-screen fixed left-0 top-0 select-none z-30">
      {/* Brand Header */}
      <div>
        <div className="p-5 border-b border-[#E2E0D8] flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#147D69] flex items-center justify-center shadow-sm flex-shrink-0">
            <svg
              className="w-5 h-5 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {/* Shield Silhouette */}
              <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
              {/* AI Network Nexus / Risk Node Core */}
              <circle cx="12" cy="11.5" r="2.5" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="12" cy="11.5" r="0.9" fill="currentColor" stroke="none" />
              <path d="M12 7.2v1.8M9.2 13.8l1.4-1.1M14.8 13.8l-1.4-1.1" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </div>
          <div className="flex flex-col justify-center min-w-0">
            <div className="font-sans text-[13.5px] tracking-wider flex items-center gap-1.5 leading-none">
              <span className="font-bold text-[#252B29]">RING</span>
              <span className="font-extrabold text-[#147D69]">SENTINEL</span>
            </div>
            <div className="text-[9.5px] uppercase tracking-[0.16em] text-[#737A76] font-semibold font-sans mt-1 leading-none">
              AI RISK INTELLIGENCE
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="p-3 space-y-1 mt-2">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = currentPage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 text-left ${
                  isActive
                    ? 'bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30 shadow-sm'
                    : 'text-[#737A76] hover:text-[#3D4543] hover:bg-[#F3F1EB] border border-transparent'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-[#147D69]' : 'text-[#737A76]'}`} />
                <span>{item.label}</span>
                {isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[#147D69]" />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer System Status */}
      <div className="p-4 border-t border-[#E2E0D8]">
        <div className="bg-white border border-[#E2E0D8] rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-[#147D69]" />
            <span className="text-[11px] font-semibold text-[#252B29] uppercase tracking-wider">
              Prototype Active
            </span>
          </div>
          <p className="text-[10px] text-[#737A76] leading-relaxed">
            10K Accounts • Synthetic Benchmark
          </p>
          <div className="mt-2 text-[9px] font-mono text-[#737A76] border-t border-[#E2E0D8] pt-1.5">
            Defensive SOC • Non-Blocking
          </div>
        </div>
      </div>
    </aside>
  );
}
