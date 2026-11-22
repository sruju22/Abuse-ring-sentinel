/**
 * API Service Client for Abuse-Ring Sentinel Backend.
 */

const API_BASE = '/api';

async function fetchJson(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Request failed with status ${res.status}`);
    }
    return await res.json();
  } catch (error) {
    console.error(`API Error on ${url}:`, error);
    throw error;
  }
}

export const api = {
  // Overview
  getOverview: () => fetchJson('/overview'),

  // Accounts & Investigations
  getAccounts: ({
    page = 1,
    pageSize = 25,
    search = '',
    riskLevel = 'ALL',
    reason = 'ALL',
    action = 'ALL',
    clusterId = 'ALL',
    minScore,
    maxScore,
    evidenceType = 'ALL',
    sortBy = 'final_risk_score',
    sortOrder = 'desc',
  } = {}) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sort_by: sortBy,
      sort_order: sortOrder,
    });
    if (search) params.append('search', search);
    if (riskLevel && riskLevel !== 'ALL') params.append('risk_level', riskLevel);
    if (reason && reason !== 'ALL') params.append('reason', reason);
    if (action && action !== 'ALL') params.append('action', action);
    if (clusterId && clusterId !== 'ALL') params.append('cluster_id', clusterId);
    if (minScore != null) params.append('min_score', String(minScore));
    if (maxScore != null) params.append('max_score', String(maxScore));
    if (evidenceType && evidenceType !== 'ALL') params.append('evidence_type', evidenceType);
    return fetchJson(`/accounts?${params.toString()}`);
  },

  getAccountDetail: (accountId) => fetchJson(`/accounts/${accountId}`),

  // Clusters
  getClusters: () => fetchJson('/clusters'),
  getClusterDetail: (clusterId) => fetchJson(`/clusters/${clusterId}`),

  // Transactions
  getTransactions: ({
    page = 1,
    pageSize = 25,
    accountId = '',
    clusterId = 'ALL',
    transactionType = 'ALL',
    status = 'ALL',
    minAmount,
    maxAmount,
    sortBy = 'timestamp',
    sortOrder = 'desc',
  } = {}) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sort_by: sortBy,
      sort_order: sortOrder,
    });
    if (accountId) params.append('account_id', accountId);
    if (clusterId && clusterId !== 'ALL') params.append('cluster_id', clusterId);
    if (transactionType && transactionType !== 'ALL') params.append('transaction_type', transactionType);
    if (status && status !== 'ALL') params.append('status', status);
    if (minAmount != null) params.append('min_amount', String(minAmount));
    if (maxAmount != null) params.append('max_amount', String(maxAmount));
    return fetchJson(`/transactions?${params.toString()}`);
  },

  // Audit Activity Log
  getAuditLog: () => fetchJson('/audit-log'),
  addAuditEvent: (event) =>
    fetchJson('/audit-log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
    }),

  // Model Intelligence & Evaluation
  getModels: () => fetchJson('/models'),

  // System
  getSystem: () => fetchJson('/system'),

  // Phase 4 & 5 Investigation Engine APIs
  investigations: {
    getQueue: ({
      limit = 50,
      offset = 0,
      riskTier,
      minProbability,
      hasSharedDevice,
      sortBy = 'probability',
    } = {}) => {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
        sort_by: sortBy,
      });
      if (riskTier && riskTier !== 'ALL') params.append('risk_tier', riskTier);
      if (minProbability != null && minProbability !== '') params.append('min_probability', String(minProbability));
      if (hasSharedDevice != null && hasSharedDevice !== 'ALL') {
        params.append('has_shared_device', String(hasSharedDevice === 'true' || hasSharedDevice === true));
      }
      return fetchJson(`/investigations/queue?${params.toString()}`);
    },

    getAccount: (accountId, mode = 'predictive') => {
      const cleanId = encodeURIComponent(String(accountId).trim());
      const params = new URLSearchParams({ mode });
      return fetchJson(`/investigations/accounts/${cleanId}?${params.toString()}`);
    },

    getTimeline: (accountId, mode = 'predictive') => {
      const cleanId = encodeURIComponent(String(accountId).trim());
      const params = new URLSearchParams({ mode });
      return fetchJson(`/investigations/accounts/${cleanId}/timeline?${params.toString()}`);
    },
    getAccountTimeline: (accountId, mode = 'predictive') => {
      const cleanId = encodeURIComponent(String(accountId).trim());
      const params = new URLSearchParams({ mode });
      return fetchJson(`/investigations/accounts/${cleanId}/timeline?${params.toString()}`);
    },

    getClusters: ({ limit = 50, sortBy = 'high_risk_count' } = {}) => {
      const params = new URLSearchParams({
        limit: String(limit),
        sort_by: sortBy,
      });
      return fetchJson(`/investigations/clusters?${params.toString()}`);
    },

    getClusterDetail: (clusterId, options = {}) => {
      const cleanId = encodeURIComponent(String(clusterId).trim());
      const params = new URLSearchParams();
      if (typeof options === 'boolean') {
        params.set('include_evaluation_meta', String(options));
      } else {
        if (options.includeEvaluationMeta) params.set('include_evaluation_meta', 'true');
        if (options.relationshipLimit) params.set('relationship_limit', String(options.relationshipLimit));
        if (options.evidenceType) params.set('evidence_type', String(options.evidenceType));
      }
      const qs = params.toString();
      return fetchJson(`/investigations/clusters/${cleanId}${qs ? `?${qs}` : ''}`);
    },

    getPrioritizationBenchmarks: (split = 'validation') => {
      const params = new URLSearchParams({ split });
      return fetchJson(`/investigations/benchmarks/prioritization?${params.toString()}`);
    },
  },

  // AI Investigation Copilot
  copilot: {
    getStatus: () => fetchJson('/investigations/copilot/status'),
    getSuggestedQuestions: (accountId, mode = 'predictive') => {
      const cleanId = encodeURIComponent(String(accountId).trim());
      const params = new URLSearchParams({ account_id: cleanId, mode });
      return fetchJson(`/investigations/copilot/suggested-questions?${params.toString()}`);
    },
    getBrief: (accountId, mode = 'predictive') => {
      return fetchJson('/investigations/copilot/brief', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: String(accountId).trim(), mode }),
      });
    },
    chat: ({ accountId, mode = 'predictive', message, history = [] }) => {
      return fetchJson('/investigations/copilot/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: String(accountId).trim(),
          mode,
          message,
          history,
        }),
      });
    },
  },
};
