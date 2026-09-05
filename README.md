# Abuse-Ring Sentinel: AI Risk Intelligence Platform

**Abuse-Ring Sentinel** is a production-grade fintech AI Risk Intelligence & Security Operations Center (SOC) detection engine designed to detect coordinated abuse rings, collusive transaction networks, and multi-accounting clusters across seemingly independent user accounts.

Built for the **Razorpay AI Builder Buildathon**, this system combines supervised machine learning, heterogeneous graph topology, temporal coordination analytics, and multi-entity relationship resolution into an explainable, non-blocking risk scoring engine.

---

## 🌟 Key Capabilities & Architectural Highlights

1. **Multi-Signal Risk Engine**: Modular 0–100 risk scoring combining:
   - **40% Supervised ML Evidence**: Random Forest with balanced class weights.
   - **30% Graph Community Evidence**: Louvain community density, node degree, and link strength.
   - **20% Coordination Evidence**: Temporal activity synchrony and amount-pattern matching.
   - **10% Multi-Entity Relationship**: Multi-entity overlap protecting single-infrastructure shared households.
2. **Defensive Non-Blocking Protocol**: Actionable tiering (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) that routes high-risk cases to human review queues rather than disruptive auto-blocking.
3. **Strict Ground-Truth Isolation**: Operational API endpoints and dashboard views strictly exclude synthetic labels (`ring_id`, `account_type`), relying solely on observable features.
4. **Interactive Coordinated Risk Network Graph**: High-performance interactive HTML5 Canvas/SVG multi-hop graph visualization linking accounts, devices, IPs, and payment destinations.
5. **Human-Readable Reason Codes**: Translates technical anomalies into plain-English analyst rationales (`High Behavioral Risk`, `Destination Funneling`, `Coordinated Timing Burst`).

---

## 🚀 Quickstart: Running the Dashboard

### Prerequisites
- Python 3.9+ with virtual environment (`.venv`)
- Node.js 18+ and npm (only needed if modifying frontend source)

### Option 1: Unified Server (FastAPI + Pre-Built Frontend)
Launch the unified server serving both the REST API and the production-compiled frontend on `http://127.0.0.1:8000`:

```bash
# Activate python environment
source .venv/bin/activate

# Launch dashboard server
python dashboard/run_dashboard.py
```
Open your browser and navigate to: **`http://127.0.0.1:8000`**

### Option 2: Live Development Mode (Vite Hot-Reload)
If you wish to make live frontend modifications:

```bash
# Terminal 1: Launch FastAPI backend
source .venv/bin/activate
python src/api/server.py

# Terminal 2: Launch Vite development server
cd dashboard/frontend
npm run dev
```
Navigate to: **`http://localhost:3000`**

---

## 📊 Dashboard Views

| Page | Description | Key Features |
| :--- | :--- | :--- |
| **1. Overview** | Executive SOC command center | Top KPI metrics, Risk Distribution donut chart, 4-Signal Evidence Stack, Priority Escalations table, Top Risk Drivers, Emerging Clusters grid. |
| **2. Investigations** | Account deep-dive workspace | Filterable account list, 0–100 composite risk dial, 4 modular evidence scorecards, "Why was this account flagged?" reason cards, defensive actions, behavioral metrics, and recent transactions. |
| **3. Risk Clusters** | Coordinated network graph | Interactive Canvas force graph visualizing multi-hop relationships (Accounts, Devices, IPs, Destinations), cluster switcher, and member risk list. |
| **4. Transactions** | Transaction stream explorer | Searchable/filterable stream of 159,569 transactions with counterparty identification, amount filters, and account risk correlation. |
| **5. Model Intelligence** | Empirical evaluation hub | Stratified held-out test metrics (RF vs LR), ML-only vs Full System comparison table, Top Predictive Signals feature importance chart, and Post-Hoc Archetype Generalization breakdown. |
| **6. System Architecture** | Pipeline & data integrity | End-to-end data flow visualization (Data → Features → Graph → ML → Risk Engine → Human Review), pipeline statistics, and verified ground-truth isolation audit. |

---

## 📂 Project Directory Structure

```text
abuse-ring-sentinel/
├── data/
│   ├── raw/                       # 10K accounts, 159K transactions
│   └── processed/
│       ├── account_features.csv   # 27 behavioral, temporal & graph features
│       ├── graph_clusters.csv     # Detected community clusters
│       ├── model_results/         # Baseline metrics & feature importances
│       └── risk_results/          # Account & cluster risk scores, E2E evaluation
├── src/
│   ├── api/                       # FastAPI REST API (server.py)
│   ├── data_generation/           # Synthetic accounts & transaction generator
│   ├── features/                  # Vectorized feature engineering
│   ├── graph/                     # Graph projection & Louvain community detection
│   ├── models/                    # Random Forest & Logistic Regression trainers
│   ├── scoring/                   # Modular 0-100 Risk Engine (risk_engine.py)
│   └── evaluation/                # Hold-out & End-to-End evaluation benchmarks
├── dashboard/
│   ├── frontend/                  # React + Vite + Tailwind + Lucide + Recharts
│   └── run_dashboard.py           # Unified launcher script
├── tests/                         # 41 automated unit & integration tests
├── requirements.txt
└── README.md
```

---

## 🧪 Automated Testing

Run the complete test suite across the API, Risk Engine, Feature Engineering, Graph Analysis, and End-to-End Evaluation:

```bash
source .venv/bin/activate
pytest tests
```

**Status**: `41 passed in ~9s`
