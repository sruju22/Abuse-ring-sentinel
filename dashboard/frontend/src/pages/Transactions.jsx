import React, { useState, useEffect } from 'react';
import {
  CreditCard,
  Search,
  Filter,
  ArrowUpDown,
  Clock,
  CheckCircle,
  XCircle,
  ExternalLink,
  ShieldAlert,
  Calendar,
  IndianRupee,
} from 'lucide-react';
import { api } from '../services/api';
import { formatINR, USD_TO_INR } from '../utils/currency';

export default function Transactions({ onSelectAccount, onNavigate }) {
  const [transactions, setTransactions] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const [accountId, setAccountId] = useState('');
  const [clusterId, setClusterId] = useState('ALL');
  const [txType, setTxType] = useState('ALL');
  const [status, setStatus] = useState('ALL');
  const [minAmount, setMinAmount] = useState('');
  const [maxAmount, setMaxAmount] = useState('');

  const [selectedTx, setSelectedTx] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api
      .getTransactions({
        page,
        pageSize,
        accountId,
        clusterId,
        transactionType: txType,
        status,
        minAmount: minAmount ? parseFloat(minAmount) / USD_TO_INR : undefined,
        maxAmount: maxAmount ? parseFloat(maxAmount) / USD_TO_INR : undefined,
        sortBy: 'timestamp',
        sortOrder: 'desc',
      })
      .then((res) => {
        if (mounted) {
          setTransactions(res.items || []);
          setTotal(res.total || 0);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [page, pageSize, accountId, clusterId, txType, status, minAmount, maxAmount]);

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1E293B]/70 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <CreditCard className="w-5 h-5 text-indigo-400" />
              Transaction Stream Explorer
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-[10px] font-mono font-semibold uppercase">
              159,569 Records
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Search, filter and inspect raw transaction streams with correlated account risk telemetry
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-4 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 text-xs font-mono">
          {/* Account Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter Account ID..."
              value={accountId}
              onChange={(e) => {
                setAccountId(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#090D16] border border-[#1E293B] rounded-lg pl-8 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Cluster Filter */}
          <select
            value={clusterId}
            onChange={(e) => {
              setClusterId(e.target.value);
              setPage(1);
            }}
            className="bg-[#090D16] border border-[#1E293B] rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Clusters</option>
            <option value="CLUSTER_001">CLUSTER_001</option>
            <option value="CLUSTER_002">CLUSTER_002</option>
            <option value="CLUSTER_003">CLUSTER_003</option>
            <option value="CLUSTER_004">CLUSTER_004</option>
            <option value="CLUSTER_005">CLUSTER_005</option>
          </select>

          {/* Type Filter */}
          <select
            value={txType}
            onChange={(e) => {
              setTxType(e.target.value);
              setPage(1);
            }}
            className="bg-[#090D16] border border-[#1E293B] rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Types</option>
            <option value="p2p">P2P Transfer</option>
            <option value="transfer">Bank Transfer</option>
            <option value="payment">Merchant Payment</option>
            <option value="cashout">ATM / Cashout</option>
          </select>

          {/* Status Filter */}
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="bg-[#090D16] border border-[#1E293B] rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="FAILED">FAILED</option>
          </select>

          {/* Min Amount */}
          <input
            type="number"
            placeholder="Min Amount (₹)..."
            value={minAmount}
            onChange={(e) => {
              setMinAmount(e.target.value);
              setPage(1);
            }}
            className="bg-[#090D16] border border-[#1E293B] rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />

          {/* Max Amount */}
          <input
            type="number"
            placeholder="Max Amount (₹)..."
            value={maxAmount}
            onChange={(e) => {
              setMaxAmount(e.target.value);
              setPage(1);
            }}
            className="bg-[#090D16] border border-[#1E293B] rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 border-t border-[#1E293B] pt-2">
          <span>{total?.toLocaleString()} Transactions Matching Query</span>
          <span>Page {page}</span>
        </div>
      </div>

      {/* Main Transactions Table */}
      <div className="bg-[#111726] border border-[#1E293B] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[#090D16] border-b border-[#1E293B] text-slate-400 text-[10px] uppercase tracking-wider">
              <tr>
                <th className="py-3 px-4">Tx ID</th>
                <th className="py-3 px-4">Account ID</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Counterparty / Target</th>
                <th className="py-3 px-4">Account Risk</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E293B]/60">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    Loading transactions...
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    No transactions found for filter criteria.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr
                    key={tx.transaction_id}
                    onClick={() => setSelectedTx(tx)}
                    className="hover:bg-[#151C2C] cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 px-4 font-bold text-slate-300">{tx.transaction_id}</td>
                    <td
                      className="py-2.5 px-4 font-bold text-cyan-400 hover:text-cyan-300"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectAccount(tx.account_id);
                        onNavigate('investigations');
                      }}
                    >
                      {tx.account_id}
                    </td>
                    <td className="py-2.5 px-4 text-slate-400 text-[11px]">{tx.timestamp}</td>
                    <td className="py-2.5 px-4 font-bold text-white">{formatINR(tx.amount)}</td>
                    <td className="py-2.5 px-4 capitalize text-slate-300">{tx.transaction_type}</td>
                    <td className="py-2.5 px-4 text-slate-400">
                      {tx.destination_id || tx.merchant_id || '-'}
                    </td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          tx.account_risk_score >= 80
                            ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                            : tx.account_risk_score >= 60
                            ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                            : tx.account_risk_score >= 30
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        }`}
                      >
                        {tx.account_risk_score?.toFixed(1)} ({tx.account_risk_level})
                      </span>
                    </td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded font-semibold ${
                          tx.status === 'SUCCESS'
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : 'bg-red-500/10 text-red-400'
                        }`}
                      >
                        {tx.status === 'SUCCESS' ? (
                          <CheckCircle className="w-3 h-3" />
                        ) : (
                          <XCircle className="w-3 h-3" />
                        )}
                        <span>{tx.status}</span>
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="p-3 bg-[#090D16] border-t border-[#1E293B] flex items-center justify-between text-xs font-mono">
          <div className="text-slate-400 text-[11px]">
            Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, total)} of {total?.toLocaleString()}
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-3 py-1 bg-[#111726] border border-[#1E293B] disabled:opacity-40 rounded hover:bg-[#1E293B] text-slate-200"
            >
              Previous
            </button>
            <span className="text-slate-400 text-[11px]">Page {page}</span>
            <button
              disabled={page * pageSize >= total}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 bg-[#111726] border border-[#1E293B] disabled:opacity-40 rounded hover:bg-[#1E293B] text-slate-200"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Transaction Detail Modal */}
      {selectedTx && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-100">
          <div className="bg-[#111726] border border-[#1E293B] rounded-xl max-w-md w-full p-5 space-y-4 font-mono shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#1E293B] pb-3">
              <span className="text-sm font-bold text-white">Transaction Telemetry</span>
              <button
                onClick={() => setSelectedTx(null)}
                className="text-slate-400 hover:text-white text-xs px-2 py-1 bg-[#1E293B] rounded"
              >
                Close
              </button>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Tx ID:</span>
                <span className="text-white font-bold">{selectedTx.transaction_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Account ID:</span>
                <span className="text-cyan-400 font-bold">{selectedTx.account_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Amount:</span>
                <span className="text-white font-bold">{formatINR(selectedTx.amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Type:</span>
                <span className="text-slate-200 capitalize">{selectedTx.transaction_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Timestamp:</span>
                <span className="text-slate-300">{selectedTx.timestamp}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Counterparty / Target:</span>
                <span className="text-amber-400 font-bold">{selectedTx.destination_id || selectedTx.merchant_id || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Cluster Membership:</span>
                <span className="text-cyan-300 font-bold">{selectedTx.cluster_id || 'Unassigned'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Account Risk Level:</span>
                <span className="text-orange-400 font-bold">{selectedTx.account_risk_level} ({selectedTx.account_risk_score?.toFixed(1)})</span>
              </div>
            </div>

            {/* Raw Transaction JSON Inspector (Section 8) */}
            <div className="space-y-1 pt-2 border-t border-[#1E293B]">
              <span className="text-[10px] uppercase text-slate-400 font-bold block">Raw Telemetry Payload</span>
              <pre className="p-2.5 bg-[#090D16] border border-[#1E293B] rounded-lg text-[10px] text-slate-300 font-mono overflow-x-auto max-h-32">
                {JSON.stringify(selectedTx, null, 2)}
              </pre>
            </div>

            <div className="pt-2 border-t border-[#1E293B]">
              <button
                onClick={() => {
                  onSelectAccount(selectedTx.account_id);
                  onNavigate('investigations');
                }}
                className="w-full py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                <span>Investigate Account {selectedTx.account_id}</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
