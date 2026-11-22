import React, { useEffect, useState } from 'react';
import {
  Users,
  CreditCard,
  ShieldAlert,
  AlertTriangle,
  Network,
  ArrowRight,
  TrendingUp,
  Activity,
  Layers,
  ChevronRight,
  ExternalLink,
  Bot,
  Clock,
  Smartphone,
  ShieldCheck,
  CheckCircle2,
  Cpu,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { api } from '../services/api';

export default function Overview({ onNavigate, onSelectAccount, onSelectCluster }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showArchDetails, setShowArchDetails] = useState(false);

  useEffect(() => {
    let mounted = true;
    api
      .getOverview()
      .then((res) => {
        if (mounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[#147D69] border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-[#737A76]">Loading Risk Operations Center...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8 text-center bg-white border border-[#C64B43]/30 rounded-xl shadow-sm max-w-lg mx-auto mt-12">
        <AlertTriangle className="w-8 h-8 text-[#C64B43] mx-auto mb-3" />
        <h3 className="text-sm font-bold text-[#252B29] mb-1">Failed to Load Overview Data</h3>
        <p className="text-xs text-[#737A76] mb-4">{error || 'Unknown error'}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-[#F7F6F2] hover:bg-[#E2E0D8] text-xs font-medium rounded-lg text-[#252B29] transition-colors border border-[#E2E0D8]"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const { kpis, risk_distribution, priority_investigations, top_risk_drivers, emerging_clusters } = data;

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload;
      return (
        <div className="bg-white/95 border border-[#E2E0D8] p-2.5 rounded-lg shadow text-xs font-mono">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
            <span className="font-bold text-[#252B29]">{d.level} Tier</span>
          </div>
          <div className="text-[#3D4543]">{d.count?.toLocaleString()} accounts ({d.percentage}%)</div>
          <div className="text-[#9BA09D] text-[10px] mt-0.5">{d.range || ''}</div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#E2E0D8] pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-extrabold text-[#252B29] tracking-tight flex items-center gap-2">
              <Activity className="w-5 h-5 text-[#147D69]" />
              Risk Operations Center
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-[#147D69]/10 border border-[#147D69]/25 text-[#147D69] text-[10px] font-mono font-medium">
              Live Synthetic Benchmark
            </span>
          </div>
          <p className="text-xs text-[#737A76] mt-1 font-sans">
            Operational triage snapshot • Calibrated CatBoost ML and decoupled graph investigation engine
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => onNavigate('clusters')}
            className="flex items-center gap-2 px-3.5 py-2 bg-white hover:bg-[#F7F6F2] text-[#252B29] text-xs font-semibold rounded-lg border border-[#E2E0D8] shadow-sm transition-all font-sans"
          >
            <Network className="w-3.5 h-3.5 text-[#147D69]" />
            <span>Risk Clusters (299)</span>
          </button>
          <button
            onClick={() => onNavigate('investigations')}
            className="flex items-center gap-2 px-4 py-2 bg-[#147D69] hover:bg-[#117A62] text-white text-xs font-bold rounded-lg shadow-sm transition-all font-sans"
          >
            <span>Launch Investigations (436)</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 2. Top KPI Cards Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* KPI 1: Accounts Analyzed */}
        <div className="bg-white border border-[#E2E0D8] rounded-xl p-3.5 space-y-1 shadow-sm">
          <div className="flex items-center justify-between text-[#737A76] text-[10px] font-mono uppercase font-semibold">
            <span>Accounts Analyzed</span>
            <Users className="w-3.5 h-3.5 text-[#147D69]" />
          </div>
          <div className="text-2xl font-black font-mono text-[#252B29]">
            {kpis.accounts_analyzed?.toLocaleString()}
          </div>
          <div className="text-[10px] text-[#9BA09D] font-mono truncate">
            {kpis.valid_predictive_accounts?.toLocaleString() || '9,990'} PIT Valid • 10 Excluded
          </div>
        </div>

        {/* KPI 2: Transactions */}
        <button
          onClick={() => onNavigate('transactions')}
          className="bg-white border border-[#E2E0D8] hover:border-[#7C6EAF]/50 rounded-xl p-3.5 space-y-1 shadow-sm text-left transition-all group cursor-pointer"
        >
          <div className="flex items-center justify-between text-[#737A76] group-hover:text-[#7C6EAF] text-[10px] font-mono uppercase font-semibold transition-colors">
            <span>Transactions</span>
            <CreditCard className="w-3.5 h-3.5 text-[#7C6EAF]" />
          </div>
          <div className="text-2xl font-black font-mono text-[#252B29] group-hover:text-[#7C6EAF] transition-colors">
            {kpis.transactions_analyzed?.toLocaleString()}
          </div>
          <div className="text-[10px] text-[#9BA09D] font-mono truncate flex items-center justify-between">
            <span>30-day transactional stream</span>
            <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </button>

        {/* KPI 3: Action Required */}
        <button
          onClick={() => onNavigate('investigations')}
          className="bg-white border border-[#B99A45]/30 hover:border-[#B99A45] rounded-xl p-3.5 space-y-1 shadow-sm text-left transition-all group cursor-pointer"
        >
          <div className="flex items-center justify-between text-[#B99A45] text-[10px] font-mono uppercase font-semibold">
            <span>Action Required</span>
            <ShieldAlert className="w-3.5 h-3.5 text-[#B99A45]" />
          </div>
          <div className="text-2xl font-black font-mono text-[#B99A45]">
            {kpis.high_critical_count?.toLocaleString() || '436'}
          </div>
          <div className="text-[10px] text-[#B99A45]/80 font-mono truncate flex items-center justify-between">
            <span>Decision Cutoff: P &ge; 0.35</span>
            <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </button>

        {/* KPI 4: Priority Review Queue */}
        <button
          onClick={() => onNavigate('investigations')}
          className="bg-white border border-[#C64B43]/30 hover:border-[#C64B43] rounded-xl p-3.5 space-y-1 shadow-sm text-left transition-all group cursor-pointer"
        >
          <div className="flex items-center justify-between text-[#C64B43] text-[10px] font-mono uppercase font-semibold">
            <span>Priority Queue</span>
            <AlertTriangle className="w-3.5 h-3.5 text-[#C64B43]" />
          </div>
          <div className="text-2xl font-black font-mono text-[#C64B43]">
            353 <span className="text-xs font-normal text-[#737A76]">Crit</span> + 83 <span className="text-xs font-normal text-[#737A76]">High</span>
          </div>
          <div className="text-[10px] text-[#C64B43]/80 font-mono truncate flex items-center justify-between">
            <span>Sorted by CatBoost P(abuse)</span>
            <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </button>

        {/* KPI 5: Retrospective Clusters */}
        <button
          onClick={() => onNavigate('clusters')}
          className="bg-white border border-[#E2E0D8] hover:border-[#147D69]/50 rounded-xl p-3.5 space-y-1 shadow-sm text-left transition-all group cursor-pointer"
        >
          <div className="flex items-center justify-between text-[#737A76] group-hover:text-[#147D69] text-[10px] font-mono uppercase font-semibold transition-colors">
            <span>Risk Clusters</span>
            <Network className="w-3.5 h-3.5 text-[#147D69]" />
          </div>
          <div className="text-2xl font-black font-mono text-[#147D69]">
            {kpis.candidate_clusters_count || '299'}
          </div>
          <div className="text-[10px] text-[#9BA09D] font-mono truncate flex items-center justify-between">
            <span>30-day Louvain communities</span>
            <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </button>
      </div>

      {/* 3. Middle Operational Grid: Risk Distribution + Architecture Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left: Account Risk Distribution */}
        <div className="lg:col-span-6 bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-3 shadow-sm">
          <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2.5">
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#252B29] font-sans flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-[#147D69]" />
                Account Risk Distribution
              </h2>
              <span className="text-[10px] text-[#737A76] font-mono">
                Platt-calibrated CatBoost probabilities across 10,000 accounts
              </span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#B99A45]/10 border border-[#B99A45]/25 text-[#B99A45] font-semibold">
              Decision Cutoff: 0.35
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-12 items-center gap-4 pt-1">
            <div className="sm:col-span-6 h-40 min-h-[160px] flex items-center justify-center relative">
              <PieChart width={180} height={160}>
                <Pie
                  data={risk_distribution}
                  dataKey="count"
                  nameKey="level"
                  cx="50%"
                  cy="50%"
                  innerRadius={44}
                  outerRadius={68}
                  paddingAngle={3}
                  stroke="#FFFFFF"
                  strokeWidth={2}
                  isAnimationActive={false}
                >
                  {risk_distribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none font-mono">
                <span className="text-base font-extrabold text-[#252B29]">436</span>
                <span className="text-[9px] uppercase tracking-wider text-[#B99A45] font-bold">&ge; 0.35 Triage</span>
              </div>
            </div>

            <div className="sm:col-span-6 space-y-1.5 font-mono">
              {risk_distribution.map((d) => (
                <button
                  key={d.level}
                  onClick={() => onNavigate('investigations')}
                  className="w-full flex items-center justify-between p-1.5 px-2.5 rounded-lg bg-[#F7F6F2] hover:bg-[#EAE8E0] border border-[#E2E0D8] text-xs transition-colors group cursor-pointer text-left"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
                    <span className="font-semibold text-[#3D4543] group-hover:text-[#252B29]">{d.level}</span>
                  </div>
                  <div className="text-right flex items-center gap-1.5">
                    <span className="font-bold text-[#252B29]">{d.count?.toLocaleString()}</span>
                    <span className="text-[10px] text-[#737A76]">({d.percentage}%)</span>
                    <ChevronRight className="w-3 h-3 text-[#9BA09D] opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Architecture Summary Card (Progressive Disclosure) */}
        <div className="lg:col-span-6 bg-white border border-[#E2E0D8] rounded-xl p-4 flex flex-col justify-between space-y-3 shadow-sm">
          <div className="space-y-2">
            <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2.5">
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#252B29] font-sans flex items-center gap-2">
                <Cpu className="w-3.5 h-3.5 text-[#147D69]" />
                Decoupled Detection Architecture
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#147D69]/10 border border-[#147D69]/25 text-[#147D69] font-semibold">
                Pure ML + Decoupled Graph
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2.5 pt-1 text-xs font-sans">
              <div className="p-2.5 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg space-y-1">
                <div className="flex items-center gap-1.5 text-[#147D69] font-bold text-[11px]">
                  <Bot className="w-3.5 h-3.5" />
                  <span>CatBoost Baseline</span>
                </div>
                <p className="text-[10px] text-[#737A76] leading-tight">
                  Point-in-time Platt-calibrated probability P(abuse). PR-AUC: <span className="font-mono">0.6242</span>.
                </p>
              </div>

              <div className="p-2.5 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg space-y-1">
                <div className="flex items-center gap-1.5 text-[#7C6EAF] font-bold text-[11px]">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Frozen 0.35 Rule</span>
                </div>
                <p className="text-[10px] text-[#737A76] leading-tight">
                  Validation-frozen threshold. <span className="font-mono">77.8%</span> recall against coordinated abuse rings.
                </p>
              </div>

              <div className="p-2.5 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg space-y-1">
                <div className="flex items-center gap-1.5 text-[#C64B43] font-bold text-[11px]">
                  <Network className="w-3.5 h-3.5" />
                  <span>Graph Intelligence</span>
                </div>
                <p className="text-[10px] text-[#737A76] leading-tight">
                  Entity sharing badges (Device/IP). Zero score blending prevents false positives.
                </p>
              </div>

              <div className="p-2.5 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg space-y-1">
                <div className="flex items-center gap-1.5 text-[#147D69] font-bold text-[11px]">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Temporal Integrity</span>
                </div>
                <p className="text-[10px] text-[#737A76] leading-tight">
                  Strict 7-day observation cutoff (t &le; T_obs). Zero future data leakage.
                </p>
              </div>
            </div>
          </div>

          {/* Collapsible Architecture Details Toggle */}
          <div>
            <button
              onClick={() => setShowArchDetails(!showArchDetails)}
              className="w-full flex items-center justify-between px-3 py-1.5 bg-[#F7F6F2] hover:bg-[#E2E0D8] border border-[#E2E0D8] rounded-lg text-[10px] font-sans text-[#3D4543] transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <Info className="w-3 h-3 text-[#147D69]" />
                <span>Why Heuristic Composite Fusion Was Rejected</span>
              </span>
              {showArchDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>

            {showArchDetails && (
              <div className="mt-2 p-3 bg-[#F7F6F2] border border-[#147D69]/20 rounded-lg text-[10px] font-sans text-[#737A76] space-y-1">
                <p className="leading-relaxed">
                  During Phase 3.1 & Phase 4, heuristic composite weighting formulas (e.g. arbitrary linear blending of ML, graph density, and similarity) were empirically proven to reduce PR-AUC and increase false positive escalations on benign shared households.
                </p>
                <p className="text-[#147D69] font-semibold pt-0.5">
                  Resolution: Queue prioritization is driven strictly by calibrated CatBoost probabilities, with graph relationships presented as decoupled context for human review.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4. Priority Investigations Queue (Recent Top Accounts) */}
      <div className="bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-3 shadow-sm">
        <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2.5">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#252B29] font-sans flex items-center gap-2">
              <ShieldAlert className="w-3.5 h-3.5 text-[#C64B43]" />
              Priority Investigations Queue
            </h2>
            <span className="text-[10px] text-[#737A76] font-mono">
              Accounts exceeding 0.35 decision threshold, sorted strictly by calibrated P(abuse) descending
            </span>
          </div>
          <button
            onClick={() => onNavigate('investigations')}
            className="text-xs text-[#147D69] hover:text-[#0F6B59] flex items-center gap-1 font-sans font-medium transition-colors"
          >
            Open Full Workspace <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E2E0D8] text-[#737A76] text-[10px] uppercase">
                <th className="pb-2 font-semibold">Account ID</th>
                <th className="pb-2 font-semibold">Calibrated P(Abuse)</th>
                <th className="pb-2 font-semibold">Risk Tier</th>
                <th className="pb-2 font-semibold">Decision Status</th>
                <th className="pb-2 font-semibold">Evidence Badges</th>
                <th className="pb-2 font-semibold">Outcome Window</th>
                <th className="pb-2 font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E0D8]/60">
              {priority_investigations.slice(0, 6).map((acc) => (
                <tr
                  key={acc.account_id}
                  onClick={() => {
                    onSelectAccount(acc.account_id);
                    onNavigate('investigations');
                  }}
                  className="hover:bg-[#F7F6F2] cursor-pointer transition-colors group"
                >
                  <td className="py-2.5 font-bold font-mono text-[#147D69] group-hover:text-[#0F6B59] flex items-center gap-1.5">
                    <span>{acc.account_id}</span>
                    <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </td>
                  <td className="py-2.5 font-black font-mono text-[#C64B43]">
                    {acc.calibrated_probability != null ? acc.calibrated_probability.toFixed(4) : (acc.final_risk_score / 100).toFixed(4)}
                  </td>
                  <td className="py-2.5">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      acc.risk_tier === 'CRITICAL' || acc.risk_level === 'CRITICAL'
                        ? 'bg-[#C64B43]/10 text-[#C64B43] border border-[#C64B43]/25'
                        : acc.risk_tier === 'HIGH' || acc.risk_level === 'HIGH'
                        ? 'bg-[#D58A27]/10 text-[#D58A27] border border-[#D58A27]/25'
                        : acc.risk_tier === 'MEDIUM' || acc.risk_level === 'MEDIUM'
                        ? 'bg-[#B99A45]/10 text-[#B99A45] border border-[#B99A45]/25'
                        : 'bg-[#78858A]/10 text-[#78858A] border border-[#78858A]/25'
                    }`}>
                      {acc.risk_tier || acc.risk_level}
                    </span>
                  </td>
                  <td className="py-2.5">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                      acc.is_high_risk
                        ? 'text-[#C64B43] bg-[#C64B43]/10'
                        : 'text-[#78858A] bg-[#78858A]/10'
                    }`}>
                      {acc.is_high_risk ? 'ESCALATED (\u2265 0.35)' : 'MONITOR (< 0.35)'}
                    </span>
                  </td>
                  <td className="py-2.5 text-[#3D4543]">
                    {acc.evidence_badges && acc.evidence_badges.length > 0 ? (
                      <div className="flex gap-1">
                        {acc.evidence_badges.map((b) => (
                          <span key={b} className="text-[9px] px-1.5 py-0.5 rounded bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/20">
                            {b}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-[10px] text-[#9BA09D] font-mono">BEHAVIORAL_ANOMALY</span>
                    )}
                  </td>
                  <td className="py-2.5 text-[#737A76] text-[10px] font-mono">
                    {acc.outcome_window_status || 'COMPLETE'}
                  </td>
                  <td className="py-2.5 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectAccount(acc.account_id);
                        onNavigate('investigations');
                      }}
                      className="px-2.5 py-1 rounded bg-[#F7F6F2] hover:bg-[#147D69] hover:text-white text-[#147D69] border border-[#E2E0D8] text-[10px] font-bold transition-all inline-flex items-center gap-1"
                    >
                      Inspect <ChevronRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Emerging Coordinated Clusters (Retrospective Macro Communities) */}
      <div className="bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-3 shadow-sm">
        <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2.5">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#252B29] font-sans flex items-center gap-2">
              <Network className="w-3.5 h-3.5 text-[#147D69]" />
              Retrospective Macro Communities (299 Clusters)
            </h2>
            <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-[#B99A45]/10 text-[#B99A45] border border-[#B99A45]/25 uppercase font-semibold">
              Post-Hoc Audit
            </span>
          </div>
          <button
            onClick={() => onNavigate('clusters')}
            className="text-xs text-[#147D69] hover:text-[#0F6B59] flex items-center gap-1 font-sans font-medium transition-colors"
          >
            Explore Graph Explorer <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {emerging_clusters.slice(0, 5).map((cluster) => {
            const totalMembers = cluster.account_count || cluster.num_members || 1;
            const highCount = cluster.high_risk_count || 0;
            const ratioPct = Math.min(100, Math.round((highCount / totalMembers) * 100));

            return (
              <button
                key={cluster.cluster_id}
                onClick={() => {
                  onSelectCluster(cluster.cluster_id);
                  onNavigate('clusters');
                }}
                className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] hover:border-[#147D69]/50 hover:bg-white rounded-xl text-left font-sans transition-all group cursor-pointer shadow-none hover:shadow-sm"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold font-mono text-[#252B29] group-hover:text-[#147D69] transition-colors">
                    {cluster.cluster_id}
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white group-hover:bg-[#F7F6F2] text-[#3D4543] font-bold border border-[#E2E0D8]">
                    {totalMembers} Accts
                  </span>
                </div>

                <div className="space-y-1 text-[11px] mt-2">
                  <div className="flex justify-between text-[#737A76]">
                    <span>High Risk:</span>
                    <span className="font-bold text-[#C64B43]">{highCount} ({ratioPct}%)</span>
                  </div>
                  <div className="w-full bg-[#E2E0D8] h-1.5 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${ratioPct}%`,
                        backgroundColor: ratioPct >= 50 ? '#C64B43' : '#D58A27',
                      }}
                    />
                  </div>
                  <div className="flex justify-between text-[#9BA09D] text-[10px] pt-0.5">
                    <span>Mean P:</span>
                    <span className="font-mono font-medium text-[#252B29]">
                      {cluster.mean_calibrated_probability != null ? cluster.mean_calibrated_probability.toFixed(3) : '0.499'}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 6. Subtle Synthetic Benchmark Disclosure */}
      <div className="px-4 py-2 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg flex items-center justify-between text-[11px] text-[#737A76]">
        <span className="flex items-center gap-2">
          <Info className="w-3.5 h-3.5 text-[#147D69] shrink-0" />
          <span>Synthetic Defense Evaluation Environment • <span className="font-mono">10,000</span> accounts • <span className="font-mono">159,569</span> transactions</span>
        </span>
        <span className="text-[#9BA09D] text-[10px] font-mono">Deterministic Benchmark</span>
      </div>
    </div>
  );
}
