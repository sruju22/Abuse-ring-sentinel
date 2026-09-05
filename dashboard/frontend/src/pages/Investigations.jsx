import React, { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  Shield,
  ShieldAlert,
  AlertTriangle,
  Bot,
  Clock,
  Target,
  Network,
  Zap,
  CheckCircle,
  Smartphone,
  Globe,
  ArrowRight,
  ExternalLink,
  IndianRupee,
  Activity,
  ChevronRight,
  ChevronLeft,
  UserCheck,
  FileText,
  XCircle,
  AlertCircle,
  Eye,
  History,
  Send,
  RotateCcw,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';
import NetworkGraph from '../components/graph/NetworkGraph';
import { formatINR } from '../utils/currency';

const REASON_ICONS = {
  HIGH_ML_RISK: Bot,
  STRONG_TIMING_COORDINATION: Clock,
  STRONG_AMOUNT_SIMILARITY: IndianRupee,
  DESTINATION_CONCENTRATION: Target,
  STRONG_GRAPH_CLUSTER: Network,
  SHARED_INFRASTRUCTURE: Smartphone,
  HIGH_TRANSACTION_VELOCITY: Zap,
  STANDARD_ACTIVITY: CheckCircle,
};

export default function Investigations({ selectedAccountId, onSelectAccount, onNavigate }) {
  // Navigation / View state
  const [viewMode, setViewMode] = useState('table'); // 'table' or 'detail'
  
  // Filters
  const [search, setSearch] = useState('');
  const [riskLevel, setRiskLevel] = useState('ALL');
  const [minScore, setMinScore] = useState('');
  const [maxScore, setMaxScore] = useState('');
  const [clusterId, setClusterId] = useState('ALL');
  const [evidenceType, setEvidenceType] = useState('ALL');
  const [actionFilter, setActionFilter] = useState('ALL');
  
  // Data state
  const [accounts, setAccounts] = useState([]);
  const [totalAccounts, setTotalAccounts] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loadingList, setLoadingList] = useState(false);

  // Active account deep-dive state
  const [activeAccountId, setActiveAccountId] = useState(selectedAccountId || 'ACC_009937');
  const [activeAccount, setActiveAccount] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Human Review triage state
  const [reviewStatus, setReviewStatus] = useState(null);
  const [analystNotes, setAnalystNotes] = useState('');
  const [auditLogs, setAuditLogs] = useState([]);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  // Fetch accounts list with multi-signal filters
  useEffect(() => {
    let mounted = true;
    setLoadingList(true);
    api
      .getAccounts({
        page,
        pageSize,
        search,
        riskLevel,
        action: actionFilter,
        clusterId,
        minScore: minScore !== '' ? parseFloat(minScore) : undefined,
        maxScore: maxScore !== '' ? parseFloat(maxScore) : undefined,
        evidenceType,
        sortBy: 'final_risk_score',
        sortOrder: 'desc',
      })
      .then((res) => {
        if (mounted) {
          setAccounts(res.items || []);
          setTotalAccounts(res.total || 0);
          setLoadingList(false);

          // If no active account is set, default to first item
          if (!activeAccountId && res.items?.length > 0) {
            setActiveAccountId(res.items[0].account_id);
          }
        }
      })
      .catch(() => {
        if (mounted) setLoadingList(false);
      });
    return () => {
      mounted = false;
    };
  }, [page, pageSize, search, riskLevel, actionFilter, clusterId, minScore, maxScore, evidenceType]);

  // Sync external selectedAccountId prop
  useEffect(() => {
    if (selectedAccountId) {
      setActiveAccountId(selectedAccountId);
      setViewMode('detail');
    }
  }, [selectedAccountId]);

  // Fetch account deep-dive details
  useEffect(() => {
    if (!activeAccountId) return;
    let mounted = true;
    setLoadingDetail(true);
    api
      .getAccountDetail(activeAccountId)
      .then((res) => {
        if (mounted) {
          setActiveAccount(res);
          setReviewStatus(null); // reset local override
          setLoadingDetail(false);
        }
      })
      .catch(() => {
        if (mounted) setLoadingDetail(false);
      });
    return () => {
      mounted = false;
    };
  }, [activeAccountId]);

  // Fetch audit logs
  const refreshAuditLogs = () => {
    api.getAuditLog().then((logs) => {
      setAuditLogs(logs || []);
    }).catch(() => {});
  };

  useEffect(() => {
    refreshAuditLogs();
  }, [activeAccountId]);

  // Handle human review actions
  const handleReviewAction = async (actionType) => {
    if (!activeAccountId) return;
    setIsSubmittingReview(true);
    try {
      await api.addAuditEvent({
        action: actionType,
        target: activeAccountId,
        notes: analystNotes || `Analyst marked account as ${actionType}.`,
        analyst: 'Risk Analyst (Session)',
        severity: actionType === 'ESCALATE' ? 'HIGH' : actionType === 'FALSE_POSITIVE' ? 'LOW' : 'INFO',
      });
      setReviewStatus(actionType);
      setAnalystNotes('');
      refreshAuditLogs();
    } catch (err) {
      console.error('Failed to record audit action:', err);
    } finally {
      setIsSubmittingReview(false);
    }
  };

  const handleAccountClick = (accId) => {
    setActiveAccountId(accId);
    if (onSelectAccount) onSelectAccount(accId);
    setViewMode('detail');
  };

  const handleNextAccount = () => {
    const currentIndex = accounts.findIndex((a) => a.account_id === activeAccountId);
    if (currentIndex >= 0 && currentIndex < accounts.length - 1) {
      handleAccountClick(accounts[currentIndex + 1].account_id);
    }
  };

  const handlePrevAccount = () => {
    const currentIndex = accounts.findIndex((a) => a.account_id === activeAccountId);
    if (currentIndex > 0) {
      handleAccountClick(accounts[currentIndex - 1].account_id);
    }
  };

  const resetFilters = () => {
    setSearch('');
    setRiskLevel('ALL');
    setMinScore('');
    setMaxScore('');
    setClusterId('ALL');
    setEvidenceType('ALL');
    setActionFilter('ALL');
    setPage(1);
  };

  return (
    <div className="space-y-5 pb-12">
      {/* Header Banner & Breadcrumbs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1E293B]/70 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <Search className="w-5 h-5 text-cyan-400" />
              Investigation Workspace
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-[10px] font-mono font-semibold uppercase">
              Explainable Risk Engine
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Account-level behavioral telemetry, verifiable reason signals, topology neighborhood, and defensive triage
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-2 bg-[#111726] border border-[#1E293B] p-1 rounded-lg">
          <button
            onClick={() => setViewMode('table')}
            className={`px-3 py-1.5 rounded text-xs font-mono font-semibold transition-all ${
              viewMode === 'table'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Accounts Table ({totalAccounts?.toLocaleString()})
          </button>
          <button
            onClick={() => setViewMode('detail')}
            className={`px-3 py-1.5 rounded text-xs font-mono font-semibold transition-all ${
              viewMode === 'detail'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Account Deep-Dive ({activeAccountId})
          </button>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* LEFT SIDEBAR: FILTERS */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-[#1E293B] pb-2.5">
              <span className="text-xs font-bold text-white font-mono uppercase flex items-center gap-1.5">
                <Filter className="w-3.5 h-3.5 text-cyan-400" />
                Filter Accounts
              </span>
              <button
                onClick={resetFilters}
                className="text-[10px] text-slate-400 hover:text-cyan-400 transition-colors font-mono"
              >
                Reset All
              </button>
            </div>

            {/* 1. Account ID Search */}
            <div>
              <label className="text-[10px] font-semibold text-slate-400 uppercase font-mono block mb-1.5">
                Account ID Search
              </label>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  placeholder="e.g. ACC_009937..."
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                  className="w-full bg-[#090D16] border border-[#1E293B] rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 font-mono focus:outline-none focus:border-cyan-500 transition-all"
                />
              </div>
            </div>

            {/* 2. Risk Tier */}
            <div>
              <label className="text-[10px] font-semibold text-slate-400 uppercase font-mono block mb-1.5">
                Risk Tier
              </label>
              <div className="grid grid-cols-5 gap-1 font-mono text-[10px]">
                {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => {
                      setRiskLevel(lvl);
                      setPage(1);
                    }}
                    className={`py-1 rounded text-center font-medium transition-all ${
                      riskLevel === lvl
                        ? 'bg-cyan-500 text-slate-950 font-bold'
                        : 'bg-[#090D16] text-slate-400 hover:text-slate-200 border border-[#1E293B]'
                    }`}
                  >
                    {lvl === 'CRITICAL' ? 'CRIT' : lvl}
                  </button>
                ))}
              </div>
            </div>

            {/* 3. Risk Score Range */}
            <div>
              <label className="text-[10px] font-semibold text-slate-400 uppercase font-mono block mb-1.5">
                Risk Score Range (0 - 100)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="number"
                  placeholder="Min (e.g. 60)"
                  value={minScore}
                  onChange={(e) => {
                    setMinScore(e.target.value);
                    setPage(1);
                  }}
                  className="bg-[#090D16] border border-[#1E293B] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 font-mono focus:outline-none focus:border-cyan-500"
                />
                <input
                  type="number"
                  placeholder="Max (e.g. 100)"
                  value={maxScore}
                  onChange={(e) => {
                    setMaxScore(e.target.value);
                    setPage(1);
                  }}
                  className="bg-[#090D16] border border-[#1E293B] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {/* 4. Cluster Membership */}
            <div>
              <label className="text-[10px] font-semibold text-slate-400 uppercase font-mono block mb-1.5">
                Cluster Membership
              </label>
              <select
                value={clusterId}
                onChange={(e) => {
                  setClusterId(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-[#090D16] border border-[#1E293B] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
              >
                <option value="ALL">All Accounts</option>
                <option value="IN_CLUSTER">Any Detected Cluster</option>
                <option value="CLUSTER_001">CLUSTER_001 (28 Accts)</option>
                <option value="CLUSTER_002">CLUSTER_002 (38 Accts)</option>
                <option value="CLUSTER_003">CLUSTER_003 (4 Accts)</option>
                <option value="CLUSTER_004">CLUSTER_004 (4 Accts)</option>
                <option value="CLUSTER_005">CLUSTER_005 (26 Accts)</option>
                <option value="UNASSIGNED">Unassigned / Isolated</option>
              </select>
            </div>

            {/* 5. Dominant Evidence Signal */}
            <div>
              <label className="text-[10px] font-semibold text-slate-400 uppercase font-mono block mb-1.5">
                Elevated Evidence Signal
              </label>
              <select
                value={evidenceType}
                onChange={(e) => {
                  setEvidenceType(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-[#090D16] border border-[#1E293B] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
              >
                <option value="ALL">All Signals</option>
                <option value="ML">High ML Evidence (≥ 60)</option>
                <option value="GRAPH">High Graph Evidence (≥ 60)</option>
                <option value="COORDINATION">High Coordination (≥ 40)</option>
                <option value="RELATIONSHIP">High Relationship (≥ 40)</option>
              </select>
            </div>

            {/* Active Accounts Count */}
            <div className="pt-2 border-t border-[#1E293B] flex items-center justify-between text-[11px] font-mono text-slate-400">
              <span>Matching:</span>
              <span className="font-bold text-white">{totalAccounts?.toLocaleString()} accounts</span>
            </div>
          </div>

          {/* Quick Shortcuts */}
          <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 space-y-2">
            <span className="text-[10px] font-semibold text-slate-400 uppercase font-mono block">
              Quick Investigation Targets
            </span>
            <div className="space-y-1.5 font-mono text-xs">
              <button
                onClick={() => handleAccountClick('ACC_009937')}
                className="w-full p-2 rounded bg-[#090D16] border border-[#1E293B] hover:border-cyan-500/40 text-left flex items-center justify-between transition-colors group"
              >
                <span className="font-bold text-cyan-300">ACC_009937</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-bold">
                  81.2 CRITICAL
                </span>
              </button>
              <button
                onClick={() => handleAccountClick('ACC_009936')}
                className="w-full p-2 rounded bg-[#090D16] border border-[#1E293B] hover:border-cyan-500/40 text-left flex items-center justify-between transition-colors group"
              >
                <span className="font-bold text-slate-200 group-hover:text-cyan-300">ACC_009936</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-bold">
                  80.9 CRITICAL
                </span>
              </button>
              <button
                onClick={() => handleAccountClick('ACC_000006')}
                className="w-full p-2 rounded bg-[#090D16] border border-[#1E293B] hover:border-cyan-500/40 text-left flex items-center justify-between transition-colors group"
              >
                <span className="font-bold text-slate-200 group-hover:text-cyan-300">ACC_000006</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 font-bold">
                  50.2 MEDIUM
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT MAIN AREA: TABLE VIEW OR ACCOUNT DEEP DIVE */}
        <div className="lg:col-span-9 space-y-5">
          {viewMode === 'table' ? (
            /* MAIN INVESTIGATION TABLE */
            <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#1E293B] pb-3">
                <div>
                  <h2 className="text-sm font-bold text-white font-mono uppercase flex items-center gap-2">
                    <Activity className="w-4 h-4 text-cyan-400" />
                    Account Risk Assessment Queue
                  </h2>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Multi-signal composite scores and recommended routing actions. Click any account to launch deep-dive.
                  </p>
                </div>
                <div className="text-xs font-mono text-slate-400">
                  Page {page} of {Math.max(1, Math.ceil(totalAccounts / pageSize))}
                </div>
              </div>

              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-[#1E293B] text-slate-400 text-[10px] uppercase tracking-wider">
                      <th className="pb-3 font-semibold">Account ID</th>
                      <th className="pb-3 font-semibold">Risk Score</th>
                      <th className="pb-3 font-semibold text-cyan-400">ML</th>
                      <th className="pb-3 font-semibold text-indigo-400">Graph</th>
                      <th className="pb-3 font-semibold text-pink-400">Coord</th>
                      <th className="pb-3 font-semibold">Risk Tier</th>
                      <th className="pb-3 font-semibold">Cluster</th>
                      <th className="pb-3 font-semibold">Recommended Action</th>
                      <th className="pb-3 font-semibold text-right">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1E293B]/60">
                    {loadingList ? (
                      <tr>
                        <td colSpan="9" className="py-12 text-center text-slate-500 font-mono">
                          Evaluating risk records...
                        </td>
                      </tr>
                    ) : accounts.length === 0 ? (
                      <tr>
                        <td colSpan="9" className="py-12 text-center text-slate-500 font-mono">
                          No accounts match criteria.
                        </td>
                      </tr>
                    ) : (
                      accounts.map((acc) => {
                        const isCrit = acc.risk_level === 'CRITICAL';
                        const isHigh = acc.risk_level === 'HIGH';
                        const isMed = acc.risk_level === 'MEDIUM';

                        return (
                          <tr
                            key={acc.account_id}
                            onClick={() => handleAccountClick(acc.account_id)}
                            className="hover:bg-[#151C2C] cursor-pointer transition-colors group"
                          >
                            {/* Account ID */}
                            <td className="py-3 font-bold text-cyan-400 group-hover:text-cyan-300">
                              {acc.account_id}
                            </td>

                            {/* Risk Score */}
                            <td className="py-3 font-extrabold text-white">
                              <span
                                className={`px-2 py-0.5 rounded text-xs ${
                                  isCrit
                                    ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                                    : isHigh
                                    ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                                    : isMed
                                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                    : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                }`}
                              >
                                {acc.final_risk_score?.toFixed(1)}
                              </span>
                            </td>

                            {/* Signals */}
                            <td className="py-3 text-slate-300 font-semibold">{acc.ml_score?.toFixed(0)}</td>
                            <td className="py-3 text-slate-300 font-semibold">{acc.graph_score?.toFixed(0)}</td>
                            <td className="py-3 text-slate-300 font-semibold">{acc.coordination_score?.toFixed(0)}</td>

                            {/* Risk Tier */}
                            <td className="py-3">
                              <span
                                className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                                  isCrit
                                    ? 'bg-red-500/10 text-red-400'
                                    : isHigh
                                    ? 'bg-orange-500/10 text-orange-400'
                                    : isMed
                                    ? 'bg-amber-500/10 text-amber-400'
                                    : 'bg-emerald-500/10 text-emerald-400'
                                }`}
                              >
                                {acc.risk_level}
                              </span>
                            </td>

                            {/* Cluster */}
                            <td className="py-3 text-slate-400">
                              {acc.cluster_id ? (
                                <span className="px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 text-[10px]">
                                  {acc.cluster_id}
                                </span>
                              ) : (
                                <span className="text-slate-500">—</span>
                              )}
                            </td>

                            {/* Recommended Action */}
                            <td className="py-3 text-slate-300 text-[11px] capitalize">
                              {acc.recommended_action}
                            </td>

                            {/* Inspect Action */}
                            <td className="py-3 text-right">
                              <span className="text-[11px] text-cyan-400 group-hover:text-cyan-300 font-semibold flex items-center justify-end gap-1">
                                Open <ChevronRight className="w-3.5 h-3.5" />
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination Footer */}
              <div className="flex items-center justify-between pt-3 border-t border-[#1E293B] text-xs font-mono">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-3 py-1.5 bg-[#090D16] border border-[#1E293B] disabled:opacity-40 rounded hover:bg-[#151C2C] text-slate-300"
                >
                  Previous
                </button>
                <span className="text-slate-400">
                  Showing {accounts.length > 0 ? (page - 1) * pageSize + 1 : 0} -{' '}
                  {Math.min(totalAccounts, page * pageSize)} of {totalAccounts?.toLocaleString()}
                </span>
                <button
                  disabled={page * pageSize >= totalAccounts}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 bg-[#090D16] border border-[#1E293B] disabled:opacity-40 rounded hover:bg-[#151C2C] text-slate-300"
                >
                  Next
                </button>
              </div>
            </div>
          ) : (
            /* ACCOUNT INVESTIGATION VIEW (CENTERPIECE DEEP-DIVE) */
            <div className="space-y-5">
              {/* Back to Table Bar & Navigation */}
              <div className="flex items-center justify-between bg-[#111726] border border-[#1E293B] p-3 rounded-xl">
                <button
                  onClick={() => setViewMode('table')}
                  className="flex items-center gap-1.5 text-xs font-mono font-bold text-cyan-400 hover:text-cyan-300 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                  <span>Back to Accounts Table</span>
                </button>

                <div className="flex items-center gap-2 font-mono text-xs">
                  <button
                    onClick={handlePrevAccount}
                    className="p-1.5 rounded bg-[#090D16] border border-[#1E293B] hover:bg-[#151C2C] text-slate-300"
                    title="Previous Account"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </button>
                  <span className="text-slate-400 px-2">{activeAccountId}</span>
                  <button
                    onClick={handleNextAccount}
                    className="p-1.5 rounded bg-[#090D16] border border-[#1E293B] hover:bg-[#151C2C] text-slate-300"
                    title="Next Account"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {loadingDetail || !activeAccount ? (
                <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-12 text-center text-slate-400 font-mono text-xs">
                  Loading account telemetry profile...
                </div>
              ) : (
                <>
                  {/* 1. ACCOUNT HERO BANNER */}
                  <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5 relative overflow-hidden space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-3">
                          <h2 className="text-2xl font-black font-mono text-white tracking-tight">
                            {activeAccount.account_id}
                          </h2>
                          <span
                            className={`text-xs px-3 py-1 rounded-full font-mono font-bold uppercase tracking-wider ${
                              activeAccount.risk_level === 'CRITICAL'
                                ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                                : activeAccount.risk_level === 'HIGH'
                                ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40'
                                : activeAccount.risk_level === 'MEDIUM'
                                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                            }`}
                          >
                            {activeAccount.risk_level} Risk Tier
                          </span>
                          {activeAccount.cluster_id && (
                            <span className="text-xs px-2.5 py-1 rounded-full font-mono bg-cyan-500/10 border border-cyan-500/30 text-cyan-300">
                              Member: {activeAccount.cluster_id}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-400 mt-1 font-mono flex items-center gap-2">
                          <span>Status:</span>
                          <strong className="text-white capitalize">
                            {reviewStatus || activeAccount.recommended_action}
                          </strong>
                        </div>
                      </div>

                      {/* Final Risk Score Dial */}
                      <div className="flex items-center gap-3 bg-[#090D16] border border-[#1E293B] px-5 py-3 rounded-xl font-mono">
                        <div>
                          <div className="text-[10px] uppercase text-slate-400 font-semibold tracking-wider">
                            Final Risk Score
                          </div>
                          <div className="text-3xl font-black text-white">
                            {activeAccount.final_risk_score?.toFixed(1)}
                            <span className="text-xs text-slate-500 font-normal"> / 100</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* HUMAN REVIEW ACTION BAR (SECTION 10) */}
                    <div className="pt-3 border-t border-[#1E293B] flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-400 uppercase font-mono">
                          Review Actions:
                        </span>
                        <button
                          onClick={() => handleReviewAction('REVIEW')}
                          disabled={isSubmittingReview}
                          className="px-3 py-1.5 rounded-lg bg-[#1E293B] hover:bg-[#2A3B53] text-xs font-mono font-medium text-slate-200 transition-colors"
                        >
                          Review
                        </button>
                        <button
                          onClick={() => handleReviewAction('ESCALATE')}
                          disabled={isSubmittingReview}
                          className="px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 text-xs font-mono font-bold transition-colors"
                        >
                          Escalate
                        </button>
                        <button
                          onClick={() => handleReviewAction('MARK_INVESTIGATING')}
                          disabled={isSubmittingReview}
                          className="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 text-xs font-mono font-medium transition-colors"
                        >
                          Mark Investigating
                        </button>
                        <button
                          onClick={() => handleReviewAction('FALSE_POSITIVE')}
                          disabled={isSubmittingReview}
                          className="px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 text-xs font-mono font-medium transition-colors"
                        >
                          Mark False Positive
                        </button>
                      </div>

                      <div className="text-[10px] font-mono text-slate-400 bg-[#090D16] px-2.5 py-1 rounded border border-[#1E293B]">
                        Defensive Prototype • Non-Blocking Actions
                      </div>
                    </div>
                  </div>

                  {/* 2. FOUR EVIDENCE CARDS (SECTION 4) */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                    {/* ML EVIDENCE */}
                    <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 space-y-2">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[11px] font-semibold uppercase tracking-wider">ML Evidence</span>
                        <Bot className="w-4 h-4 text-cyan-400" />
                      </div>
                      <div className="text-2xl font-extrabold font-mono text-cyan-400">
                        {activeAccount.evidence_scores.ml_score?.toFixed(1)}
                        <span className="text-xs text-slate-500 font-normal"> / 100</span>
                      </div>
                      <div className="w-full h-1.5 bg-[#090D16] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-cyan-500 rounded-full"
                          style={{ width: `${activeAccount.evidence_scores.ml_score}%` }}
                        />
                      </div>
                      <div className="text-[11px] text-slate-400 leading-tight">
                        {activeAccount.evidence_scores.ml_score >= 60
                          ? 'Behavioral model assigns high abuse anomaly probability.'
                          : 'Behavioral transaction patterns within baseline bounds.'}
                      </div>
                      <div className="text-[10px] font-mono text-slate-500 pt-1 border-t border-[#1E293B]">
                        Weight: 40% (Contribution: {((activeAccount.evidence_scores.ml_score * 0.40)).toFixed(1)})
                      </div>
                    </div>

                    {/* GRAPH EVIDENCE */}
                    <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 space-y-2">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[11px] font-semibold uppercase tracking-wider">Graph Evidence</span>
                        <Network className="w-4 h-4 text-indigo-400" />
                      </div>
                      <div className="text-2xl font-extrabold font-mono text-indigo-400">
                        {activeAccount.evidence_scores.graph_score?.toFixed(1)}
                        <span className="text-xs text-slate-500 font-normal"> / 100</span>
                      </div>
                      <div className="w-full h-1.5 bg-[#090D16] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 rounded-full"
                          style={{ width: `${activeAccount.evidence_scores.graph_score}%` }}
                        />
                      </div>
                      <div className="text-[11px] text-slate-400 leading-tight">
                        {activeAccount.evidence_scores.graph_score >= 60
                          ? 'Account belongs to a strongly connected suspicious cluster.'
                          : 'Sparse graph community with low multi-entity link strength.'}
                      </div>
                      <div className="text-[10px] font-mono text-slate-500 pt-1 border-t border-[#1E293B]">
                        Weight: 30% (Contribution: {((activeAccount.evidence_scores.graph_score * 0.30)).toFixed(1)})
                      </div>
                    </div>

                    {/* COORDINATION */}
                    <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 space-y-2">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[11px] font-semibold uppercase tracking-wider">Coordination</span>
                        <Clock className="w-4 h-4 text-pink-400" />
                      </div>
                      <div className="text-2xl font-extrabold font-mono text-pink-400">
                        {activeAccount.evidence_scores.coordination_score?.toFixed(1)}
                        <span className="text-xs text-slate-500 font-normal"> / 100</span>
                      </div>
                      <div className="w-full h-1.5 bg-[#090D16] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-pink-500 rounded-full"
                          style={{ width: `${activeAccount.evidence_scores.coordination_score}%` }}
                        />
                      </div>
                      <div className="text-[11px] text-slate-400 leading-tight">
                        {activeAccount.evidence_scores.coordination_score >= 40
                          ? 'Transaction timing and amount behavior overlaps with several accounts.'
                          : 'Independent activity timing without synchronized bursts.'}
                      </div>
                      <div className="text-[10px] font-mono text-slate-500 pt-1 border-t border-[#1E293B]">
                        Weight: 20% (Contribution: {((activeAccount.evidence_scores.coordination_score * 0.20)).toFixed(1)})
                      </div>
                    </div>

                    {/* RELATIONSHIP */}
                    <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 space-y-2">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[11px] font-semibold uppercase tracking-wider">Relationship</span>
                        <Smartphone className="w-4 h-4 text-emerald-400" />
                      </div>
                      <div className="text-2xl font-extrabold font-mono text-emerald-400">
                        {activeAccount.evidence_scores.relationship_score?.toFixed(1)}
                        <span className="text-xs text-slate-500 font-normal"> / 100</span>
                      </div>
                      <div className="w-full h-1.5 bg-[#090D16] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full"
                          style={{ width: `${activeAccount.evidence_scores.relationship_score}%` }}
                        />
                      </div>
                      <div className="text-[11px] text-slate-400 leading-tight">
                        {activeAccount.evidence_scores.relationship_score >= 40
                          ? 'Account shares hardware device, IP, or destination infrastructure.'
                          : 'Distinct unshared hardware and network infrastructure footprint.'}
                      </div>
                      <div className="text-[10px] font-mono text-slate-500 pt-1 border-t border-[#1E293B]">
                        Weight: 10% (Contribution: {((activeAccount.evidence_scores.relationship_score * 0.10)).toFixed(1)})
                      </div>
                    </div>
                  </div>

                  {/* 3. "WHY WAS THIS ACCOUNT FLAGGED?" (SECTION 4 - STRICT DATA INTEGRITY) */}
                  <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#1E293B] pb-2.5">
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        Why Was This Account Flagged?
                      </h3>
                      <span className="text-[10px] font-mono text-slate-400">
                        Derived strictly from verified observable features
                      </span>
                    </div>

                    <div className="space-y-2 pt-1">
                      {activeAccount.factual_explanations?.map((bullet, idx) => (
                        <div key={idx} className="flex items-start gap-2.5 text-xs text-slate-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 shrink-0" />
                          <span className="font-mono">{bullet}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 4. TRANSPARENT RISK SCORE EXPLANATION (SECTION 9) */}
                  <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between border-b border-[#1E293B] pb-3">
                      <div>
                        <h3 className="text-sm font-bold text-white font-mono uppercase flex items-center gap-2">
                          <Layers className="w-4 h-4 text-cyan-400" />
                          Risk Score Evidence Contribution
                        </h3>
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          {activeAccount.score_formula?.explanation || 'Risk score combines independent evidence sources to reduce reliance on a single signal.'}
                        </p>
                      </div>
                      <div className="text-right font-mono">
                        <span className="text-[10px] uppercase text-slate-400 block">Final Risk Score</span>
                        <span className="text-2xl font-black text-white">
                          {activeAccount.final_risk_score?.toFixed(1)} / 100
                        </span>
                      </div>
                    </div>

                    {/* Contribution Breakdown Bars */}
                    <div className="space-y-3 font-mono text-xs">
                      {activeAccount.score_formula?.contributions?.map((item) => (
                        <div key={item.signal} className="p-3 bg-[#090D16] border border-[#1E293B] rounded-lg">
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-white">{item.signal}</span>
                              <span className="text-[10px] text-slate-400 bg-[#1E293B] px-1.5 py-0.5 rounded">
                                Weight: {item.weight_pct}
                              </span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-slate-400">
                                Raw Score: <strong className="text-slate-200">{item.score?.toFixed(1)}</strong>
                              </span>
                              <span className="font-bold text-cyan-300">
                                Contribution: +{item.contribution?.toFixed(1)}
                              </span>
                            </div>
                          </div>
                          {/* Progress bar representing absolute contribution points */}
                          <div className="w-full h-1.5 bg-[#1E293B] rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-300"
                              style={{
                                width: `${Math.min(100, item.contribution * 2.5)}%`,
                                backgroundColor: item.color,
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 5. ABUSE RING NEIGHBORHOOD GRAPH (SECTION 5) */}
                  <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#1E293B] pb-2.5">
                      <div>
                        <h3 className="text-sm font-bold text-white font-mono uppercase flex items-center gap-2">
                          <Network className="w-4 h-4 text-indigo-400" />
                          Suspicious Neighborhood Sub-Graph
                        </h3>
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          Direct physical infrastructure overlap: shared hardware devices, subnet IPs, and counterparty endpoints
                        </p>
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">
                        {activeAccount.neighborhood_graph?.nodes?.length || 0} Entities •{' '}
                        {activeAccount.neighborhood_graph?.links?.length || 0} Relationships
                      </div>
                    </div>

                    {activeAccount.neighborhood_graph?.nodes?.length > 1 ? (
                      <NetworkGraph
                        nodes={activeAccount.neighborhood_graph.nodes}
                        links={activeAccount.neighborhood_graph.links}
                        selectedNodeId={activeAccount.account_id}
                        onSelectNode={(node) => {
                          if (node.type === 'account' && node.id !== activeAccount.account_id) {
                            handleAccountClick(node.id);
                          }
                        }}
                        height={420}
                      />
                    ) : (
                      <div className="h-48 flex items-center justify-center bg-[#090D16] border border-[#1E293B] rounded-xl text-xs font-mono text-slate-500">
                        Account operates with isolated infrastructure footprints (no direct shared device/IP links).
                      </div>
                    )}
                  </div>

                  {/* 6. HUMAN REVIEW WORKFLOW & AUDIT TRAIL (SECTION 10) */}
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                    {/* Analyst Review Form */}
                    <div className="lg:col-span-6 bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-3">
                      <h3 className="text-sm font-bold text-white font-mono uppercase flex items-center gap-2 border-b border-[#1E293B] pb-2.5">
                        <FileText className="w-4 h-4 text-cyan-400" />
                        Analyst Review Notes
                      </h3>

                      <textarea
                        rows="3"
                        placeholder="Document investigative findings, counterparty rationale, or escalation notes..."
                        value={analystNotes}
                        onChange={(e) => setAnalystNotes(e.target.value)}
                        className="w-full bg-[#090D16] border border-[#1E293B] rounded-lg p-3 text-xs text-slate-200 placeholder-slate-500 font-mono focus:outline-none focus:border-cyan-500 resize-none"
                      />

                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-slate-500 font-mono">
                          Actions update local prototype audit log.
                        </span>
                        <button
                          onClick={() => handleReviewAction('ANALYST_NOTE')}
                          disabled={!analystNotes.trim() || isSubmittingReview}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 text-slate-950 text-xs font-bold font-mono rounded-lg transition-colors"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>Save Note</span>
                        </button>
                      </div>
                    </div>

                    {/* Audit Activity Timeline */}
                    <div className="lg:col-span-6 bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-3">
                      <div className="flex items-center justify-between border-b border-[#1E293B] pb-2.5">
                        <h3 className="text-sm font-bold text-white font-mono uppercase flex items-center gap-2">
                          <History className="w-4 h-4 text-slate-400" />
                          Audit Activity History
                        </h3>
                        <span className="text-[10px] font-mono text-slate-400">Live Triage Trail</span>
                      </div>

                      <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                        {auditLogs.slice(0, 6).map((log) => (
                          <div
                            key={log.id}
                            className="p-2.5 bg-[#090D16] border border-[#1E293B] rounded-lg text-xs font-mono"
                          >
                            <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
                              <span className="font-bold text-cyan-400">{log.action}</span>
                              <span>{log.timestamp?.replace('T', ' ')?.replace('Z', '')}</span>
                            </div>
                            <div className="text-slate-300 text-[11px]">{log.notes}</div>
                            <div className="text-[9px] text-slate-500 mt-1 flex items-center justify-between">
                              <span>Target: {log.target}</span>
                              <span>{log.analyst}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* 7. RECENT TRANSACTIONS STREAM */}
                  <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#1E293B] pb-2.5">
                      <h3 className="text-sm font-bold text-white font-mono uppercase flex items-center gap-2">
                        <Clock className="w-4 h-4 text-slate-400" />
                        Recent Transaction Stream ({activeAccount.recent_transactions?.length || 0} Records)
                      </h3>
                      <button
                        onClick={() => onNavigate('transactions')}
                        className="text-xs text-cyan-400 hover:text-cyan-300 font-mono transition-colors"
                      >
                        Open Full Explorer →
                      </button>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead>
                          <tr className="border-b border-[#1E293B] text-slate-400 text-[10px] uppercase">
                            <th className="pb-2">Tx ID</th>
                            <th className="pb-2">Timestamp</th>
                            <th className="pb-2">Amount</th>
                            <th className="pb-2">Type</th>
                            <th className="pb-2">Counterparty</th>
                            <th className="pb-2">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#1E293B]/60">
                          {activeAccount.recent_transactions?.map((tx) => (
                            <tr key={tx.transaction_id} className="hover:bg-[#151C2C]">
                              <td className="py-2 text-cyan-400">{tx.transaction_id}</td>
                              <td className="py-2 text-slate-400">{tx.timestamp}</td>
                              <td className="py-2 font-bold text-white">{formatINR(tx.amount)}</td>
                              <td className="py-2 capitalize text-slate-300">{tx.transaction_type}</td>
                              <td className="py-2 text-slate-400">
                                {tx.destination_id || tx.merchant_id || '—'}
                              </td>
                              <td className="py-2">
                                <span
                                  className={`text-[10px] px-1.5 py-0.5 rounded ${
                                    tx.status === 'SUCCESS'
                                      ? 'bg-emerald-500/10 text-emerald-400'
                                      : 'bg-red-500/10 text-red-400'
                                  }`}
                                >
                                  {tx.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
