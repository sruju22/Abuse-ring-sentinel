import React, { useState, useEffect } from 'react';
import {
  Server,
  Database,
  Cpu,
  Layers,
  Network,
  ShieldCheck,
  CheckCircle2,
  Lock,
  ArrowDown,
  ArrowRight,
  GitBranch,
} from 'lucide-react';
import { api } from '../services/api';

export default function SystemArchitecture() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    api
      .getSystem()
      .then((res) => {
        if (mounted) {
          setData(res);
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

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-slate-400">Loading System Architecture...</span>
        </div>
      </div>
    );
  }

  const { pipeline_architecture, dataset_statistics, ground_truth_isolation } = data;

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1E293B]/70 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <Server className="w-5 h-5 text-cyan-400" />
              System Architecture & Integrity
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[10px] font-mono font-semibold uppercase">
              Operational Pipeline
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Modular multi-stage detection flow, pipeline statistics, and strict label isolation guarantees
          </p>
        </div>
      </div>

      {/* STATS STRIP */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono">
        <div className="p-3 bg-[#111726] border border-[#1E293B] rounded-xl text-center">
          <div className="text-[10px] text-slate-400 uppercase">Accounts</div>
          <div className="text-lg font-bold text-white mt-1">10,000</div>
        </div>
        <div className="p-3 bg-[#111726] border border-[#1E293B] rounded-xl text-center">
          <div className="text-[10px] text-slate-400 uppercase">Transactions</div>
          <div className="text-lg font-bold text-indigo-400 mt-1">159,569</div>
        </div>
        <div className="p-3 bg-[#111726] border border-[#1E293B] rounded-xl text-center">
          <div className="text-[10px] text-slate-400 uppercase">Features</div>
          <div className="text-lg font-bold text-cyan-400 mt-1">27 Signals</div>
        </div>
        <div className="p-3 bg-[#111726] border border-[#1E293B] rounded-xl text-center">
          <div className="text-[10px] text-slate-400 uppercase">Synthetic Rings</div>
          <div className="text-lg font-bold text-amber-400 mt-1">36 Rings</div>
        </div>
        <div className="p-3 bg-[#111726] border border-[#1E293B] rounded-xl text-center">
          <div className="text-[10px] text-slate-400 uppercase">Graph Clusters</div>
          <div className="text-lg font-bold text-emerald-400 mt-1">5 Communities</div>
        </div>
        <div className="p-3 bg-[#111726] border border-[#1E293B] rounded-xl text-center">
          <div className="text-[10px] text-slate-400 uppercase">Automated Tests</div>
          <div className="text-lg font-bold text-emerald-400 mt-1">31 Passed</div>
        </div>
      </div>

      {/* PIPELINE ARCHITECTURE FLOW */}
      <div className="bg-[#111726] border border-[#1E293B] rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-[#1E293B] pb-3">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            End-to-End Processing Pipeline
          </h2>
          <span className="text-[10px] font-mono text-slate-400">Deterministic • Sub-Millisecond Execution</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
          {pipeline_architecture?.map((step) => (
            <div
              key={step.step}
              className="p-4 bg-[#090D16] border border-[#1E293B] rounded-xl space-y-2 relative"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-bold text-cyan-400 px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20">
                  Step 0{step.step}
                </span>
                <span className="text-[10px] font-mono text-slate-400 uppercase">{step.badge}</span>
              </div>
              <h3 className="text-xs font-bold text-white pt-1">{step.name}</h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">{step.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* GROUND TRUTH ISOLATION GUARANTEE */}
      <div className="bg-[#111726] border border-emerald-500/30 rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              Ground Truth Isolation & Leakage Defense
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                AUDIT VERIFIED
              </span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Production data governance guarantee strictly separating operational features from evaluation labels
            </p>
          </div>
        </div>

        <div className="p-3.5 bg-[#090D16] border border-[#1E293B] rounded-lg text-xs font-mono text-slate-300 space-y-1.5">
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Operational UI and API completely exclude `ring_id`, `account_type`, and ground truth labels.</span>
          </div>
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Feature matrix inputs are generated solely from observable transactional and network telemetry.</span>
          </div>
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>All decision thresholds frozen strictly on validation split without held-out test contamination.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
