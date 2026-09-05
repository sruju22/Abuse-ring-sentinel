import React, { useState, useEffect } from 'react';
import {
  Network,
  ShieldAlert,
  AlertTriangle,
  ExternalLink,
  ChevronRight,
  Smartphone,
  Globe,
  Target,
  Users,
  Activity,
  Layers,
  Clock,
  Zap,
  Filter,
  ArrowRight,
  Share2,
  CheckCircle,
  HelpCircle,
  TrendingUp,
} from 'lucide-react';
import { api } from '../services/api';
import NetworkGraph from '../components/graph/NetworkGraph';
import { formatINR } from '../utils/currency';

export default function RiskClusters({ selectedClusterId, onSelectCluster, onSelectAccount, onNavigate }) {
  const [clusters, setClusters] = useState([]);
  const [activeClusterId, setActiveClusterId] = useState(selectedClusterId || 'CLUSTER_001');
  const [clusterDetail, setClusterDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(false);

  // Coordination Timeline filter state
  const [timelineFilter, setTimelineFilter] = useState('ALL'); // 'ALL', 'BURST_ONLY', 'CASHOUT_ONLY'
  const [timelineSearch, setTimelineSearch] = useState('');

  // Load cluster summaries
  useEffect(() => {
    let mounted = true;
    api
      .getClusters()
      .then((res) => {
        if (mounted) {
          setClusters(res);
          if (!selectedClusterId && res.length > 0) {
            setActiveClusterId(res[0].cluster_id);
          }
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Sync external selectedClusterId prop
  useEffect(() => {
    if (selectedClusterId) {
      setActiveClusterId(selectedClusterId);
    }
  }, [selectedClusterId]);

  // Load active cluster network graph, timeline & members
  useEffect(() => {
    if (!activeClusterId) return;
    let mounted = true;
    setGraphLoading(true);
    api
      .getClusterDetail(activeClusterId)
      .then((res) => {
        if (mounted) {
          setClusterDetail(res);
          setGraphLoading(false);
        }
      })
      .catch(() => {
        if (mounted) setGraphLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [activeClusterId]);

  const handleNodeSelect = (node) => {
    if (node.type === 'account') {
      onSelectAccount(node.id);
      onNavigate('investigations');
    }
  };

  // Filter timeline events
  const filteredTimeline = (clusterDetail?.coordination_timeline || []).filter((tx) => {
    if (timelineFilter === 'BURST_ONLY' && !tx.is_burst) return false;
    if (timelineFilter === 'CASHOUT_ONLY' && !['cashout', 'p2p_transfer', 'withdrawal'].includes(tx.transaction_type?.toLowerCase())) return false;
    if (timelineSearch && !tx.account_id.toLowerCase().includes(timelineSearch.toLowerCase()) && !tx.transaction_id.toLowerCase().includes(timelineSearch.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1E293B]/70 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <Network className="w-5 h-5 text-cyan-400" />
              Risk Clusters Investigation
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-[10px] font-mono font-semibold uppercase">
              Louvain Graph Intelligence
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Cluster Overview → Member Accounts → Subgraph Visualization → Shared Behavioral Patterns → Timeline of Events → Composite Risk Explanation
          </p>
        </div>
      </div>

      {/* 1. CLUSTER CARDS SWITCHER (SECTION 6) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
        {clusters.map((c) => {
          const isActive = activeClusterId === c.cluster_id;
          return (
            <button
              key={c.cluster_id}
              onClick={() => {
                setActiveClusterId(c.cluster_id);
                if (onSelectCluster) onSelectCluster(c.cluster_id);
              }}
              className={`p-4 rounded-xl border text-left font-mono transition-all relative overflow-hidden ${
                isActive
                  ? 'bg-cyan-500/10 border-cyan-500/60 shadow-lg shadow-cyan-500/10'
                  : 'bg-[#111726] border-[#1E293B] hover:border-slate-600 hover:bg-[#151C2C]'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className={`text-xs font-bold ${isActive ? 'text-cyan-300' : 'text-white'}`}>
                  {c.cluster_id}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-[#1E293B] text-slate-200 font-bold">
                  {c.account_count} Accts
                </span>
              </div>

              <div className="space-y-1 text-xs">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Avg Risk:</span>
                  <span className="font-bold text-white">{c.average_risk_score?.toFixed(1)}</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Peak Risk:</span>
                  <span className="font-bold text-orange-400">{c.maximum_risk_score?.toFixed(1)}</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Graph Strength:</span>
                  <span className="text-indigo-400 font-bold">{c.average_graph_strength?.toFixed(2)}</span>
                </div>
              </div>

              <div className="pt-2 mt-2 border-t border-[#1E293B] flex items-center justify-between text-[10px]">
                <span className="capitalize text-cyan-400">{c.recommended_action}</span>
                <span className="text-slate-500">{c.risk_level}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* 2. "WHY THIS CLUSTER MATTERS" & DOMINANT TYPOLOGY (SECTION 5 & 7) */}
      {clusterDetail?.why_cluster_matters && (
        <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#1E293B] pb-3">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-orange-500/10 border border-orange-500/20 text-orange-400">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-white font-mono uppercase">
                    Why This Cluster Matters: {clusterDetail.why_cluster_matters.typology_label}
                  </h2>
                  <span className="px-2 py-0.5 rounded bg-orange-500/20 text-orange-400 text-[10px] font-mono font-bold">
                    {clusterDetail.why_cluster_matters.dominant_typology}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  {clusterDetail.why_cluster_matters.typology_description}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs font-mono">
              <div className="text-right">
                <div className="text-[10px] text-slate-400">Synchronized Bursts</div>
                <div className="font-bold text-pink-400">
                  {clusterDetail.why_cluster_matters.burst_percentage}% of events
                </div>
              </div>
              <div className="text-right">
                <div className="text-[10px] text-slate-400">Shared Hardware</div>
                <div className="font-bold text-indigo-400">
                  {clusterDetail.why_cluster_matters.shared_devices_count} Devices
                </div>
              </div>
              <div className="text-right">
                <div className="text-[10px] text-slate-400">Shared IPs</div>
                <div className="font-bold text-cyan-400">
                  {clusterDetail.why_cluster_matters.shared_ips_count} IPs
                </div>
              </div>
            </div>
          </div>

          {/* Key Relationship Bullets */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
            {clusterDetail.why_cluster_matters.strongest_relationships?.map((rel, i) => (
              <div key={i} className="p-2.5 bg-[#090D16] border border-[#1E293B] rounded-lg flex items-center gap-2 text-slate-300">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                <span>{rel}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. NETWORK GRAPH & MEMBER ACCOUNTS (SECTION 5 & 6) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Interactive Graph Canvas */}
        <div className="lg:col-span-8 space-y-4">
          <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 font-mono">
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Abuse Ring Graph: {activeClusterId}
                </span>
                <span className="text-[10px] text-slate-400">
                  ({clusterDetail?.network_graph?.nodes?.length || 0} Entities • {clusterDetail?.network_graph?.links?.length || 0} Links)
                </span>
              </div>
              <div className="text-[11px] font-mono text-cyan-400">
                Click any Account Node to open investigation
              </div>
            </div>

            {graphLoading || !clusterDetail ? (
              <div className="h-[520px] flex items-center justify-center bg-[#090D16] rounded-xl border border-[#1E293B]">
                <div className="flex flex-col items-center gap-2 text-xs font-mono text-slate-400">
                  <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                  <span>Computing topological projection...</span>
                </div>
              </div>
            ) : (
              <NetworkGraph
                nodes={clusterDetail.network_graph.nodes}
                links={clusterDetail.network_graph.links}
                onSelectNode={handleNodeSelect}
                height={520}
              />
            )}
          </div>
        </div>

        {/* Member Accounts Drawer */}
        <div className="lg:col-span-4 space-y-4">
          {clusterDetail && (
            <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 space-y-3 font-mono flex flex-col h-[580px]">
              <div className="flex items-center justify-between border-b border-[#1E293B] pb-2.5">
                <span className="text-xs font-bold text-white uppercase flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-cyan-400" />
                  Member Accounts ({clusterDetail.member_accounts?.length || 0})
                </span>
                <span className="text-[10px] text-slate-400">Sorted by Risk</span>
              </div>

              <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
                {clusterDetail.member_accounts?.map((m) => (
                  <div
                    key={m.account_id}
                    onClick={() => {
                      onSelectAccount(m.account_id);
                      onNavigate('investigations');
                    }}
                    className="p-2.5 bg-[#090D16] border border-[#1E293B] hover:border-cyan-500/40 rounded-lg cursor-pointer transition-all flex items-center justify-between text-xs group"
                  >
                    <div>
                      <div className="font-bold text-white group-hover:text-cyan-300 flex items-center gap-1.5">
                        <span>{m.account_id}</span>
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5 capitalize">
                        {m.recommended_action}
                      </div>
                    </div>

                    <div className="text-right">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                          m.final_risk_score >= 80
                            ? 'bg-red-500/20 text-red-400'
                            : m.final_risk_score >= 60
                            ? 'bg-orange-500/20 text-orange-400'
                            : 'bg-amber-500/20 text-amber-400'
                        }`}
                      >
                        {m.final_risk_score?.toFixed(1)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="pt-2 border-t border-[#1E293B] text-[10px] text-slate-500">
                Click any member account to navigate directly to its telemetry profile.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 4. COORDINATION TIMELINE (SECTION 7) */}
      <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#1E293B] pb-3">
          <div>
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-pink-400" />
              <h2 className="text-sm font-bold text-white font-mono uppercase">
                Coordination Timeline: {activeClusterId}
              </h2>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Chronological sequence of cross-account transactions. Synchronized burst events occur within ≤ 30-minute intervals.
            </p>
          </div>

          {/* Timeline Filter Controls */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            <div className="flex items-center bg-[#090D16] border border-[#1E293B] rounded-lg p-1">
              <button
                onClick={() => setTimelineFilter('ALL')}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                  timelineFilter === 'ALL' ? 'bg-cyan-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                All Events
              </button>
              <button
                onClick={() => setTimelineFilter('BURST_ONLY')}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors flex items-center gap-1 ${
                  timelineFilter === 'BURST_ONLY' ? 'bg-pink-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Zap className="w-3 h-3" />
                <span>Bursts Only (≤30m)</span>
              </button>
              <button
                onClick={() => setTimelineFilter('CASHOUT_ONLY')}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                  timelineFilter === 'CASHOUT_ONLY' ? 'bg-amber-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Cashouts / P2P
              </button>
            </div>
          </div>
        </div>

        {/* Timeline Table */}
        <div className="overflow-x-auto max-h-[420px] overflow-y-auto pr-1">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-[#1E293B] text-slate-400 text-[10px] uppercase sticky top-0 bg-[#111726] z-10">
                <th className="pb-2.5 font-semibold">Timestamp</th>
                <th className="pb-2.5 font-semibold">Account ID</th>
                <th className="pb-2.5 font-semibold">Delta from Prev</th>
                <th className="pb-2.5 font-semibold">Amount</th>
                <th className="pb-2.5 font-semibold">Type</th>
                <th className="pb-2.5 font-semibold">Destination / Merchant</th>
                <th className="pb-2.5 font-semibold">Status</th>
                <th className="pb-2.5 font-semibold text-right">Coordination Flag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E293B]/60">
              {filteredTimeline.length === 0 ? (
                <tr>
                  <td colSpan="8" className="py-8 text-center text-slate-500">
                    No transactions match current timeline filter.
                  </td>
                </tr>
              ) : (
                filteredTimeline.map((tx) => (
                  <tr key={tx.transaction_id} className="hover:bg-[#151C2C] transition-colors">
                    {/* Timestamp */}
                    <td className="py-2.5 text-slate-300 font-semibold">{tx.timestamp}</td>

                    {/* Account */}
                    <td className="py-2.5 font-bold text-cyan-400 hover:text-cyan-300 cursor-pointer"
                      onClick={() => {
                        onSelectAccount(tx.account_id);
                        onNavigate('investigations');
                      }}
                    >
                      {tx.account_id}
                    </td>

                    {/* Delta */}
                    <td className="py-2.5 text-slate-400">
                      {tx.diff_minutes != null ? (
                        <span className={tx.is_burst ? 'text-pink-400 font-bold' : 'text-slate-400'}>
                          +{tx.diff_minutes} min
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>

                    {/* Amount */}
                    <td className="py-2.5 font-bold text-white">{formatINR(tx.amount)}</td>

                    {/* Type */}
                    <td className="py-2.5 capitalize text-slate-300">{tx.transaction_type}</td>

                    {/* Destination */}
                    <td className="py-2.5 text-slate-400">
                      {tx.destination_id ? (
                        <span className="text-amber-400 font-semibold">{tx.destination_id}</span>
                      ) : (
                        tx.merchant_id || '—'
                      )}
                    </td>

                    {/* Status */}
                    <td className="py-2.5">
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded ${
                          tx.status === 'SUCCESS' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                        }`}
                      >
                        {tx.status}
                      </span>
                    </td>

                    {/* Typology Marker */}
                    <td className="py-2.5 text-right">
                      {tx.is_burst ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-pink-500/20 text-pink-400 border border-pink-500/30 text-[10px] font-bold">
                          <Zap className="w-3 h-3" />
                          <span>Burst Window (≤30m)</span>
                        </span>
                      ) : (
                        <span className="text-slate-600 text-[10px]">Routine Flow</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
