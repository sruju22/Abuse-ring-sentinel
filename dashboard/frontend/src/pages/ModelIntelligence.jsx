import React, { useState, useEffect } from 'react';
import {
  BrainCircuit,
  Cpu,
  BarChart3,
  Layers,
  Scale,
  ShieldCheck,
  ShieldAlert,
  TrendingUp,
  Info,
  Target,
  Bot,
  CheckCircle2,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { api } from '../services/api';

export default function ModelIntelligence() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('primary'); // 'primary' | 'prioritization' | 'comparison' | 'features' | 'methodology'

  // Prioritization Benchmark state
  const [benchmarkSplit, setBenchmarkSplit] = useState('validation');
  const [benchmarkData, setBenchmarkData] = useState(null);
  const [loadingBenchmark, setLoadingBenchmark] = useState(false);

  useEffect(() => {
    let mounted = true;
    api
      .getModels()
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

  useEffect(() => {
    let mounted = true;
    setLoadingBenchmark(true);
    api.investigations
      .getPrioritizationBenchmarks(benchmarkSplit)
      .then((res) => {
        if (mounted) {
          setBenchmarkData(res);
          setLoadingBenchmark(false);
        }
      })
      .catch((err) => {
        console.error('Failed to load prioritization benchmark:', err);
        if (mounted) setLoadingBenchmark(false);
      });
    return () => {
      mounted = false;
    };
  }, [benchmarkSplit]);

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[#147D69] border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-[#737A76]">Loading Model Intelligence telemetry...</span>
        </div>
      </div>
    );
  }

  const {
    baseline_metrics,
    top_features,
  } = data;

  return (
    <div className="space-y-4 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E0D8] pb-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-extrabold text-[#252B29] tracking-tight flex items-center gap-2">
              <BrainCircuit className="w-5 h-5 text-[#147D69]" />
              Model Intelligence & Benchmarks
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-[#147D69]/10 border border-[#147D69]/25 text-[#147D69] text-[10px] font-mono font-semibold">
              Protocol B Unseen-Ring Evaluation
            </span>
          </div>
          <p className="text-xs text-[#737A76] mt-0.5">
            Empirical benchmark metrics, probability calibration, prioritization tests, and feature attribution
          </p>
        </div>
      </div>

      {/* Tab Switcher Pills */}
      <div className="flex flex-wrap items-center gap-1 bg-white border border-[#E2E0D8] p-1 rounded-xl font-sans text-xs shadow-sm">
        {[
          { id: 'primary', label: 'Primary Model' },
          { id: 'prioritization', label: 'Prioritization Benchmark' },
          { id: 'comparison', label: 'Model Comparisons' },
          { id: 'features', label: 'Feature Importance' },
          { id: 'methodology', label: 'Evaluation Methodology' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 rounded-lg transition-all font-semibold ${
              activeTab === tab.id
                ? 'bg-[#147D69] text-white font-bold shadow-sm'
                : 'text-[#737A76] hover:text-[#252B29] hover:bg-[#F7F6F2]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* =================================================================== */}
      {/* TAB 1: PRIMARY MODEL & CALIBRATION METRICS                          */}
      {/* =================================================================== */}
      {activeTab === 'primary' && (
        <div className="space-y-4">
          {/* Primary Model Card */}
          <div className="bg-white border border-[#147D69]/30 rounded-xl p-5 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E2E0D8] pb-3">
              <div className="flex items-center gap-2.5">
                <Bot className="w-5 h-5 text-[#147D69]" />
                <div>
                  <h3 className="text-sm font-bold text-[#252B29] flex items-center gap-2">
                    <span>Untuned CatBoost Baseline + Platt Scaling</span>
                    <span className="px-2 py-0.5 rounded bg-[#147D69]/10 text-[#147D69] text-[10px] font-mono font-bold">
                      PRODUCTION PRIMARY
                    </span>
                  </h3>
                  <p className="text-[10px] text-[#737A76] font-mono mt-0.5">
                    Evaluated on Protocol B inductive unseen-ring splits (1,678 untouched test accounts)
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono">
                <span className="text-[#737A76]">Frozen Threshold:</span>
                <span className="font-extrabold text-[#147D69] bg-[#147D69]/10 px-2 py-0.5 rounded border border-[#147D69]/30">
                  0.35
                </span>
              </div>
            </div>

            {/* Metric Strips */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-center font-mono">
              <div className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg">
                <div className="text-[10px] text-[#737A76] uppercase">PR-AUC</div>
                <div className="text-lg font-black text-[#147D69] mt-1">0.6242</div>
                <div className="text-[9px] text-[#147D69]">Top Benchmark</div>
              </div>
              <div className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg">
                <div className="text-[10px] text-[#737A76] uppercase">Recall (@0.35)</div>
                <div className="text-lg font-black text-[#147D69] mt-1">77.78%</div>
                <div className="text-[9px] text-[#737A76]">63 / 81 Positives</div>
              </div>
              <div className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg">
                <div className="text-[10px] text-[#737A76] uppercase">Precision</div>
                <div className="text-lg font-black text-[#3D4543] mt-1">52.07%</div>
                <div className="text-[9px] text-[#737A76]">At 0.35 Cutoff</div>
              </div>
              <div className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg">
                <div className="text-[10px] text-[#737A76] uppercase">F1 Score</div>
                <div className="text-lg font-black text-[#252B29] mt-1">0.6238</div>
                <div className="text-[9px] text-[#737A76]">Harmonic Mean</div>
              </div>
              <div className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg">
                <div className="text-[10px] text-[#737A76] uppercase">ROC-AUC</div>
                <div className="text-lg font-black text-[#7C6EAF] mt-1">0.9701</div>
                <div className="text-[9px] text-[#737A76]">Global Ranking</div>
              </div>
              <div className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg">
                <div className="text-[10px] text-[#737A76] uppercase">Brier Score</div>
                <div className="text-lg font-black text-[#147D69] mt-1">0.0211</div>
                <div className="text-[9px] text-[#737A76]">Platt Calibrated</div>
              </div>
            </div>

            {/* Model Card Details */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono pt-1">
              <div className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg space-y-1">
                <span className="text-[10px] text-[#737A76] uppercase font-bold block">Algorithm & Trees</span>
                <p className="text-[#3D4543]">CatBoostClassifier (baseline hyperparameters, default depth 6, 1,000 iterations).</p>
              </div>
              <div className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg space-y-1">
                <span className="text-[10px] text-[#737A76] uppercase font-bold block">Calibration Scheme</span>
                <p className="text-[#3D4543]">Platt scaling (logistic sigmoid fit on validation logits). Guarantees true probability output.</p>
              </div>
              <div className="p-3 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg space-y-1">
                <span className="text-[10px] text-[#737A76] uppercase font-bold block">Decision Threshold Policy</span>
                <p className="text-[#3D4543]">Frozen at 0.35 on validation split. Balances fraud capture against human investigation capacity.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* TAB 2: PRIORITIZATION BENCHMARK (PURE ML vs HEURISTIC FUSION)       */}
      {/* =================================================================== */}
      {activeTab === 'prioritization' && (
        <div className="bg-white border border-[#E2E0D8] rounded-xl p-5 space-y-4 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E0D8] pb-3">
            <div>
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-[#147D69]" />
                <h2 className="text-sm font-bold text-[#252B29] uppercase tracking-wider font-mono">
                  Investigative Prioritization Benchmark
                </h2>
                <span className="px-2 py-0.5 rounded bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30 text-[10px] font-mono font-bold uppercase">
                  Pure ML vs Heuristic IPWH
                </span>
              </div>
              <p className="text-[11px] text-[#737A76] font-mono mt-0.5">
                Empirical audit comparing Pure Calibrated CatBoost ML vs Heuristic Prioritization across Top-K investigator cutoffs
              </p>
            </div>

            {/* Split Switcher */}
            <div className="flex items-center gap-1 bg-[#F7F6F2] p-1 rounded-lg border border-[#E2E0D8] text-xs font-mono">
              <button
                onClick={() => setBenchmarkSplit('validation')}
                className={`px-3 py-1 rounded transition-all font-semibold ${
                  benchmarkSplit === 'validation'
                    ? 'bg-[#147D69] text-white font-bold'
                    : 'text-[#737A76] hover:text-[#3D4543]'
                }`}
              >
                Validation Split (1,676)
              </button>
              <button
                onClick={() => setBenchmarkSplit('test')}
                className={`px-3 py-1 rounded transition-all font-semibold ${
                  benchmarkSplit === 'test'
                    ? 'bg-[#147D69] text-white font-bold'
                    : 'text-[#737A76] hover:text-[#3D4543]'
                }`}
              >
                Test Split (1,678)
              </button>
            </div>
          </div>

          <div className="p-3 bg-[#147D69]/5 border border-[#147D69]/25 rounded-lg text-xs font-mono text-[#147D69]">
            <strong>Decision Policy:</strong> The triage queue preserves pure calibrated CatBoost probability as its primary sorting metric.
            Graph evidence provides contextual badges and explanations, but is strictly <strong>never blended</strong> into model probabilities because heuristic graph fusion reduces true fraud capture and elevates benign shared households.
          </div>

          {loadingBenchmark || !benchmarkData ? (
            <div className="py-8 text-center text-xs font-mono text-[#737A76]">
              Loading benchmark metrics...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-[#F7F6F2] border-b border-[#E2E0D8] text-[#737A76] text-[10px] uppercase">
                  <tr>
                    <th className="py-2.5 px-3">Top-K Cutoff</th>
                    <th className="py-2.5 px-3 text-[#147D69]">Pure CatBoost ML (TPs)</th>
                    <th className="py-2.5 px-3 text-[#147D69]">Pure ML Recall</th>
                    <th className="py-2.5 px-3 text-[#147D69]">Pure ML Precision</th>
                    <th className="py-2.5 px-3 text-[#B99A45]">Heuristic IPWH (TPs)</th>
                    <th className="py-2.5 px-3 text-[#B99A45]">IPWH Recall</th>
                    <th className="py-2.5 px-3 text-[#B99A45]">IPWH Precision</th>
                    <th className="py-2.5 px-3 text-right">Delta / Impact</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E0D8]">
                  {['top_25', 'top_50', 'top_100'].map((kKey) => {
                    const ml = benchmarkData.pure_ml_ranking?.[kKey] || {};
                    const ipwh = benchmarkData.heuristic_ipwh_ranking?.[kKey] || {};
                    const tpDiff = (ml.true_positives || 0) - (ipwh.true_positives || 0);

                    return (
                      <tr key={kKey} className="hover:bg-[#F7F6F2]">
                        <td className="py-3 px-3 font-bold text-[#252B29] uppercase">{kKey.replace('_', ' ')}</td>
                        <td className="py-3 px-3 font-extrabold text-[#147D69]">
                          {ml.true_positives} / {ml.k}
                        </td>
                        <td className="py-3 px-3 text-[#147D69] font-bold">
                          {((ml.recall || 0) * 100).toFixed(1)}%
                        </td>
                        <td className="py-3 px-3 text-[#3D4543]">
                          {((ml.precision || 0) * 100).toFixed(1)}%
                        </td>
                        <td className="py-3 px-3 font-extrabold text-[#B99A45]">
                          {ipwh.true_positives} / {ipwh.k}
                        </td>
                        <td className="py-3 px-3 text-[#3D4543]">
                          {((ipwh.recall || 0) * 100).toFixed(1)}%
                        </td>
                        <td className="py-3 px-3 text-[#3D4543]">
                          {((ipwh.precision || 0) * 100).toFixed(1)}%
                        </td>
                        <td className="py-3 px-3 text-right font-extrabold">
                          {tpDiff >= 0 ? (
                            <span className="text-[#147D69]">+{tpDiff} TPs (Pure ML Winner)</span>
                          ) : (
                            <span className="text-[#C64B43]">{tpDiff} TPs</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* TAB 3: MODEL COMPARISONS                                            */}
      {/* =================================================================== */}
      {activeTab === 'comparison' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
            {/* Model 1: Untuned CatBoost */}
            <div className="bg-white border border-[#147D69]/30 rounded-xl p-4 space-y-3 shadow-sm">
              <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
                <span className="font-bold text-[#252B29] text-xs">CatBoost Baseline</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#147D69]/10 text-[#147D69] font-bold">WINNER</span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-[#737A76]">PR-AUC:</span>
                  <span className="text-[#147D69] font-bold">0.6242</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737A76]">Recall (@0.35):</span>
                  <span className="text-[#147D69] font-bold">77.78%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737A76]">Precision:</span>
                  <span className="text-[#3D4543] font-bold">52.07%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737A76]">ROC-AUC:</span>
                  <span className="text-[#7C6EAF] font-bold">0.9701</span>
                </div>
              </div>
              <p className="text-[10px] text-[#737A76] pt-1 border-t border-[#E2E0D8]">
                Selected for highest unseen-ring generalization and superior recall on Protocol B.
              </p>
            </div>

            {/* Model 2: Tuned CatBoost */}
            <div className="bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-3 shadow-sm">
              <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
                <span className="font-bold text-[#252B29] text-xs">Tuned CatBoost</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#F7F6F2] text-[#737A76] font-bold">OVERFIT</span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-[#737A76]">PR-AUC:</span>
                  <span className="text-[#3D4543] font-bold">0.6131</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737A76]">Recall (@0.35):</span>
                  <span className="text-[#B99A45] font-bold">62.96%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737A76]">Precision:</span>
                  <span className="text-[#3D4543] font-bold">52.58%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737A76]">ROC-AUC:</span>
                  <span className="text-[#7C6EAF] font-bold">0.9723</span>
                </div>
              </div>
              <p className="text-[10px] text-[#737A76] pt-1 border-t border-[#E2E0D8]">
                Hyperparameter tuning overfit training splits, resulting in -14.82% lower recall on unseen rings.
              </p>
            </div>

            {/* Model 3: Random Forest Baseline */}
            <div className="bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-3 shadow-sm">
              <div className="flex items-center justify-between border-b border-[#E2E0D8] pb-2">
                <span className="font-bold text-[#252B29] text-xs">Random Forest</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#F7F6F2] text-[#737A76] font-bold">BASELINE</span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-[#737A76]">PR-AUC:</span>
                  <span className="text-[#3D4543] font-bold">0.5840</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737A76]">Recall:</span>
                  <span className="text-[#3D4543] font-bold">71.60%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737A76]">Precision:</span>
                  <span className="text-[#3D4543] font-bold">48.33%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737A76]">ROC-AUC:</span>
                  <span className="text-[#7C6EAF] font-bold">0.9612</span>
                </div>
              </div>
              <p className="text-[10px] text-[#737A76] pt-1 border-t border-[#E2E0D8]">
                Useful tabular benchmark; lower calibration fidelity than Platt-scaled CatBoost.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* TAB 4: FEATURE IMPORTANCE                                           */}
      {/* =================================================================== */}
      {activeTab === 'features' && (
        <div className="bg-white border border-[#E2E0D8] rounded-xl p-5 space-y-3 shadow-sm">
          <div className="border-b border-[#E2E0D8] pb-2.5">
            <h2 className="text-xs font-bold text-[#252B29] font-mono uppercase flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-[#147D69]" />
              Top Predictive Signals (Observable Feature Attribution)
            </h2>
            <p className="text-[10px] text-[#737A76] font-mono mt-0.5">
              Ranked importance of observable features computed strictly at t &le; T_obs
            </p>
          </div>

          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={top_features}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 140, bottom: 5 }}
              >
                <XAxis type="number" stroke="#E2E0D8" tick={{ fontSize: 10, fontFamily: 'JetBrains Mono', fill: '#737A76' }} />
                <YAxis
                  type="category"
                  dataKey="feature"
                  stroke="#E2E0D8"
                  tick={{ fontSize: 10, fill: '#3D4543', fontFamily: 'JetBrains Mono' }}
                  width={130}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    borderColor: '#E2E0D8',
                    fontSize: '11px',
                    fontFamily: 'JetBrains Mono',
                    color: '#252B29',
                  }}
                />
                <Bar dataKey="importance" fill="#147D69" radius={[0, 4, 4, 0]}>
                  {top_features?.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={index < 3 ? '#147D69' : index < 6 ? '#7C6EAF' : '#4E9BB5'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* TAB 5: EVALUATION METHODOLOGY                                       */}
      {/* =================================================================== */}
      {activeTab === 'methodology' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
          <div className="bg-white border border-[#E2E0D8] rounded-xl p-4 space-y-2 shadow-sm">
            <span className="font-bold text-[#252B29] uppercase text-xs flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-[#147D69]" />
              Protocol A: Chronological Out-of-Time (OOT)
            </span>
            <p className="text-[11px] text-[#737A76] leading-relaxed">
              Splits data chronologically by registration timestamp. Evaluates how well models trained on earlier cohorts generalize to future cohorts where attack tactics may drift over time.
            </p>
            <div className="text-[10px] text-[#9BA09D] pt-1 border-t border-[#E2E0D8]">
              Accounts: 6,000 Train / 2,000 Val / 2,000 Test
            </div>
          </div>

          <div className="bg-white border border-[#147D69]/25 rounded-xl p-4 space-y-2 shadow-sm">
            <span className="font-bold text-[#147D69] uppercase text-xs flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-[#147D69]" />
              Protocol B: Inductive Unseen-Ring Holdout (Primary)
            </span>
            <p className="text-[11px] text-[#737A76] leading-relaxed">
              Entire synthetic abuse rings are assigned atomically to either train, validation, or test. Test rings are completely unseen during training, preventing ring-level identity leakage.
            </p>
            <div className="text-[10px] text-[#147D69] pt-1 border-t border-[#E2E0D8]">
              Primary Benchmark Split: 1,678 untouched test accounts (81 positive attack events).
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
