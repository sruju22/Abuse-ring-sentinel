import React, { useState, useEffect, useMemo } from 'react';
import {
  Network,
  ShieldAlert,
  AlertTriangle,
  ChevronRight,
  Users,
  Activity,
  Layers,
  Zap,
  Search,
  Info,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../services/api';
import NetworkGraph from '../components/graph/NetworkGraph';
import { formatINR } from '../utils/currency';

export default function RiskClusters({
  selectedClusterId,
  onSelectCluster,
  onSelectAccount,
  onNavigate,
}) {
  const [clusters, setClusters] = useState([]);
  const [activeClusterId, setActiveClusterId] = useState(selectedClusterId || 'CLUSTER_056');
  const [clusterDetail, setClusterDetail] = useState(null);
  const [sortBy, setSortBy] = useState('high_risk_count');
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [memberSearch, setMemberSearch] = useState('');
  const [evidenceFilter, setEvidenceFilter] = useState('ALL');
  const [showRelsDrawer, setShowRelsDrawer] = useState(false);
  const [relsLimit, setRelsLimit] = useState(25);

  // 1. Fetch Clusters List
  useEffect(() => {
    let mounted = true;
    setLoadingList(true);
    api.investigations
      .getClusters({ limit: 50, sortBy })
      .then((res) => {
        if (mounted) {
          const list = res.clusters || [];
          setClusters(list);
          if (!selectedClusterId && list.length > 0) {
            setActiveClusterId(list[0].cluster_id);
          }
          setLoadingList(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          console.error('Failed to load clusters:', err);
          setLoadingList(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [sortBy]);

  // Sync external selectedClusterId prop
  useEffect(() => {
    if (selectedClusterId) {
      setActiveClusterId(selectedClusterId);
    }
  }, [selectedClusterId]);

  // 2. Fetch Active Cluster Detail
  useEffect(() => {
    if (!activeClusterId) return;
    let mounted = true;
    setLoadingDetail(true);
    api.investigations
      .getClusterDetail(activeClusterId)
      .then((res) => {
        if (mounted) {
          setClusterDetail(res);
          setLoadingDetail(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          console.error(`Failed to load cluster ${activeClusterId}:`, err);
          setLoadingDetail(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [activeClusterId]);

  // Navigate to Account Investigation
  const handleInspectAccount = (accountId) => {
    if (onSelectAccount) onSelectAccount(accountId);
    if (onNavigate) onNavigate('investigations');
  };

  // Format Graph Nodes & Links with Complete Infrastructure & Component Topology
  const graphData = useMemo(() => {
    if (!clusterDetail) return { nodes: [], links: [] };

    const nodeMap = new Map();
    const linkList = [];
    const linkKeys = new Set();

    // Map high-risk probabilities
    const highRiskMap = new Map(
      (clusterDetail.high_risk_members || []).map((m) => [
        m.account_id,
        m.calibrated_probability != null ? m.calibrated_probability * 100 : 85,
      ])
    );
    const probMap = new Map(
      (clusterDetail.high_risk_members || []).map((m) => [
        m.account_id,
        m.calibrated_probability != null ? m.calibrated_probability : 0.85,
      ])
    );

    // Filter relationships by active evidence filter
    const allRels = clusterDetail.top_relationships || [];
    const rels =
      evidenceFilter === 'ALL'
        ? allRels
        : allRels.filter((r) => r.evidence_type === evidenceFilter);

    // 1. Process relationships and shared infrastructure entities
    rels.forEach((rel) => {
      // Ensure source and target accounts are present
      if (!nodeMap.has(rel.source_account)) {
        nodeMap.set(rel.source_account, {
          id: rel.source_account,
          label: rel.source_account,
          type: 'account',
          risk_score: highRiskMap.get(rel.source_account) != null ? highRiskMap.get(rel.source_account) : 25,
          probability: probMap.get(rel.source_account) != null ? probMap.get(rel.source_account) : 0.25,
        });
      }
      if (!nodeMap.has(rel.target_account)) {
        nodeMap.set(rel.target_account, {
          id: rel.target_account,
          label: rel.target_account,
          type: 'account',
          risk_score: highRiskMap.get(rel.target_account) != null ? highRiskMap.get(rel.target_account) : 25,
          probability: probMap.get(rel.target_account) != null ? probMap.get(rel.target_account) : 0.25,
        });
      }

      // If there is a shared hardware/network entity, add it to the graph
      const hasSharedEntity =
        rel.shared_entity_id &&
        rel.shared_entity_id !== 'BURST_WINDOW_300S' &&
        rel.evidence_type !== 'TIMING_SYNCHRONY';

      if (hasSharedEntity) {
        const entId = rel.shared_entity_id;
        if (!nodeMap.has(entId)) {
          let entType = 'destination';
          if (rel.evidence_type === 'SHARED_DEVICE' || entId.startsWith('DEV_')) {
            entType = 'device';
          } else if (rel.evidence_type === 'SHARED_IP' || entId.startsWith('IP_')) {
            entType = 'ip';
          }

          nodeMap.set(entId, {
            id: entId,
            label: entId,
            type: entType,
          });
        }

        const k1 = `${rel.source_account}->${entId}`;
        if (!linkKeys.has(k1)) {
          linkKeys.add(k1);
          linkList.push({
            source: rel.source_account,
            target: entId,
            type: rel.evidence_type.toLowerCase(),
            strength: rel.evidence_strength,
          });
        }

        const k2 = `${entId}->${rel.target_account}`;
        if (!linkKeys.has(k2)) {
          linkKeys.add(k2);
          linkList.push({
            source: entId,
            target: rel.target_account,
            type: rel.evidence_type.toLowerCase(),
            strength: rel.evidence_strength,
          });
        }
      } else {
        const k = `${rel.source_account}->${rel.target_account}`;
        if (!linkKeys.has(k)) {
          linkKeys.add(k);
          linkList.push({
            source: rel.source_account,
            target: rel.target_account,
            type: (rel.evidence_type || 'coordination').toLowerCase(),
            strength: rel.evidence_strength,
          });
        }
      }
    });

    // 2. Guarantee 100% account representation when viewing complete cluster topology
    if (evidenceFilter === 'ALL') {
      (clusterDetail.member_account_ids || []).forEach((accId) => {
        if (!nodeMap.has(accId)) {
          nodeMap.set(accId, {
            id: accId,
            label: `${accId} (Unlinked)`,
            type: 'account',
            risk_score: highRiskMap.get(accId) != null ? highRiskMap.get(accId) : 25,
            probability: probMap.get(accId) != null ? probMap.get(accId) : 0.25,
            isSingleton: true,
          });
        }
      });
    }

    return {
      nodes: Array.from(nodeMap.values()),
      links: linkList,
    };
  }, [clusterDetail, evidenceFilter]);

  const filteredRelationships = useMemo(() => {
    const list = clusterDetail?.top_relationships || [];
    if (evidenceFilter === 'ALL') return list;
    return list.filter((r) => r.evidence_type === evidenceFilter);
  }, [clusterDetail, evidenceFilter]);

  const filteredHighRiskMembers = useMemo(() => {
    if (!clusterDetail?.high_risk_members) return [];
    if (!memberSearch.trim()) return clusterDetail.high_risk_members;
    const term = memberSearch.trim().toLowerCase();
    return clusterDetail.high_risk_members.filter((m) =>
      m.account_id.toLowerCase().includes(term)
    );
  }, [clusterDetail, memberSearch]);

  const connMeta = clusterDetail?.connectivity_metadata;
  const compCount = connMeta?.connected_components_count ?? 1;
  const representedAccs = connMeta?.represented_accounts_count ?? clusterDetail?.num_members ?? 0;
  const totalAccs = clusterDetail?.num_members ?? 0;
  const totalRels = connMeta?.total_relationships_count ?? (clusterDetail?.top_relationships?.length || 0);

  return (
    <div className="space-y-4 pb-12">
      {/* 1. Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#E2E0D8] pb-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-extrabold text-[#252B29] tracking-tight flex items-center gap-2">
              <Network className="w-5 h-5 text-[#147D69]" />
              Risk Clusters Investigation
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-[#147D69]/10 border border-[#147D69]/25 text-[#147D69] text-[10px] font-mono font-semibold">
              299 Louvain Communities
            </span>
          </div>
          <p className="text-xs text-[#737A76] mt-0.5">
            Complete multi-hop entity graphs annotated with calibrated CatBoost risk distributions
          </p>
        </div>

        {/* Sort Switcher */}
        <div className="flex items-center gap-2 text-xs font-mono self-start md:self-auto">
          <span className="text-[#737A76]">Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-white border border-[#E2E0D8] rounded-lg px-2.5 py-1 text-xs text-[#252B29] font-mono focus:outline-none focus:border-[#147D69]"
          >
            <option value="high_risk_count">High-Risk Members (P &ge; 0.35)</option>
            <option value="high_risk_ratio">High-Risk Ratio (%)</option>
            <option value="num_members">Member Count</option>
          </select>
        </div>
      </div>

      {/* 2. Compact Retrospective Notice */}
      <div className="px-3.5 py-2 bg-[#B99A45]/10 border border-[#B99A45]/30 rounded-lg text-xs font-mono text-[#B99A45] flex items-center justify-between gap-3">
        <span className="flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-[#B99A45] shrink-0" />
          <span>
            <strong>Retrospective Post-Hoc Audit Context:</strong> 30-day macro communities were identified via global graph partitioning and were not available at prediction cutoff (T_obs).
          </span>
        </span>
        <span className="text-[10px] text-[#B99A45]/80 shrink-0 uppercase font-bold">Audit Mode</span>
      </div>

      {/* 3. Horizontal Cluster Switcher Cards */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs font-mono text-[#737A76]">
          <span>Active Communities ({clusters.length}):</span>
          <span>Click to select cluster</span>
        </div>

        {loadingList ? (
          <div className="p-4 bg-white border border-[#E2E0D8] rounded-xl text-center text-xs font-mono text-[#737A76]">
            Loading communities...
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 max-h-36 overflow-y-auto pr-1">
            {clusters.map((c) => {
              const isActive = activeClusterId === c.cluster_id;
              return (
                <button
                  key={c.cluster_id}
                  onClick={() => {
                    setActiveClusterId(c.cluster_id);
                    if (onSelectCluster) onSelectCluster(c.cluster_id);
                  }}
                  className={`p-2.5 rounded-xl border text-left font-mono transition-all ${
                    isActive
                      ? 'bg-[#147D69]/10 border-[#147D69]/60 shadow-sm'
                      : 'bg-white border-[#E2E0D8] hover:border-[#737A76] hover:bg-[#F7F6F2]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-bold ${isActive ? 'text-[#147D69]' : 'text-[#252B29]'}`}>
                      {c.cluster_id}
                    </span>
                    <span className="text-[9px] px-1 py-0.2 rounded bg-[#F3F1EB] text-[#3D4543] font-bold">
                      {c.num_members}
                    </span>
                  </div>
                  <div className="text-[10px] flex justify-between text-[#737A76]">
                    <span>High Risk:</span>
                    <span className={`font-bold ${c.high_risk_count > 0 ? 'text-[#C64B43]' : 'text-[#3D4543]'}`}>
                      {c.high_risk_count} ({((c.high_risk_ratio || 0) * 100).toFixed(0)}%)
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Active Cluster Detail & Graph Workspace */}
      {loadingDetail || !clusterDetail ? (
        <div className="bg-white border border-[#E2E0D8] rounded-xl p-12 text-center text-[#737A76] font-mono text-xs">
          <div className="flex items-center justify-center gap-2">
            <div className="w-4 h-4 border-2 border-[#147D69] border-t-transparent rounded-full animate-spin" />
            <span>Loading complete cluster telemetry and graph topology for {activeClusterId}...</span>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Top 3 Metric Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            <div className="bg-white border border-[#E2E0D8] rounded-xl p-3.5 space-y-1.5 font-mono shadow-sm">
              <div className="flex items-center justify-between text-[#737A76] text-[10px] uppercase font-semibold">
                <span>CatBoost Risk Distribution</span>
                <ShieldAlert className="w-3.5 h-3.5 text-[#147D69]" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black text-[#252B29]">
                  {((clusterDetail.ml_risk_distribution?.high_risk_ratio || 0) * 100).toFixed(1)}%
                </span>
                <span className="text-xs text-[#C64B43] font-bold">
                  ({clusterDetail.ml_risk_distribution?.high_risk_count} &ge; 0.35 Threshold)
                </span>
              </div>
              <div className="text-[10px] text-[#737A76] pt-1 border-t border-[#E2E0D8] flex justify-between">
                <span>Mean: {clusterDetail.ml_risk_distribution?.mean_probability?.toFixed(3)}</span>
                <span>Max: {clusterDetail.ml_risk_distribution?.max_probability?.toFixed(3)}</span>
              </div>
            </div>

            <div className="bg-white border border-[#E2E0D8] rounded-xl p-3.5 space-y-1.5 font-mono shadow-sm">
              <div className="flex items-center justify-between text-[#737A76] text-[10px] uppercase font-semibold">
                <span>Community Topology</span>
                <Users className="w-3.5 h-3.5 text-[#7C6EAF]" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black text-[#252B29]">
                  {clusterDetail.num_members}
                </span>
                <span className="text-xs text-[#147D69] font-bold">
                  ({compCount === 1 ? '1 Unified Ring' : `${compCount} Components`})
                </span>
              </div>
              <div className="text-[10px] text-[#737A76] pt-1 border-t border-[#E2E0D8] flex justify-between">
                <span>Connected: {representedAccs}/{totalAccs}</span>
                <span>Links: {totalRels} total</span>
              </div>
            </div>

            <div className="bg-white border border-[#E2E0D8] rounded-xl p-3.5 space-y-1.5 font-mono shadow-sm">
              <div className="flex items-center justify-between text-[#737A76] text-[10px] uppercase font-semibold">
                <span>Observed 30-Day Activity</span>
                <Activity className="w-3.5 h-3.5 text-[#147D69]" />
              </div>
              <div className="text-2xl font-black text-[#252B29]">
                {formatINR(clusterDetail.temporal_span?.total_volume || 0)}
              </div>
              <div className="text-[10px] text-[#737A76] pt-1 border-t border-[#E2E0D8] flex justify-between">
                <span>{clusterDetail.temporal_span?.total_transactions || 0} Transactions</span>
                <span>Span: 30 Days</span>
              </div>
            </div>
          </div>

          {/* Main Grid: High-Risk Members (Left) & Network Graph (Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Left: High-Risk Members Table */}
            <div className="lg:col-span-5 bg-white border border-[#E2E0D8] rounded-xl p-3.5 space-y-2.5 shadow-sm">
              <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
                <h3 className="text-xs font-bold text-[#252B29] font-mono uppercase flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5 text-[#147D69]" />
                  High-Risk Members ({filteredHighRiskMembers.length})
                </h3>
                <span className="text-[10px] text-[#737A76] font-mono">P &ge; 0.35</span>
              </div>

              {/* Member Search */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-[#737A76] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Filter member ID..."
                  value={memberSearch}
                  onChange={(e) => setMemberSearch(e.target.value)}
                  className="w-full bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg pl-8 pr-3 py-1 text-xs text-[#252B29] placeholder-[#9BA09D] font-mono focus:outline-none focus:border-[#147D69]"
                />
              </div>

              {/* Members List */}
              <div className="max-h-[420px] overflow-y-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-[#E2E0D8] text-[#737A76] text-[10px] uppercase">
                      <th className="pb-1.5 font-semibold">Account ID</th>
                      <th className="pb-1.5 font-semibold">P(Abuse)</th>
                      <th className="pb-1.5 font-semibold text-right">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E0D8]/60">
                    {filteredHighRiskMembers.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="py-6 text-center text-[#9BA09D] font-mono text-xs">
                          No member accounts exceed threshold.
                        </td>
                      </tr>
                    ) : (
                      filteredHighRiskMembers.map((member) => (
                        <tr key={member.account_id} className="hover:bg-[#F7F6F2] transition-colors">
                          <td className="py-2 font-bold text-[#147D69]">{member.account_id}</td>
                          <td className="py-2 font-extrabold text-[#C64B43]">
                            {member.calibrated_probability?.toFixed(4)}
                          </td>
                          <td className="py-2 text-right">
                            <button
                              onClick={() => handleInspectAccount(member.account_id)}
                              className="px-2 py-0.5 bg-[#F7F6F2] hover:bg-[#147D69] hover:text-white text-[#147D69] rounded border border-[#E2E0D8] text-[10px] font-bold transition-all inline-flex items-center gap-1"
                            >
                              Deep-Dive <ChevronRight className="w-3 h-3" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Right: Network Graph + Expandable Evidence Drawer */}
            <div className="lg:col-span-7 space-y-3">
              <div className="bg-white border border-[#E2E0D8] rounded-xl p-3.5 space-y-2.5 shadow-sm">
                <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
                  <h3 className="text-xs font-bold text-[#252B29] font-mono uppercase flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-[#147D69]" />
                    Internal Cluster Subgraph ({activeClusterId})
                  </h3>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-[#737A76] font-mono">Red: P &ge; 0.35</span>
                  </div>
                </div>

                {/* Connectivity & Evidence Layer Toolbar */}
                <div className="bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg p-2.5 space-y-2 font-mono text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          compCount === 1
                            ? 'bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30'
                            : 'bg-[#B99A45]/10 text-[#B99A45] border border-[#B99A45]/30'
                        }`}
                      >
                        {compCount === 1 ? '1 Connected Component' : `${compCount} Connected Components`}
                      </span>
                      <span className="text-[11px] text-[#3D4543] font-semibold">
                        {representedAccs} / {totalAccs} Accounts Represented (
                        {totalAccs > 0 ? ((representedAccs / totalAccs) * 100).toFixed(0) : 0}%)
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-[10px] text-[#147D69]">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Complete Graph ({totalRels} links)</span>
                    </div>
                  </div>

                  {/* Filter Pills */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-[#E2E0D8]">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-[#737A76] mr-1">Layer:</span>
                      <button
                        onClick={() => setEvidenceFilter('ALL')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition-colors ${
                          evidenceFilter === 'ALL'
                            ? 'bg-[#147D69] text-white shadow-sm'
                            : 'bg-white text-[#737A76] border border-[#E2E0D8] hover:text-[#252B29] hover:bg-[#F3F1EB]'
                        }`}
                      >
                        All ({totalRels})
                      </button>
                      <button
                        onClick={() => setEvidenceFilter('SHARED_DEVICE')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition-colors ${
                          evidenceFilter === 'SHARED_DEVICE'
                            ? 'bg-[#7C6EAF] text-white shadow-sm'
                            : 'bg-white text-[#737A76] border border-[#E2E0D8] hover:text-[#252B29] hover:bg-[#F3F1EB]'
                        }`}
                      >
                        Device ({connMeta?.relationships_by_type?.SHARED_DEVICE || 0})
                      </button>
                      <button
                        onClick={() => setEvidenceFilter('SHARED_IP')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition-colors ${
                          evidenceFilter === 'SHARED_IP'
                            ? 'bg-[#4E9BB5] text-white shadow-sm'
                            : 'bg-white text-[#737A76] border border-[#E2E0D8] hover:text-[#252B29] hover:bg-[#F3F1EB]'
                        }`}
                      >
                        IP ({connMeta?.relationships_by_type?.SHARED_IP || 0})
                      </button>
                      <button
                        onClick={() => setEvidenceFilter('SHARED_DESTINATION')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition-colors ${
                          evidenceFilter === 'SHARED_DESTINATION'
                            ? 'bg-[#D58A27] text-white shadow-sm'
                            : 'bg-white text-[#737A76] border border-[#E2E0D8] hover:text-[#252B29] hover:bg-[#F3F1EB]'
                        }`}
                      >
                        Destination ({connMeta?.relationships_by_type?.SHARED_DESTINATION || 0})
                      </button>
                    </div>

                    <div className="text-[10px] text-[#737A76]">
                      Nodes: {graphData.nodes.filter((n) => n.type === 'account').length} accs •{' '}
                      {graphData.nodes.filter((n) => n.type !== 'account').length} hubs
                    </div>
                  </div>
                </div>

                <div className="rounded-lg overflow-hidden border border-[#E2E0D8] bg-[#F7F6F2]">
                  <NetworkGraph
                    nodes={graphData.nodes}
                    links={graphData.links}
                    onInspectAccount={(targetAccId) => handleInspectAccount(targetAccId)}
                    height={460}
                    hideEdgeFilter={true}
                    defaultLayout="bipartite"
                  />
                </div>
              </div>

              {/* Progressive Disclosure: Collapsible Internal Relationships Accordion */}
              <div className="bg-white border border-[#E2E0D8] rounded-xl p-3 shadow-sm">
                <button
                  onClick={() => setShowRelsDrawer(!showRelsDrawer)}
                  className="w-full flex items-center justify-between text-xs font-mono font-bold text-[#3D4543] hover:text-[#252B29] transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-[#147D69]" />
                    <span>
                      Corroborated Internal Relationships ({filteredRelationships.length}
                      {evidenceFilter !== 'ALL' ? ` in ${evidenceFilter.replace('SHARED_', '')}` : ''})
                    </span>
                  </span>
                  {showRelsDrawer ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                {showRelsDrawer && (
                  <div className="mt-2.5 space-y-2 border-t border-[#E2E0D8] pt-2">
                    <div className="max-h-56 overflow-y-auto space-y-1.5 pr-1">
                      {filteredRelationships.length === 0 ? (
                        <div className="py-4 text-center text-[#9BA09D] font-mono text-xs">
                          No internal corroborated links for active filter.
                        </div>
                      ) : (
                        filteredRelationships.slice(0, relsLimit).map((rel, rIdx) => (
                          <div
                            key={rIdx}
                            className="p-2 rounded bg-[#F7F6F2] border border-[#E2E0D8] text-xs font-mono space-y-0.5"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-[#147D69]">
                                {rel.source_account} &harr; {rel.target_account}
                              </span>
                              <span
                                className={`text-[9px] px-1.5 py-0.2 rounded font-semibold ${
                                  rel.evidence_type === 'SHARED_DEVICE'
                                    ? 'bg-[#7C6EAF]/10 text-[#7C6EAF] border border-[#7C6EAF]/25'
                                    : rel.evidence_type === 'SHARED_IP'
                                    ? 'bg-[#4E9BB5]/10 text-[#4E9BB5] border border-[#4E9BB5]/25'
                                    : 'bg-[#D58A27]/10 text-[#D58A27] border border-[#D58A27]/25'
                                }`}
                              >
                                {rel.evidence_type}
                              </span>
                            </div>
                            <p className="text-[11px] text-[#737A76]">{rel.explanation}</p>
                          </div>
                        ))
                      )}
                    </div>

                    {filteredRelationships.length > relsLimit && (
                      <div className="text-center pt-1 border-t border-[#E2E0D8]/60">
                        <button
                          onClick={() => setRelsLimit((prev) => prev + 50)}
                          className="px-3 py-1 bg-[#F7F6F2] hover:bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30 rounded text-[10px] font-mono font-bold transition-colors"
                        >
                          Load More Relationships ({relsLimit} of {filteredRelationships.length} displayed)
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
