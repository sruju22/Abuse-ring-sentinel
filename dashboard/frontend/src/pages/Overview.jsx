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
  HelpCircle,
  Cpu,
  Info,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../services/api';

export default function Overview({ onNavigate, onSelectAccount, onSelectCluster }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
          <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-slate-400">Loading Risk Operations Center...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8 text-center bg-[#111726] border border-red-500/30 rounded-xl max-w-lg mx-auto mt-12">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
        <h3 className="text-sm font-bold text-white mb-1">Failed to Load Overview Data</h3>
        <p className="text-xs text-slate-400 mb-4">{error || 'Unknown error'}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-[#1E293B] hover:bg-[#2A3B53] text-xs font-medium rounded-lg text-white transition-colors"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const { kpis, risk_distribution, signal_stack, priority_investigations, top_risk_drivers, emerging_clusters } = data;

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload;
      return (
        <div className="bg-[#111726]/95 border border-[#1E293B] p-2.5 rounded-lg shadow-xl text-xs font-mono">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
            <span className="font-bold text-white">{d.level} Tier</span>
          </div>
          <div className="text-slate-300">{d.count?.toLocaleString()} accounts ({d.percentage}%)</div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1E293B]/70 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-extrabold text-white tracking-tight">Risk Operations Center</h1>
            <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-[10px] font-mono font-semibold uppercase tracking-wider">
              Synthetic Dataset • 10K Accounts
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Detect coordinated abuse before it becomes systemic • Real-time Multi-Signal Intelligence
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onNavigate('investigations')}
            className="flex items-center gap-2 px-3.5 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-bold rounded-lg shadow-sm shadow-cyan-500/20 transition-all"
          >
            <span>Launch Investigations</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* TOP KPI ROW */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
        {/* KPI 1 */}
        <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Accounts Analyzed</span>
            <Users className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-extrabold font-mono text-white">
            {kpis.accounts_analyzed?.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-400 mt-1.5 flex items-center gap-1 font-mono">
            <span className="text-emerald-400">100%</span> baseline coverage
          </div>
          <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 w-16 h-16 bg-cyan-500/5 rounded-full pointer-events-none" />
        </div>

        {/* KPI 2 */}
        <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Transactions</span>
            <CreditCard className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-extrabold font-mono text-white">
            {kpis.transactions_analyzed?.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-400 mt-1.5 font-mono">
            Across 30-day monitoring window
          </div>
          <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 w-16 h-16 bg-indigo-500/5 rounded-full pointer-events-none" />
        </div>

        {/* KPI 3 */}
        <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 relative overflow-hidden group">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-300">Risk-Flagged Accounts</span>
            <ShieldAlert className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-extrabold font-mono text-amber-400">
            {(kpis.risk_flagged_accounts || kpis.abuse_risk_accounts)?.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-400 mt-1.5 font-mono leading-tight">
            Accounts exceeding prototype review threshold (Score ≥ 30.0); not ground-truth abuse labels.
          </div>
          <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 w-16 h-16 bg-amber-500/5 rounded-full pointer-events-none" />
        </div>

        {/* KPI 4 */}
        <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider">High / Critical</span>
            <AlertTriangle className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-2xl font-extrabold font-mono text-red-400">
            {kpis.high_critical_count?.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-400 mt-1.5 font-mono">
            Priority Human Review Queue
          </div>
          <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 w-16 h-16 bg-red-500/5 rounded-full pointer-events-none" />
        </div>

        {/* KPI 5 */}
        <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Candidate Clusters</span>
            <Network className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-extrabold font-mono text-emerald-400">
            {kpis.candidate_clusters_count}
          </div>
          <div className="text-[10px] text-slate-400 mt-1.5 font-mono">
            Multi-hop coordinated rings
          </div>
          <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 w-16 h-16 bg-emerald-500/5 rounded-full pointer-events-none" />
        </div>
      </div>

      {/* PROMINENT SECTION: HOW THE ENGINE DETECTS COORDINATION */}
      <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-6 space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#1E293B] pb-4">
          <div>
            <div className="flex items-center gap-2.5">
              <Layers className="w-5 h-5 text-cyan-400" />
              <h2 className="text-base font-extrabold text-white tracking-tight uppercase">
                How the Engine Detects Coordination
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Coordinated abuse rings hide behind seemingly independent accounts. The engine fuses 4 independent evidence layers to unmask synchronized syndicates:
            </p>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-[#090D16] border border-cyan-500/30 text-[11px] font-mono text-cyan-300 self-start md:self-auto">
            Multi-Signal Composite Fusion
          </div>
        </div>

        {/* Four Evidence Layers */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Layer 1: ML Evidence */}
          <div className="bg-[#090D16] border border-[#1E293B] hover:border-cyan-500/40 rounded-xl p-4 space-y-3 transition-colors">
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
                <Bot className="w-4 h-4 text-cyan-400" />
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1E293B] text-cyan-300 font-bold">
                Weight: 40%
              </span>
            </div>
            <div>
              <div className="text-xs font-bold text-white uppercase tracking-wider">1. ML Evidence</div>
              <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                Mean Score: {signal_stack[0]?.mean_score?.toFixed(1) || '1.0'} / 100
              </div>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Supervised behavioral model evaluates individual transaction amounts, velocities, cashout frequencies, and statistical anomaly probabilities.
            </p>
          </div>

          {/* Layer 2: Graph Evidence */}
          <div className="bg-[#090D16] border border-[#1E293B] hover:border-indigo-500/40 rounded-xl p-4 space-y-3 transition-colors">
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                <Network className="w-4 h-4 text-indigo-400" />
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1E293B] text-indigo-300 font-bold">
                Weight: 30%
              </span>
            </div>
            <div>
              <div className="text-xs font-bold text-white uppercase tracking-wider">2. Graph Evidence</div>
              <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                Mean Score: {signal_stack[1]?.mean_score?.toFixed(1) || '0.8'} / 100
              </div>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Graph intelligence evaluates Louvain community membership, topological graph density, and multi-hop account-to-account projection edge strength.
            </p>
          </div>

          {/* Layer 3: Behavioral Coordination */}
          <div className="bg-[#090D16] border border-[#1E293B] hover:border-pink-500/40 rounded-xl p-4 space-y-3 transition-colors">
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-pink-500/10 border border-pink-500/20">
                <Clock className="w-4 h-4 text-pink-400" />
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1E293B] text-pink-300 font-bold">
                Weight: 20%
              </span>
            </div>
            <div>
              <div className="text-xs font-bold text-white uppercase tracking-wider">3. Behavioral Coordination</div>
              <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                Mean Score: {signal_stack[2]?.mean_score?.toFixed(1) || '0.6'} / 100
              </div>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Measures cross-account temporal burst synchrony (cosine similarity across 1-hour time bins) and structured transaction amount congruence.
            </p>
          </div>

          {/* Layer 4: Relationship Evidence */}
          <div className="bg-[#090D16] border border-[#1E293B] hover:border-emerald-500/40 rounded-xl p-4 space-y-3 transition-colors">
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <Smartphone className="w-4 h-4 text-emerald-400" />
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1E293B] text-emerald-300 font-bold">
                Weight: 10%
              </span>
            </div>
            <div>
              <div className="text-xs font-bold text-white uppercase tracking-wider">4. Relationship Evidence</div>
              <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                Mean Score: {signal_stack[3]?.mean_score?.toFixed(1) || '22.6'} / 100
              </div>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Identifies direct physical infrastructure reuse: shared hardware devices, subnet IP footprints, and concentrated payment destination funnels.
            </p>
          </div>
        </div>

        {/* Explainability Callout Banner */}
        <div className="p-3.5 rounded-lg bg-[#090D16] border border-cyan-500/25 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
          <div className="flex items-center gap-2 text-slate-200">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>
              <strong className="text-white">Explainability Guarantee:</strong> The final risk score is NOT simply "ML says fraud". It is a composite ensemble:
            </span>
          </div>
          <div className="text-[11px] text-cyan-300 bg-cyan-500/10 px-3 py-1 rounded border border-cyan-500/30">
            Score = (0.40 × ML) + (0.30 × Graph) + (0.20 × Coord) + (0.10 × Rel)
          </div>
        </div>
      </div>

      {/* RISK DISTRIBUTION & DETECTION SIGNAL STACK */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* LEFT: Risk Distribution */}
        <div className="lg:col-span-6 bg-[#111726] border border-[#1E293B] rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                Account Risk Distribution
              </h2>
              <p className="text-[11px] text-slate-400 mt-0.5">Categorical tiering across all 10,000 accounts</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-12 items-center gap-4">
            {/* Donut Chart */}
            <div className="sm:col-span-6 h-48 relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={risk_distribution}
                    dataKey="count"
                    nameKey="level"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={3}
                    stroke="#0B0F19"
                    strokeWidth={2}
                  >
                    {risk_distribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-lg font-bold font-mono text-white">10K</span>
                <span className="text-[9px] uppercase tracking-wider text-slate-400">Accounts</span>
              </div>
            </div>

            {/* Breakdown List */}
            <div className="sm:col-span-6 space-y-2">
              {risk_distribution.map((d) => (
                <div
                  key={d.level}
                  className="flex items-center justify-between p-2 rounded-lg bg-[#090D16] border border-[#1E293B]/70"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                    <span className="text-xs font-semibold text-slate-200">{d.level}</span>
                  </div>
                  <div className="text-right font-mono">
                    <div className="text-xs font-bold text-white">{d.count?.toLocaleString()}</div>
                    <div className="text-[10px] text-slate-400">{d.percentage}%</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT: Detection Signal Stack */}
        <div className="lg:col-span-6 bg-[#111726] border border-[#1E293B] rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                Detection Signal Stack
              </h2>
              <p className="text-[11px] text-slate-400 mt-0.5">Multi-signal evidence composition & weights</p>
            </div>
          </div>

          <div className="space-y-3.5">
            {signal_stack.map((sig) => (
              <div key={sig.signal} className="p-3 bg-[#090D16] border border-[#1E293B] rounded-lg">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white">{sig.signal}</span>
                    <span className="px-1.5 py-0.5 rounded bg-[#1E293B] text-[10px] font-mono text-slate-300">
                      Weight: {sig.weight}
                    </span>
                  </div>
                  <span className="text-xs font-mono font-bold text-slate-200">
                    Mean: {sig.mean_score?.toFixed(1)} / 100
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="w-full h-1.5 bg-[#1E293B] rounded-full overflow-hidden mb-1">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(100, Math.max(5, sig.mean_score * 2))}%`,
                      backgroundColor: sig.color,
                    }}
                  />
                </div>
                <div className="text-[10px] text-slate-400">{sig.description}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* SECOND ROW (Priority Investigations & Top Risk Drivers) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Priority Investigations Table */}
        <div className="lg:col-span-8 bg-[#111726] border border-[#1E293B] rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-400" />
                Priority Investigations
              </h2>
              <p className="text-[11px] text-slate-400 mt-0.5">Highest-risk accounts requiring human analyst review</p>
            </div>
            <button
              onClick={() => onNavigate('investigations')}
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium transition-colors"
            >
              View All <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-[#1E293B] text-slate-400 text-[10px] uppercase tracking-wider">
                  <th className="pb-2.5 font-semibold">Account ID</th>
                  <th className="pb-2.5 font-semibold">Risk Score</th>
                  <th className="pb-2.5 font-semibold">ML</th>
                  <th className="pb-2.5 font-semibold">Graph</th>
                  <th className="pb-2.5 font-semibold">Coord</th>
                  <th className="pb-2.5 font-semibold">Tier</th>
                  <th className="pb-2.5 font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E293B]/60">
                {priority_investigations.slice(0, 8).map((acc) => (
                  <tr
                    key={acc.account_id}
                    onClick={() => {
                      onSelectAccount(acc.account_id);
                      onNavigate('investigations');
                    }}
                    className="hover:bg-[#151C2C] cursor-pointer transition-colors group"
                  >
                    <td className="py-2.5 font-bold text-cyan-400 group-hover:text-cyan-300 flex items-center gap-1.5">
                      <span>{acc.account_id}</span>
                      <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </td>
                    <td className="py-2.5 font-bold text-white">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        acc.final_risk_score >= 80 ? 'bg-red-500/15 text-red-400 border border-red-500/30' :
                        acc.final_risk_score >= 60 ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30' :
                        'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                      }`}>
                        {acc.final_risk_score?.toFixed(1)}
                      </span>
                    </td>
                    <td className="py-2.5 text-slate-300">{acc.ml_score?.toFixed(0)}</td>
                    <td className="py-2.5 text-slate-300">{acc.graph_score?.toFixed(0)}</td>
                    <td className="py-2.5 text-slate-300">{acc.coordination_score?.toFixed(0)}</td>
                    <td className="py-2.5">
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                        acc.risk_level === 'CRITICAL' ? 'bg-red-500/10 text-red-400' : 'bg-orange-500/10 text-orange-400'
                      }`}>
                        {acc.risk_level}
                      </span>
                    </td>
                    <td className="py-2.5 text-slate-400 text-[11px] capitalize">
                      {acc.recommended_action}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Top Risk Drivers */}
        <div className="lg:col-span-4 bg-[#111726] border border-[#1E293B] rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                Top Risk Drivers
              </h2>
              <p className="text-[11px] text-slate-400 mt-0.5">Most frequent elevated telemetry signals</p>
            </div>
          </div>

          <div className="space-y-2.5">
            {top_risk_drivers.map((driver, idx) => (
              <div key={driver.code} className="p-2.5 bg-[#090D16] border border-[#1E293B] rounded-lg flex items-center justify-between">
                <div>
                  <div className="text-xs font-semibold text-slate-200">{driver.title}</div>
                  <div className="text-[10px] font-mono text-slate-400">{driver.code}</div>
                </div>
                <span className="font-mono font-bold text-xs text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
                  {driver.count?.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* THIRD ROW (Emerging Risk Clusters) */}
      <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Network className="w-4 h-4 text-cyan-400" />
              Emerging Coordinated Clusters
            </h2>
            <p className="text-[11px] text-slate-400 mt-0.5">Identified candidate multi-hop communities sharing infrastructure and behavior</p>
          </div>
          <button
            onClick={() => onNavigate('clusters')}
            className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium transition-colors"
          >
            Explore Network Graph <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
          {emerging_clusters.map((cluster) => (
            <div
              key={cluster.cluster_id}
              onClick={() => {
                onSelectCluster(cluster.cluster_id);
                onNavigate('clusters');
              }}
              className="p-4 bg-[#090D16] border border-[#1E293B] hover:border-cyan-500/40 rounded-xl cursor-pointer transition-all hover:shadow-lg hover:shadow-cyan-500/5 group"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-xs text-white group-hover:text-cyan-300">
                  {cluster.cluster_id}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  {cluster.account_count} Accts
                </span>
              </div>

              <div className="space-y-1.5 text-xs font-mono mb-3">
                <div className="flex justify-between text-slate-400 text-[11px]">
                  <span>Peak Risk:</span>
                  <span className="font-bold text-orange-400">{cluster.maximum_risk_score?.toFixed(1)}</span>
                </div>
                <div className="flex justify-between text-slate-400 text-[11px]">
                  <span>Avg Risk:</span>
                  <span className="text-slate-200">{cluster.average_risk_score?.toFixed(1)}</span>
                </div>
                <div className="flex justify-between text-slate-400 text-[11px]">
                  <span>Graph Strength:</span>
                  <span className="text-slate-200">{cluster.average_graph_strength?.toFixed(2)}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-[#1E293B] flex items-center justify-between text-[10px] font-mono text-slate-400">
                <span className="capitalize text-amber-400">{cluster.recommended_action}</span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 group-hover:translate-x-0.5 transition-all" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* SYNTHETIC BENCHMARK TRANSPARENCY DISCLAIMER */}
      <div className="bg-[#111726]/60 border border-[#1E293B] rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5">
          <Info className="w-4 h-4 text-cyan-400 shrink-0" />
          <div className="text-slate-300">
            <strong className="text-white">Synthetic Benchmark:</strong> Dataset contains simulated account and transaction behavior created for defensive evaluation. It does not represent real Razorpay customer data.
          </div>
        </div>
        <div className="text-[10px] font-mono text-slate-400 bg-[#090D16] px-2.5 py-1 rounded border border-[#1E293B] shrink-0 self-start sm:self-auto">
          Deterministic Defense Evaluation
        </div>
      </div>
    </div>
  );
}
