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
};
