import React, { useState, useEffect } from 'react';
import {
  CreditCard,
  Search,
  Filter,
  CheckCircle,
  XCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
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
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

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
    <div className="space-y-4 pb-12">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E0D8] pb-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-extrabold text-[#252B29] tracking-tight flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-[#147D69]" />
              Transaction Stream Explorer
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-[#147D69]/10 border border-[#147D69]/25 text-[#147D69] text-[10px] font-mono font-semibold">
              {total?.toLocaleString()} Records
            </span>
          </div>
          <p className="text-xs text-[#737A76] mt-0.5">
            Real-time synthetic transaction ledger with linked account risk telemetry
          </p>
        </div>
      </div>

      {/* Unified Filter Bar (Progressive Disclosure) */}
      <div className="bg-white border border-[#E2E0D8] rounded-xl p-3 space-y-3 font-mono text-xs shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Account Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-3.5 h-3.5 text-[#737A76] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by Account ID (e.g. ACC_009754)..."
              value={accountId}
              onChange={(e) => {
                setAccountId(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg pl-8 pr-3 py-1.5 text-xs text-[#252B29] placeholder-[#9BA09D] focus:outline-none focus:border-[#147D69]"
            />
          </div>

          {/* Quick Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5">
            {/* Status Pills */}
            <span className="text-[10px] text-[#737A76] mr-1 uppercase">Status:</span>
            {['ALL', 'SUCCESS', 'FAILED'].map((st) => (
              <button
                key={st}
                onClick={() => {
                  setStatus(st);
                  setPage(1);
                }}
                className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all ${
                  status === st
                    ? 'bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30 font-bold'
                    : 'text-[#737A76] hover:text-[#252B29] hover:bg-[#F3F1EB] border border-[#E2E0D8]'
                }`}
              >
                {st}
              </button>
            ))}

            {/* Type Pills */}
            <span className="text-[10px] text-[#737A76] ml-2 mr-1 uppercase">Type:</span>
            {['ALL', 'p2p', 'cashout', 'transfer'].map((t) => (
              <button
                key={t}
                onClick={() => {
                  setTxType(t);
                  setPage(1);
                }}
                className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase transition-all ${
                  txType === t
                    ? 'bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30 font-bold'
                    : 'text-[#737A76] hover:text-[#252B29] hover:bg-[#F3F1EB] border border-[#E2E0D8]'
                }`}
              >
                {t}
              </button>
            ))}

            {/* Advanced Filters Toggle */}
            <button
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
              className="ml-2 px-2.5 py-1 rounded bg-[#F7F6F2] hover:bg-[#E2E0D8] text-[#3D4543] border border-[#E2E0D8] text-[11px] font-semibold flex items-center gap-1 transition-colors"
            >
              <Filter className="w-3 h-3" />
              <span>More</span>
              {showAdvancedFilters ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          </div>
        </div>

        {/* Expandable Advanced Filters Drawer */}
        {showAdvancedFilters && (
          <div className="pt-2.5 border-t border-[#E2E0D8] grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-[10px] text-[#737A76] uppercase block mb-1">Cluster Community</label>
              <select
                value={clusterId}
                onChange={(e) => {
                  setClusterId(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg px-2.5 py-1 text-xs text-[#252B29] focus:outline-none focus:border-[#147D69]"
              >
                <option value="ALL">All Clusters</option>
                <option value="CLUSTER_056">CLUSTER_056</option>
                <option value="CLUSTER_049">CLUSTER_049</option>
                <option value="CLUSTER_106">CLUSTER_106</option>
                <option value="CLUSTER_006">CLUSTER_006</option>
                <option value="CLUSTER_107">CLUSTER_107</option>
              </select>
            </div>

            <div>
              <label className="text-[10px] text-[#737A76] uppercase block mb-1">Min Amount (₹)</label>
              <input
                type="number"
                placeholder="0"
                value={minAmount}
                onChange={(e) => {
                  setMinAmount(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg px-2.5 py-1 text-xs text-[#252B29] focus:outline-none focus:border-[#147D69]"
              />
            </div>

            <div>
              <label className="text-[10px] text-[#737A76] uppercase block mb-1">Max Amount (₹)</label>
              <input
                type="number"
                placeholder="500,000"
                value={maxAmount}
                onChange={(e) => {
                  setMaxAmount(e.target.value);
                  setPage(1);
                }}
                className="w-full bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg px-2.5 py-1 text-xs text-[#252B29] focus:outline-none focus:border-[#147D69]"
              />
            </div>
          </div>
        )}
      </div>

      {/* Main Transactions Table */}
      <div className="bg-white border border-[#E2E0D8] rounded-xl overflow-hidden font-mono text-xs shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-[#F7F6F2] border-b border-[#E2E0D8] text-[#737A76] text-[10px] uppercase tracking-wider">
              <tr>
                <th className="py-2.5 px-4 font-semibold">Tx ID</th>
                <th className="py-2.5 px-4 font-semibold">Account ID</th>
                <th className="py-2.5 px-4 font-semibold">Timestamp</th>
                <th className="py-2.5 px-4 font-semibold">Amount</th>
                <th className="py-2.5 px-4 font-semibold">Type</th>
                <th className="py-2.5 px-4 font-semibold">Counterparty</th>
                <th className="py-2.5 px-4 font-semibold">Status</th>
                <th className="py-2.5 px-4 font-semibold text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E0D8]/60">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#737A76]">
                    Loading transactions...
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-[#9BA09D]">
                    No transactions match criteria.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr
                    key={tx.transaction_id}
                    onClick={() => setSelectedTx(tx)}
                    className="hover:bg-[#F7F6F2] cursor-pointer transition-colors"
                  >
                    <td className="py-2 px-4 text-[#737A76] text-[11px]">{tx.transaction_id}</td>
                    <td
                      className="py-2 px-4 font-bold text-[#147D69] hover:text-[#0F5F50]"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectAccount(tx.account_id);
                        onNavigate('investigations');
                      }}
                    >
                      {tx.account_id}
                    </td>
                    <td className="py-2 px-4 text-[#737A76] text-[11px]">{tx.timestamp}</td>
                    <td className="py-2 px-4 font-bold text-[#252B29]">{formatINR(tx.amount)}</td>
                    <td className="py-2 px-4 capitalize text-[#3D4543]">{tx.transaction_type}</td>
                    <td className="py-2 px-4 text-[#737A76] text-[11px]">
                      {tx.destination_id || tx.merchant_id || '-'}
                    </td>
                    <td className="py-2 px-4">
                      <span
                        className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.2 rounded font-bold ${
                          tx.status === 'SUCCESS'
                            ? 'bg-[#147D69]/10 text-[#147D69]'
                            : 'bg-[#C64B43]/10 text-[#C64B43]'
                        }`}
                      >
                        {tx.status === 'SUCCESS' ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        <span>{tx.status}</span>
                      </span>
                    </td>
                    <td className="py-2 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTx(tx);
                        }}
                        className="px-2 py-0.5 rounded bg-[#F7F6F2] hover:bg-[#E2E0D8] text-[#3D4543] border border-[#E2E0D8] text-[10px] transition-colors"
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="p-2.5 bg-[#F7F6F2] border-t border-[#E2E0D8] flex items-center justify-between text-xs text-[#737A76]">
          <span className="text-[11px]">
            Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, total)} of {total?.toLocaleString()}
          </span>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-2.5 py-1 bg-white border border-[#E2E0D8] disabled:opacity-40 rounded hover:bg-[#E2E0D8] text-[#252B29]"
            >
              Prev
            </button>
            <span className="text-[11px]">Page {page}</span>
            <button
              disabled={page * pageSize >= total}
              onClick={() => setPage((p) => p + 1)}
              className="px-2.5 py-1 bg-white border border-[#E2E0D8] disabled:opacity-40 rounded hover:bg-[#E2E0D8] text-[#252B29]"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Transaction Detail Modal */}
      {selectedTx && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white border border-[#E2E0D8] rounded-xl max-w-md w-full p-4 space-y-3 font-mono text-xs shadow-lg">
            <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
              <span className="text-xs font-bold text-[#252B29] uppercase tracking-wider">Transaction Telemetry</span>
              <button
                onClick={() => setSelectedTx(null)}
                className="text-[#737A76] hover:text-[#252B29] text-xs px-2 py-0.5 bg-[#F3F1EB] rounded"
              >
                Close
              </button>
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[#737A76]">Tx ID:</span>
                <span className="text-[#252B29] font-bold">{selectedTx.transaction_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#737A76]">Account ID:</span>
                <span className="text-[#147D69] font-bold">{selectedTx.account_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#737A76]">Amount:</span>
                <span className="text-[#252B29] font-bold">{formatINR(selectedTx.amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#737A76]">Type:</span>
                <span className="text-[#3D4543] capitalize">{selectedTx.transaction_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#737A76]">Timestamp:</span>
                <span className="text-[#3D4543]">{selectedTx.timestamp}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#737A76]">Counterparty:</span>
                <span className="text-[#147D69]">{selectedTx.destination_id || selectedTx.merchant_id || '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#737A76]">Status:</span>
                <span className={selectedTx.status === 'SUCCESS' ? 'text-[#147D69] font-bold' : 'text-[#C64B43] font-bold'}>
                  {selectedTx.status}
                </span>
              </div>
            </div>

            <div className="pt-2 border-t border-[#E2E0D8]">
              <button
                onClick={() => {
                  onSelectAccount(selectedTx.account_id);
                  onNavigate('investigations');
                }}
                className="w-full py-1.5 bg-[#147D69] hover:bg-[#0F5F50] text-white font-bold text-xs rounded-lg transition-colors flex items-center justify-center gap-1.5"
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
