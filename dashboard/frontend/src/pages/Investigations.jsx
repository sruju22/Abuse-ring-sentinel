import React, { useState, useEffect, useMemo } from 'react';
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
  Calendar,
  Lock,
  Unlock,
  Info,
  SlidersHorizontal,
  Activity,
  ExternalLink,
  CreditCard,
  Sparkles,
} from 'lucide-react';
import { api } from '../services/api';
import NetworkGraph from '../components/graph/NetworkGraph';
import InvestigationCopilot from '../components/copilot/InvestigationCopilot';
import { formatINR } from '../utils/currency';

export default function Investigations({ selectedAccountId, onSelectAccount, onNavigate }) {
  // Navigation: 'table' (Queue Workspace) or 'detail' (Account Deep-Dive)
  const [viewMode, setViewMode] = useState(selectedAccountId ? 'detail' : 'table');

  // AI Investigation Copilot drawer open state
  const [isCopilotOpen, setIsCopilotOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return new URLSearchParams(window.location.search).get('copilot') === 'true';
    }
    return false;
  });

  // Active sub-tab in Detail view: 'evidence' | 'timeline' | 'triage'
  const [detailTab, setDetailTab] = useState('evidence');

  // Investigation Mode: 'predictive' (t <= T_obs) or 'retrospective' (all 30 days)
  const [investigationMode, setInvestigationMode] = useState('predictive');

  // Filters state
  const [search, setSearch] = useState('');
  const [riskTierFilter, setRiskTierFilter] = useState('ALL');
  const [hasSharedDevice, setHasSharedDevice] = useState('ALL');

  // Queue data state
  const [queueItems, setQueueItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [decisionThreshold, setDecisionThreshold] = useState(0.35);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [loadingQueue, setLoadingQueue] = useState(false);
  const [queueError, setQueueError] = useState(null);

  // Active account deep-dive state
  const [activeAccountId, setActiveAccountId] = useState(selectedAccountId || null);
  const [accountData, setAccountData] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState(null);

  // Human Review triage state
  const [reviewStatus, setReviewStatus] = useState(null);
  const [analystNotes, setAnalystNotes] = useState('');
  const [auditLogs, setAuditLogs] = useState([]);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  // ---------------------------------------------------------------------------
  // 1. Fetch Investigation Queue
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let mounted = true;
    setLoadingQueue(true);
    setQueueError(null);

    const offset = (page - 1) * pageSize;
    api.investigations
      .getQueue({
        limit: pageSize,
        offset,
        riskTier: riskTierFilter,
        hasSharedDevice: hasSharedDevice !== 'ALL' ? hasSharedDevice : undefined,
        sortBy: 'probability',
      })
      .then((res) => {
        if (mounted) {
          setQueueItems(res.items || []);
          setTotalCount(res.total_count || 0);
          if (res.decision_threshold != null) {
            setDecisionThreshold(res.decision_threshold);
          }
          setLoadingQueue(false);

          if (!activeAccountId && res.items?.length > 0) {
            setActiveAccountId(res.items[0].account_id);
          }
        }
      })
      .catch((err) => {
        if (mounted) {
          console.error('Failed to load queue:', err);
          setQueueError(err.message || 'Failed to connect to backend queue service');
          setLoadingQueue(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [page, pageSize, riskTierFilter, hasSharedDevice]);

  // Sync external selectedAccountId prop
  useEffect(() => {
    if (selectedAccountId) {
      setActiveAccountId(selectedAccountId);
      setViewMode('detail');
    }
  }, [selectedAccountId]);

  // ---------------------------------------------------------------------------
  // 2. Fetch Active Account Telemetry & Point-in-Time Timeline
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!activeAccountId) return;
    let mounted = true;
    setLoadingDetail(true);
    setDetailError(null);

    Promise.all([
      api.investigations.getAccount(activeAccountId, investigationMode),
      api.investigations.getTimeline(activeAccountId, investigationMode),
    ])
      .then(([accRes, timeRes]) => {
        if (mounted) {
          setAccountData(accRes);
          setTimelineData(timeRes);
          setLoadingDetail(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          console.error(`Error loading account ${activeAccountId}:`, err);
          setDetailError(err.message || 'Error loading account data');
          setLoadingDetail(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [activeAccountId, investigationMode]);

  // ---------------------------------------------------------------------------
  // 3. Filter Queue by Search Term
  // ---------------------------------------------------------------------------
  const filteredQueueItems = useMemo(() => {
    if (!search.trim()) return queueItems;
    const term = search.trim().toLowerCase();
    return queueItems.filter((item) =>
      item.account_id.toLowerCase().includes(term)
    );
  }, [queueItems, search]);

  // ---------------------------------------------------------------------------
  // 4. Submit Analyst Human Triage Action
  // ---------------------------------------------------------------------------
  const handleTriageAction = async (decision) => {
    if (!activeAccountId) return;
    setIsSubmittingReview(true);
    const event = {
      action_type: decision,
      account_id: activeAccountId,
      performed_by: 'SOC_SENIOR_ANALYST',
      details: {
        mode: investigationMode,
        calibrated_probability: accountData?.ml_prediction?.calibrated_probability,
        risk_tier: accountData?.ml_prediction?.risk_tier,
        notes: analystNotes.trim() || 'Standard investigation triage protocol executed.',
        timestamp: new Date().toISOString(),
      },
    };

    try {
      await api.addAuditEvent(event);
      setReviewStatus(decision);
      setAuditLogs((prev) => [event, ...prev]);
      setAnalystNotes('');
      setIsSubmittingReview(false);
    } catch (e) {
      console.error('Audit submit error:', e);
      setReviewStatus(decision);
      setAuditLogs((prev) => [event, ...prev]);
      setIsSubmittingReview(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Graph Network Format
  // ---------------------------------------------------------------------------
  const graphNodesAndLinks = useMemo(() => {
    if (!accountData) return { nodes: [], links: [] };

    const focalScore = (accountData.ml_prediction?.calibrated_probability || 0.5) * 100;
    const focalNode = {
      id: accountData.account_id,
      label: `${accountData.account_id} (Focal)`,
      type: 'account',
      isFocal: true,
      risk_score: focalScore,
      risk_tier: accountData.ml_prediction?.risk_tier || 'CRITICAL',
    };

    const nodeMap = new Map();
    nodeMap.set(focalNode.id, focalNode);
    const linkList = [];
    const linkKeys = new Set();
    const rels = accountData.relationships || [];

    // Map peer probabilities from queue items if available
    const queueRiskMap = new Map((queueItems || []).map((q) => [q.account_id, q.calibrated_probability]));

    rels.forEach((rel) => {
      const peerId =
        rel.target_account === accountData.account_id
          ? rel.source_account
          : rel.target_account;

      // Add peer account node
      if (!nodeMap.has(peerId)) {
        const peerProb = queueRiskMap.get(peerId);
        const peerScore = peerProb != null ? peerProb * 100 : focalScore > 50 ? 55 : 20;
        nodeMap.set(peerId, {
          id: peerId,
          label: peerId,
          type: 'account',
          risk_score: peerScore,
          isFocal: false,
        });
      }

      // Check for shared infrastructure entity (Device, IP, Destination)
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
            isFocal: false,
          });
        }

        // Bipartite edges connecting through shared entity
        const key1 = `${rel.source_account}->${entId}`;
        if (!linkKeys.has(key1)) {
          linkKeys.add(key1);
          linkList.push({
            source: rel.source_account,
            target: entId,
            type: rel.evidence_type.toLowerCase(),
            strength: rel.evidence_strength,
          });
        }

        const key2 = `${entId}->${rel.target_account}`;
        if (!linkKeys.has(key2)) {
          linkKeys.add(key2);
          linkList.push({
            source: entId,
            target: rel.target_account,
            type: rel.evidence_type.toLowerCase(),
            strength: rel.evidence_strength,
          });
        }
      } else {
        // Direct Account-to-Account coordination edge (e.g. Timing Synchrony)
        const key = `${rel.source_account}->${rel.target_account}`;
        if (!linkKeys.has(key)) {
          linkKeys.add(key);
          linkList.push({
            source: rel.source_account,
            target: rel.target_account,
            type: (rel.evidence_type || 'timing_synchrony').toLowerCase(),
            strength: rel.evidence_strength,
          });
        }
      }
    });

    return {
      nodes: Array.from(nodeMap.values()),
      links: linkList,
    };
  }, [accountData, queueItems]);

  const getRiskTierBadge = (tier, isHighRisk) => {
    const t = tier || 'LOW';
    if (t === 'CRITICAL') {
      return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-[#C64B43]/10 text-[#C64B43] border border-[#C64B43]/25">CRITICAL</span>;
    }
    if (t === 'HIGH' || isHighRisk) {
      return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-[#D58A27]/10 text-[#D58A27] border border-[#D58A27]/25">HIGH</span>;
    }
    if (t === 'MEDIUM') {
      return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-[#B99A45]/10 text-[#B99A45] border border-[#B99A45]/25">MEDIUM</span>;
    }
    if (t === 'UNRATED') {
      return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-[#F7F6F2] text-[#737A76] border border-[#E2E0D8]">UNRATED</span>;
    }
    return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/25">LOW</span>;
  };

  return (
    <div className="space-y-4 pb-12">
      {/* 1. Header Banner & View Mode Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E0D8] pb-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-extrabold text-[#252B29] tracking-tight flex items-center gap-2">
              <Search className="w-5 h-5 text-[#147D69]" />
              Investigation Workspace
            </h1>
            <span className="px-2 py-0.5 rounded-full bg-[#147D69]/10 border border-[#147D69]/25 text-[#147D69] text-[10px] font-mono font-semibold">
              Prioritized Queue
            </span>
          </div>
          <p className="text-xs text-[#737A76] mt-0.5">
            Triage accounts by calibrated CatBoost probability with decoupled relationship context
          </p>
        </div>

        {/* View Mode Pill Switcher */}
        <div className="flex items-center gap-1.5 bg-[#F7F6F2] border border-[#E2E0D8] p-1 rounded-lg self-start sm:self-auto text-xs">
          <button
            onClick={() => setViewMode('table')}
            className={`px-3 py-1 rounded-md transition-all font-semibold ${
              viewMode === 'table'
                ? 'bg-[#147D69] text-white font-bold shadow-sm'
                : 'text-[#737A76] hover:text-[#252B29]'
            }`}
          >
            Queue ({totalCount?.toLocaleString()})
          </button>
          <button
            onClick={() => setViewMode('detail')}
            className={`px-3 py-1 rounded-md transition-all font-semibold flex items-center gap-1.5 ${
              viewMode === 'detail'
                ? 'bg-[#147D69] text-white font-bold shadow-sm'
                : 'text-[#737A76] hover:text-[#252B29]'
            }`}
          >
            <span>Account Deep-Dive</span>
            {activeAccountId && (
              <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${viewMode === 'detail' ? 'bg-white/20 text-white' : 'bg-white text-[#147D69]'}`}>
                {activeAccountId}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* =================================================================== */}
      {/* VIEW MODE 1: TRIAGE QUEUE                                           */}
      {/* =================================================================== */}
      {viewMode === 'table' && (
        <div className="space-y-3">
          {/* Filter Bar */}
          <div className="bg-white border border-[#E2E0D8] rounded-xl p-3 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-sm">
            {/* Search Input */}
            <div className="relative flex-1 max-w-sm">
              <Search className="w-3.5 h-3.5 text-[#737A76] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search Account ID (e.g. ACC_009754)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg pl-8 pr-3 py-1.5 text-xs text-[#252B29] placeholder-[#9BA09D] font-mono focus:outline-none focus:border-[#147D69]"
              />
            </div>

            {/* Quick Filter Pills */}
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="text-[11px] text-[#737A76] mr-1">Tier:</span>
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((tier) => (
                <button
                  key={tier}
                  onClick={() => {
                    setRiskTierFilter(tier);
                    setPage(1);
                  }}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                    riskTierFilter === tier
                      ? 'bg-[#147D69] text-white font-bold'
                      : 'bg-[#F7F6F2] text-[#737A76] hover:text-[#252B29] border border-[#E2E0D8]'
                  }`}
                >
                  {tier}
                </button>
              ))}

              <button
                onClick={() => {
                  setHasSharedDevice(hasSharedDevice === 'true' ? 'ALL' : 'true');
                  setPage(1);
                }}
                className={`ml-2 px-2.5 py-1 rounded text-[11px] font-semibold transition-all flex items-center gap-1 ${
                  hasSharedDevice === 'true'
                    ? 'bg-[#7C6EAF] text-white font-bold'
                    : 'bg-[#F7F6F2] text-[#737A76] hover:text-[#252B29] border border-[#E2E0D8]'
                }`}
              >
                <Smartphone className="w-3 h-3" />
                <span>Shared Device</span>
              </button>
            </div>
          </div>

          {/* Queue Table */}
          <div className="bg-white border border-[#E2E0D8] rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F7F6F2] border-b border-[#E2E0D8] text-[#737A76] text-[10px] uppercase tracking-wider">
                  <tr>
                    <th className="py-2.5 px-4 font-semibold">Account ID</th>
                    <th className="py-2.5 px-4 font-semibold">Calibrated P(Abuse)</th>
                    <th className="py-2.5 px-4 font-semibold">Risk Tier</th>
                    <th className="py-2.5 px-4 font-semibold">Decision Rule</th>
                    <th className="py-2.5 px-4 font-semibold">Evidence Badges</th>
                    <th className="py-2.5 px-4 font-semibold">Window Status</th>
                    <th className="py-2.5 px-4 font-semibold text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E0D8]/60">
                  {loadingQueue ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-[#737A76] text-xs">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-4 h-4 border-2 border-[#147D69] border-t-transparent rounded-full animate-spin" />
                          <span>Loading investigation queue...</span>
                        </div>
                      </td>
                    </tr>
                  ) : filteredQueueItems.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-[#9BA09D] text-xs">
                        No accounts match the specified criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredQueueItems.map((item) => (
                      <tr
                        key={item.account_id}
                        onClick={() => {
                          setActiveAccountId(item.account_id);
                          if (onSelectAccount) onSelectAccount(item.account_id);
                          setViewMode('detail');
                        }}
                        className="hover:bg-[#F7F6F2] cursor-pointer transition-colors group"
                      >
                        <td className="py-2.5 px-4 font-bold font-mono text-[#147D69] group-hover:text-[#0F5F50]">
                          {item.account_id}
                        </td>
                        <td className="py-2.5 px-4 font-black font-mono text-[#C64B43]">
                          {item.calibrated_probability != null ? item.calibrated_probability.toFixed(4) : '-'}
                        </td>
                        <td className="py-2.5 px-4">
                          {getRiskTierBadge(item.risk_tier, item.is_high_risk)}
                        </td>
                        <td className="py-2.5 px-4">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                            item.is_high_risk
                              ? 'bg-[#C64B43]/10 text-[#C64B43] border border-[#C64B43]/25'
                              : 'bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/25'
                          }`}>
                            {item.is_high_risk ? 'ESCALATE (≥0.35)' : 'MONITOR'}
                          </span>
                        </td>
                        <td className="py-2.5 px-4">
                          {item.evidence_badges && item.evidence_badges.length > 0 ? (
                            <div className="flex gap-1 flex-wrap">
                              {item.evidence_badges.map((b) => (
                                <span key={b} className="text-[9px] px-1.5 py-0.5 rounded bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/20">
                                  {b}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-[10px] text-[#9BA09D] font-mono">BEHAVIORAL_ANOMALY</span>
                          )}
                        </td>
                        <td className="py-2.5 px-4 text-[10px] text-[#737A76] font-mono">
                          {item.outcome_window_status || 'COMPLETE'}
                        </td>
                        <td className="py-2.5 px-4 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveAccountId(item.account_id);
                              if (onSelectAccount) onSelectAccount(item.account_id);
                              setViewMode('detail');
                            }}
                            className="px-2.5 py-1 rounded bg-[#F7F6F2] hover:bg-[#147D69] hover:text-white text-[#147D69] border border-[#E2E0D8] text-[10px] font-bold transition-all inline-flex items-center gap-1"
                          >
                            Inspect <ChevronRight className="w-3 h-3" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="p-3 bg-[#F7F6F2] border-t border-[#E2E0D8] flex items-center justify-between text-xs text-[#737A76]">
              <span>Showing {filteredQueueItems.length} of {totalCount?.toLocaleString()} accounts</span>
              <div className="flex items-center gap-2">
                <button
                  disabled={page === 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-2.5 py-1 rounded bg-white border border-[#E2E0D8] hover:text-[#252B29] disabled:opacity-40"
                >
                  Prev
                </button>
                <span>Page {page}</span>
                <button
                  disabled={page * pageSize >= totalCount}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-2.5 py-1 rounded bg-white border border-[#E2E0D8] hover:text-[#252B29] disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* VIEW MODE 2: ACCOUNT DEEP-DIVE (PROGRESSIVE DISCLOSURE TABS)        */}
      {/* =================================================================== */}
      {viewMode === 'detail' && (
        <div className="space-y-4">
          {/* Account Sub-Header Bar */}
          <div className="bg-white border border-[#E2E0D8] rounded-xl p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-sm">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setViewMode('table')}
                className="p-1.5 rounded-lg bg-[#F7F6F2] hover:bg-[#E2E0D8] text-[#737A76] hover:text-[#252B29] border border-[#E2E0D8] transition-colors"
                title="Back to Queue"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-base font-black text-[#252B29]">{activeAccountId}</span>
                  {accountData && getRiskTierBadge(accountData.ml_prediction?.risk_tier, accountData.ml_prediction?.is_high_risk)}
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/20">
                    Threshold: {decisionThreshold}
                  </span>
                </div>
                <div className="text-[10px] font-mono text-[#737A76] mt-0.5">
                  Cutoff: {accountData?.observation_cutoff || 'T_obs'} • Community: {accountData?.cluster_id || 'CLUSTER_056'}
                </div>
              </div>
            </div>

            {/* Mode Switcher + Deep-Dive Tabs */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Investigation Mode Toggle (Predictive vs Retrospective) */}
              <div className="flex items-center bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg p-0.5 text-xs">
                <button
                  onClick={() => setInvestigationMode('predictive')}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                    investigationMode === 'predictive'
                      ? 'bg-[#147D69] text-white font-bold'
                      : 'text-[#737A76] hover:text-[#252B29]'
                  }`}
                >
                  Predictive (t &le; T_obs)
                </button>
                <button
                  onClick={() => setInvestigationMode('retrospective')}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                    investigationMode === 'retrospective'
                      ? 'bg-[#B99A45] text-white font-bold'
                      : 'text-[#737A76] hover:text-[#252B29]'
                  }`}
                >
                  Retrospective (30D)
                </button>
              </div>

              {/* Detail Tabs */}
              <div className="flex items-center bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg p-0.5 text-xs">
                <button
                  onClick={() => setDetailTab('evidence')}
                  className={`px-3 py-1 rounded text-[11px] font-semibold transition-all ${
                    detailTab === 'evidence'
                      ? 'bg-white text-[#252B29] font-bold shadow-sm'
                      : 'text-[#737A76] hover:text-[#252B29]'
                  }`}
                >
                  Evidence &amp; Topology
                </button>
                <button
                  onClick={() => setDetailTab('timeline')}
                  className={`px-3 py-1 rounded text-[11px] font-semibold transition-all ${
                    detailTab === 'timeline'
                      ? 'bg-white text-[#252B29] font-bold shadow-sm'
                      : 'text-[#737A76] hover:text-[#252B29]'
                  }`}
                >
                  Timeline &amp; Events
                </button>
                <button
                  onClick={() => setDetailTab('triage')}
                  className={`px-3 py-1 rounded text-[11px] font-semibold transition-all ${
                    detailTab === 'triage'
                      ? 'bg-white text-[#252B29] font-bold shadow-sm'
                      : 'text-[#737A76] hover:text-[#252B29]'
                  }`}
                >
                  SOC Action
                </button>
              </div>

              {/* AI Investigation Copilot Trigger in Header */}
              <button
                onClick={() => setIsCopilotOpen(!isCopilotOpen)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all border shadow-sm cursor-pointer ${
                  isCopilotOpen
                    ? 'bg-[#147D69] text-white border-[#147D69]'
                    : 'bg-gradient-to-r from-[#147D69] to-[#0E5E4E] hover:from-[#0E5E4E] hover:to-[#147D69] text-white border-emerald-400/40 hover:shadow'
                }`}
                title="Toggle AI Investigation Copilot for this account"
              >
                <Sparkles className="w-3.5 h-3.5 text-emerald-200" />
                <span>Ask Copilot</span>
                <span className="text-[9px] bg-white/20 text-white px-1.5 py-0.2 rounded font-mono font-bold tracking-wider">
                  AI
                </span>
              </button>
            </div>
          </div>

          {/* Retrospective Notice Banner (When in Retrospective mode) */}
          {investigationMode === 'retrospective' && (
            <div className="p-3 bg-[#B99A45]/10 border border-[#B99A45]/30 rounded-lg text-xs text-[#8A7230] flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-[#B99A45]" />
              <span>
                <strong>Retrospective Audit Active:</strong> Full 30-day historical data visible. Events occurring after T_obs represent outcome activity and were not visible at prediction cutoff.
              </span>
            </div>
          )}

          {/* Loading Detail State */}
          {loadingDetail || !accountData ? (
            <div className="p-12 bg-white border border-[#E2E0D8] rounded-xl text-center text-[#737A76] text-xs shadow-sm">
              <div className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 border-2 border-[#147D69] border-t-transparent rounded-full animate-spin" />
                <span>Loading account telemetry and verified relationships...</span>
              </div>
            </div>
          ) : (
            <>
              {/* TAB 1: EVIDENCE & TOPOLOGY */}
              {detailTab === 'evidence' && (
                <div className="space-y-4">
                  {/* Top 3 Metric Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                    <div className="bg-white border border-[#E2E0D8] rounded-xl p-3.5 space-y-1.5 shadow-sm">
                      <div className="flex items-center justify-between text-[#737A76] text-[10px] uppercase font-semibold">
                        <span>CatBoost Risk Score</span>
                        <Bot className="w-3.5 h-3.5 text-[#147D69]" />
                      </div>
                      <div className="text-2xl font-black font-mono text-[#C64B43]">
                        {accountData.ml_prediction?.calibrated_probability?.toFixed(4) || '0.0000'}
                      </div>
                      <div className="text-[10px] text-[#737A76] truncate font-mono">
                        Decision Threshold: {accountData.ml_prediction?.threshold || 0.35} ({accountData.ml_prediction?.is_high_risk ? 'ESCALATED' : 'PASS'})
                      </div>
                    </div>

                    <div className="bg-white border border-[#E2E0D8] rounded-xl p-3.5 space-y-1.5 shadow-sm">
                      <div className="flex items-center justify-between text-[#737A76] text-[10px] uppercase font-semibold">
                        <span>Corroborated Connections</span>
                        <Network className="w-3.5 h-3.5 text-[#7C6EAF]" />
                      </div>
                      <div className="text-2xl font-black text-[#7C6EAF]">
                        {accountData.relationships?.length || 0} Entities
                      </div>
                      <div className="text-[10px] text-[#737A76] truncate font-mono">
                        Cluster: {accountData.cluster_id || 'None'} • Density: {accountData.graph_density?.toFixed(3) || '0.073'}
                      </div>
                    </div>

                    <div className="bg-white border border-[#E2E0D8] rounded-xl p-3.5 space-y-1.5 shadow-sm">
                      <div className="flex items-center justify-between text-[#737A76] text-[10px] uppercase font-semibold">
                        <span>Observed Activity</span>
                        <Zap className="w-3.5 h-3.5 text-[#147D69]" />
                      </div>
                      <div className="text-2xl font-black text-[#252B29]">
                        {formatINR(timelineData?.summary_statistics?.total_volume || 0)}
                      </div>
                      <div className="text-[10px] text-[#737A76] truncate font-mono">
                        {timelineData?.summary_statistics?.total_transactions || 0} Transactions • Failure Rate: {((timelineData?.summary_statistics?.failed_rate || 0) * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>

                  {/* Main Grid: Relationship Cards (Left) & Network Graph (Right) */}
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                    {/* Relationship Evidence Cards */}
                    <div className="lg:col-span-5 bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-3 shadow-sm">
                      <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
                        <h3 className="text-xs font-bold text-[#252B29] uppercase flex items-center gap-1.5">
                          <Network className="w-3.5 h-3.5 text-[#147D69]" />
                          Corroborated Evidence ({accountData.relationships?.length || 0})
                        </h3>
                        <span className="text-[10px] text-[#737A76] font-mono">Decoupled Context</span>
                      </div>

                      {(!accountData.relationships || accountData.relationships.length === 0) ? (
                        <div className="py-8 text-center text-[#9BA09D] text-xs">
                          No corroborated multi-account infrastructure detected.
                        </div>
                      ) : (
                        <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
                          {accountData.relationships.map((rel, rIdx) => (
                            <div key={rIdx} className="p-2.5 rounded-lg bg-[#F7F6F2] border border-[#E2E0D8] text-xs space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-bold font-mono text-[#147D69]">
                                  {rel.target_account === activeAccountId ? rel.source_account : rel.target_account}
                                </span>
                                <span className="text-[9px] px-1.5 py-0.5 rounded font-bold bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/20">
                                  {rel.evidence_type}
                                </span>
                              </div>
                              <p className="text-[11px] text-[#3D4543]">{rel.explanation}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Network Graph */}
                    <div className="lg:col-span-7 bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-3 shadow-sm">
                      <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
                        <h3 className="text-xs font-bold text-[#252B29] uppercase flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-[#147D69]" />
                          Neighborhood Topology Subgraph
                        </h3>
                        <span className="text-[10px] text-[#737A76] font-mono">Click node to inspect</span>
                      </div>

                      <div className="rounded-lg overflow-hidden border border-[#E2E0D8] bg-[#F7F6F2]">
                        <NetworkGraph
                          nodes={graphNodesAndLinks.nodes}
                          links={graphNodesAndLinks.links}
                          focalNodeId={activeAccountId}
                          onInspectAccount={(targetAccId) => {
                            setActiveAccountId(targetAccId);
                            if (onSelectAccount) onSelectAccount(targetAccId);
                          }}
                          height={400}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: TIMELINE & ANOMALY EVENTS */}
              {detailTab === 'timeline' && (
                <div className="space-y-4">
                  {/* Anomaly Timeline */}
                  <div className="bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-3 shadow-sm">
                    <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
                      <h3 className="text-xs font-bold text-[#252B29] uppercase flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-[#147D69]" />
                        Point-in-Time Anomaly Timeline ({timelineData?.anomaly_events?.length || 0} Events)
                      </h3>
                      <span className="text-[10px] text-[#737A76] font-mono">Observation window chronology</span>
                    </div>

                    {(!timelineData?.anomaly_events || timelineData.anomaly_events.length === 0) ? (
                      <div className="py-6 text-center text-[#9BA09D] text-xs">
                        No elevated anomaly burst events detected in this window.
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                        {timelineData.anomaly_events.map((ev, eIdx) => (
                          <div key={eIdx} className="p-2.5 rounded-lg bg-[#F7F6F2] border border-[#E2E0D8] text-xs space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="text-[#737A76] text-[10px] font-mono">{ev.timestamp}</span>
                              <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                                ev.severity === 'HIGH' ? 'bg-[#C64B43]/10 text-[#C64B43]' : 'bg-[#B99A45]/10 text-[#B99A45]'
                              }`}>
                                {ev.event_type}
                              </span>
                            </div>
                            <p className="text-[11px] text-[#3D4543]">{ev.description}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Transactions Stream */}
                  <div className="bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-3 shadow-sm">
                    <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
                      <h3 className="text-xs font-bold text-[#252B29] uppercase flex items-center gap-1.5">
                        <CreditCard className="w-3.5 h-3.5 text-[#7C6EAF]" />
                        Observed Transaction History ({timelineData?.transactions?.length || 0})
                      </h3>
                    </div>

                    <div className="max-h-60 overflow-y-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-[#E2E0D8] text-[#737A76] text-[10px] uppercase">
                            <th className="pb-2 font-semibold">Timestamp</th>
                            <th className="pb-2 font-semibold">Amount</th>
                            <th className="pb-2 font-semibold">Type</th>
                            <th className="pb-2 font-semibold">Counterparty</th>
                            <th className="pb-2 font-semibold text-right">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#E2E0D8]/60">
                          {(!timelineData?.transactions || timelineData.transactions.length === 0) ? (
                            <tr>
                              <td colSpan={5} className="py-6 text-center text-[#9BA09D] text-xs">
                                No transactions recorded.
                              </td>
                            </tr>
                          ) : (
                            timelineData.transactions.slice(0, 15).map((tx) => (
                              <tr key={tx.transaction_id} className="hover:bg-[#F7F6F2]">
                                <td className="py-2 text-[#737A76] font-mono">{tx.timestamp}</td>
                                <td className="py-2 font-bold text-[#252B29] font-mono">{formatINR(tx.amount)}</td>
                                <td className="py-2 capitalize text-[#3D4543]">{tx.transaction_type}</td>
                                <td className="py-2 text-[#737A76] font-mono">{tx.destination_id || '-'}</td>
                                <td className="py-2 text-right">
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold font-mono ${
                                    tx.status === 'SUCCESS' ? 'text-[#147D69]' : 'text-[#C64B43]'
                                  }`}>
                                    {tx.status}
                                  </span>
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 3: SOC TRIAGE ACTION */}
              {detailTab === 'triage' && (
                <div className="bg-white border border-[#E2E0D8] rounded-xl p-5 space-y-4 shadow-sm">
                  <div className="border-b border-[#E2E0D8] pb-3">
                    <h3 className="text-xs font-bold text-[#252B29] uppercase flex items-center gap-1.5">
                      <UserCheck className="w-4 h-4 text-[#147D69]" />
                      Analyst Triage Decision
                    </h3>
                    <p className="text-[11px] text-[#737A76] mt-0.5">
                      Submit human-in-the-loop disposition to the immutable security audit log
                    </p>
                  </div>

                  <div className="space-y-3">
                    <textarea
                      placeholder="Add analyst investigation notes, rationale, or external corroboration..."
                      value={analystNotes}
                      onChange={(e) => setAnalystNotes(e.target.value)}
                      rows={3}
                      className="w-full bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg p-3 text-xs text-[#252B29] placeholder-[#9BA09D] font-mono focus:outline-none focus:border-[#147D69]"
                    />

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => handleTriageAction('CONFIRM_ABUSE_ESCALATION')}
                        disabled={isSubmittingReview}
                        className="px-3.5 py-2 bg-[#C64B43] hover:bg-[#B3413A] text-white text-xs font-bold rounded-lg transition-all"
                      >
                        Escalate to SOC
                      </button>
                      <button
                        onClick={() => handleTriageAction('RESTRICT_TRANSACTIONS')}
                        disabled={isSubmittingReview}
                        className="px-3.5 py-2 bg-[#D58A27] hover:bg-[#C07B20] text-white text-xs font-bold rounded-lg transition-all"
                      >
                        Restrict Account
                      </button>
                      <button
                        onClick={() => handleTriageAction('REQUEST_KYC_VERIFICATION')}
                        disabled={isSubmittingReview}
                        className="px-3.5 py-2 bg-[#B99A45] hover:bg-[#A88B3D] text-white text-xs font-bold rounded-lg transition-all"
                      >
                        Request KYC
                      </button>
                      <button
                        onClick={() => handleTriageAction('CLEAR_BENIGN')}
                        disabled={isSubmittingReview}
                        className="px-3.5 py-2 bg-[#147D69] hover:bg-[#0F5F50] text-white text-xs font-bold rounded-lg transition-all"
                      >
                        Clear Benign
                      </button>
                    </div>

                    {reviewStatus && (
                      <div className="p-2.5 rounded bg-[#147D69]/10 border border-[#147D69]/25 text-xs text-[#147D69] flex items-center gap-2">
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span>Action registered: {reviewStatus}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Floating AI Investigation Copilot Trigger */}
      {!isCopilotOpen && (
        <button
          onClick={() => setIsCopilotOpen(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 px-4 py-2.5 bg-gradient-to-r from-[#0E5E4E] via-[#147D69] to-[#0A483C] hover:from-[#147D69] hover:to-[#0F5F50] text-white font-semibold text-xs tracking-wide rounded-full shadow-xl hover:shadow-2xl transition-all duration-200 border border-emerald-300/40 hover:scale-105 active:scale-95 group cursor-pointer"
          title="Open AI Investigation Copilot"
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-300 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-200"></span>
          </span>
          <Sparkles className="w-4 h-4 text-emerald-200 group-hover:rotate-12 transition-transform duration-200" />
          <span className="font-sans font-bold">Ask Copilot</span>
          <span className="text-[9px] bg-white/20 text-white px-1.5 py-0.5 rounded-full font-mono font-bold tracking-wider uppercase border border-white/20">
            AI
          </span>
        </button>
      )}

      {/* AI Investigation Copilot Drawer */}
      <InvestigationCopilot
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
        accountId={activeAccountId}
        investigationMode={investigationMode}
        accountData={accountData}
        timelineData={timelineData}
        onNavigateTab={(tab) => setDetailTab(tab)}
      />
    </div>
  );
}
