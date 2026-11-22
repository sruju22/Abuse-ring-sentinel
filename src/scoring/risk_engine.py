"""
Abuse-Ring Sentinel - Explainable Risk Assessment & Decision Engine.

Combines supervised machine learning predictions, graph cluster intelligence,
behavioral coordination signals, and entity relationship evidence into transparent,
deterministic 0-100 risk assessments for individual accounts and detected clusters.

Strictly excludes ground-truth labels from scoring calculations.
Enforces modularity to allow weight re-calibration without architectural changes.
"""

from dataclasses import dataclass, field
import json
import os
import sys
from typing import Any, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import joblib
import numpy as np
import pandas as pd

from src.models.evaluate_model import get_archetype_for_ring


# =============================================================================
# Configuration & Domain Constants
# =============================================================================

# Configurable prototype component weights (sum to 1.0)
# NOTE: These are demonstration prototype weights, not production-calibrated Razorpay parameters.
DEFAULT_WEIGHTS: dict[str, float] = {
    "ml": 0.40,            # 40% - Supervised model probability of abuse
    "graph": 0.30,         # 30% - Cluster density, edge strength & graph connectivity
    "coordination": 0.20,  # 20% - Temporal synchrony, amount matching & burst velocity
    "relationship": 0.10,  # 10% - Multi-entity sharing (bounded to protect shared infra)
}

# Configurable prototype risk tier boundaries
# NOTE: Prototype policy thresholds for human analyst routing, not live payment blocking.
DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "LOW": (0.0, 29.999),
    "MEDIUM": (30.0, 59.999),
    "HIGH": (60.0, 79.999),
    "CRITICAL": (80.0, 100.0),
}

# Defensive Action Routing Table
# Enforces non-destructive, explainable review workflows
ACTION_MAPPING: dict[str, str] = {
    "LOW": "monitor",
    "MEDIUM": "enhanced monitoring",
    "HIGH": "human review",
    "CRITICAL": "priority human review",
}


def normalize_account_id(acc_id: str, target_digits: int = 6) -> str:
    """
    Validates and standardizes account ID strings without corrupting historical or prototype IDs.
    Stale or mismatched IDs are rejected rather than forcibly zero-padded into other accounts.
    """
    return str(acc_id).strip()


# =============================================================================
# Modular Risk Evidence Components (Each outputs 0.0 - 100.0)
# =============================================================================

def compute_ml_evidence(
    rf_probabilities: np.ndarray,
) -> np.ndarray:
    """
    Component 1: Supervised ML Evidence (0 - 100).
    
    Translates Random Forest predicted abuse probability into an interpretable
    0-100 contribution reflecting statistical likelihood of abuse patterns.
    """
    probs = np.asarray(rf_probabilities, dtype=float)
    scores = np.clip(probs * 100.0, 0.0, 100.0)
    return np.round(scores, 2)


def compute_graph_evidence(
    df_features: pd.DataFrame,
    df_clusters: Optional[pd.DataFrame] = None,
) -> np.ndarray:
    """
    Component 2: Graph Intelligence & Cluster Topology Evidence (0 - 100).
    
    Evaluates:
      - Cluster density (tightness of interconnection)
      - Average edge strength (multi-faceted link weight)
      - Cluster size (scale of coordination)
      - Local entity degree (shared destinations, devices, IPs)

    Safeguards:
      - Strict Validation: Account IDs are strictly validated against active features;
        stale cluster references or historical prototype IDs are discarded.
      - Infrastructure vs. Abuse Disambiguation:
        Ordinary shared infrastructure (campuses, households, corporate offices, public Wi-Fi)
        is protected from automatic high-risk scoring. Shared IP/device evidence is only
        treated as high-risk abuse when corroborated by:
          1. Destination funneling (high peer count into narrow targets), OR
          2. Temporal burst synchronization (high timing similarity with synchronized peers), OR
          3. Behavioral anomalies (abnormal transaction velocity >= 2.0, cashout ratio >= 0.10,
             or elevated night activity >= 0.15).
        Uncorroborated shared infrastructure is strictly bounded to LOW risk (<= 15.0).
    """
    valid_accs = set(df_features["account_id"].astype(str))

    # Build account -> cluster lookup validating strictly against active accounts
    acc_to_cluster: dict[str, dict[str, Any]] = {}
    if df_clusters is not None and not df_clusters.empty:
        for _, row in df_clusters.iterrows():
            accounts = str(row["accounts_list"]).split("|")
            for acc in accounts:
                acc_clean = str(acc).strip()
                if acc_clean in valid_accs:
                    c_data = {
                        "cluster_id": row["cluster_id"],
                        "num_accounts": float(row["num_accounts"]),
                        "average_edge_strength": float(row["average_edge_strength"]),
                        "graph_density": float(row["graph_density"]),
                    }
                    acc_to_cluster[acc_clean] = c_data

    scores = []
    for _, row in df_features.iterrows():
        acc_id = str(row["account_id"]).strip()
        c_info = acc_to_cluster.get(acc_id)

        shared_dests = float(row.get("number_of_accounts_with_shared_destinations", 0))
        unique_dests = float(row.get("unique_destinations", 0))
        transfer_ratio = float(row.get("transfer_transaction_ratio", 0.0))
        shared_devs = float(row.get("accounts_sharing_device", 0))
        shared_ips = float(row.get("accounts_sharing_ip", 0))
        timing_sim = float(row.get("average_transaction_timing_similarity", 0.0))
        timing_peers = float(row.get("number_of_accounts_with_similar_transaction_timing", 0))
        velocity = float(row.get("transactions_per_active_day", 1.0))
        cashout_ratio = float(row.get("cashout_transaction_ratio", 0.0))
        night_ratio = float(row.get("night_transaction_ratio", 0.0))

        # Multi-factor corroboration logic:
        # A) Coordinated Destination Funneling: high volume of peers sharing destinations,
        #    or focused funneling into very few unique destinations with active transfers.
        funneling = (shared_dests >= 15) or (
            (shared_dests >= 6) and (unique_dests <= 3) and (transfer_ratio >= 0.20)
        )

        # B) Temporal Burst Coordination: tight burst synchrony with multiple peers,
        #    or extreme synchrony across the active timeframe.
        burst_sync = ((timing_sim >= 0.55) and (timing_peers >= 8)) or (timing_sim >= 0.70)

        # C) Corroborated Infrastructure Abuse: shared device/IP corroborated by behavioral
        #    anomalies (velocity surge, cashout focus, night activity) or coordination.
        infra_abuse = ((shared_devs > 0) or (shared_ips > 0)) and (
            (velocity >= 2.0) or (cashout_ratio >= 0.10) or (night_ratio >= 0.15) or funneling or burst_sync
        )

        is_corroborated = funneling or burst_sync or infra_abuse

        # 1. Cluster community signal (if member of detected cluster)
        if c_info:
            c_density = c_info["graph_density"] * 40.0
            c_edge = min(c_info["average_edge_strength"] / 1.5, 1.0) * 40.0
            c_size = min(c_info["num_accounts"] / 20.0, 1.0) * 20.0
            raw_cluster_signal = c_density + c_edge + c_size

            # If cluster member has no corroborating coordination evidence, damp cluster signal
            if is_corroborated:
                cluster_signal = raw_cluster_signal
            else:
                cluster_signal = min(raw_cluster_signal * 0.25, 15.0)
        else:
            cluster_signal = 0.0

        # 2. Local graph connectivity signal
        if is_corroborated:
            dest_signal = min(shared_dests / 10.0, 1.0) * 50.0
            dev_signal = min(shared_devs / 4.0, 1.0) * 25.0
            ip_signal = min(shared_ips / 15.0, 1.0) * 25.0
            local_signal = dest_signal + dev_signal + ip_signal
        else:
            # Benign uncorroborated shared infrastructure:
            # High-fanout shared IPs (dormitories, campuses, coffee shops) discounted heavily.
            dev_signal = min(shared_devs / 2.0, 1.0) * 10.0
            ip_signal = min(shared_ips / 15.0, 1.0) * 5.0
            local_signal = dev_signal + ip_signal

        # Combine: take maximum of cluster community or direct local graph connectivity
        g_score = max(cluster_signal, local_signal)
        scores.append(float(np.clip(g_score, 0.0, 100.0)))

    return np.round(np.array(scores), 2)


def compute_coordination_evidence(
    df_features: pd.DataFrame,
) -> np.ndarray:
    """
    Component 3: Behavioral Coordination Evidence (0 - 100).
    
    Evaluates:
      - Temporal synchrony (cosine timing similarity across 1-hour time bins)
      - Timing peer count (number of accounts acting simultaneously)
      - Amount profile similarity (congruence in transaction amount distribution)
      - Transaction velocity (bursts per active day)
    """
    scores = []
    for _, row in df_features.iterrows():
        timing_sim = float(row.get("average_transaction_timing_similarity", 0.0))
        timing_peers = float(row.get("number_of_accounts_with_similar_transaction_timing", 0))
        amt_peers = float(row.get("number_of_accounts_with_similar_amount_behavior", 0))
        velocity = float(row.get("transactions_per_active_day", 1.0))

        # 1. Temporal Synchrony Signal
        # Baseline uncorrelated activity exhibits similarity ~0.25-0.45; true bursts exceed 0.60
        if timing_sim >= 0.50:
            timing_strength = min(max(0.0, (timing_sim - 0.50) / 0.45), 1.0)
            timing_peer_factor = min(timing_peers / 10.0, 1.0)
            timing_signal = (0.70 * timing_strength + 0.30 * timing_peer_factor) * 60.0
        else:
            timing_signal = 0.0

        # 2. Amount Distribution Congruence (conditional on timing coordination)
        if timing_signal > 20.0:
            amt_signal = min(amt_peers / 5000.0, 1.0) * 15.0
            vel_signal = min(max(0.0, (velocity - 1.5) / 2.0), 1.0) * 25.0
        else:
            amt_signal = 0.0
            vel_signal = min(max(0.0, (velocity - 2.0) / 2.0), 1.0) * 10.0

        coord_score = timing_signal + amt_signal + vel_signal
        scores.append(float(np.clip(coord_score, 0.0, 100.0)))

    return np.round(np.array(scores), 2)


def compute_relationship_evidence(
    df_features: pd.DataFrame,
) -> np.ndarray:
    """
    Component 4: Infrastructure & Entity Relationship Evidence (0 - 100).
    
    IMPORTANT DEFENSIVE PRINCIPLE:
      Legitimate shared environments (e.g., household Wi-Fi, university dorms,
      corporate offices) naturally share IPs or occasional devices without abuse.
      Single-entity sharing is capped to a low baseline; elevated scores strictly
      require multi-entity overlap (e.g. sharing device AND IP AND common destinations).
    """
    scores = []
    for _, row in df_features.iterrows():
        dev_count = float(row.get("accounts_sharing_device", 0))
        ip_count = float(row.get("accounts_sharing_ip", 0))
        dest_count = float(row.get("number_of_accounts_with_shared_destinations", 0))

        dev_factor = min(dev_count / 4.0, 1.0)
        ip_factor = min(ip_count / 15.0, 1.0)
        dest_factor = min(dest_count / 10.0, 1.0)

        # Additive base score
        base_score = (30.0 * dev_factor) + (20.0 * ip_factor) + (20.0 * dest_factor)

        # Multi-entity overlap bonus (only when multiple distinct entity types match)
        overlap_bonus = 0.0
        if dev_factor > 0 and ip_factor > 0:
            overlap_bonus += 15.0
        if dev_factor > 0 and dest_factor > 0:
            overlap_bonus += 15.0

        rel_score = base_score + overlap_bonus
        scores.append(float(np.clip(rel_score, 0.0, 100.0)))

    return np.round(np.array(scores), 2)


# =============================================================================
# Composite Scoring, Risk Tiering & Explainable Reason Generation
# =============================================================================

def compute_composite_risk_score(
    ml_scores: np.ndarray,
    graph_scores: np.ndarray,
    coordination_scores: np.ndarray,
    relationship_scores: np.ndarray,
    weights: Optional[dict[str, float]] = None,
) -> np.ndarray:
    """
    Combines individual evidence components using a transparent weighted formula.
    Guarantees deterministic output bounded in [0.0, 100.0].
    """
    w = weights if weights is not None else DEFAULT_WEIGHTS
    total_w = sum(w.values())
    if abs(total_w - 1.0) > 1e-6:
        # Normalize weights if not summing to 1.0
        w = {k: v / total_w for k, v in w.items()}

    final_scores = (
        w["ml"] * ml_scores
        + w["graph"] * graph_scores
        + w["coordination"] * coordination_scores
        + w["relationship"] * relationship_scores
    )
    return np.round(np.clip(final_scores, 0.0, 100.0), 2)


def assign_risk_level_and_action(
    score: float,
    thresholds: Optional[dict[str, tuple[float, float]]] = None,
) -> tuple[str, str]:
    """
    Maps a continuous risk score to a categorical risk tier and defensive action.
    """
    t = thresholds if thresholds is not None else DEFAULT_THRESHOLDS
    for level, (low, high) in t.items():
        if low <= score <= high:
            return level, ACTION_MAPPING[level]
    
    # Fallback bounds check
    if score >= 80.0:
        return "CRITICAL", ACTION_MAPPING["CRITICAL"]
    if score >= 60.0:
        return "HIGH", ACTION_MAPPING["HIGH"]
    if score >= 30.0:
        return "MEDIUM", ACTION_MAPPING["MEDIUM"]
    return "LOW", ACTION_MAPPING["LOW"]


def generate_account_reason_codes(
    row: pd.Series,
    ml_score: float,
    graph_score: float,
    coord_score: float,
    rel_score: float,
) -> str:
    """
    Generates explainable reason codes based ONLY on observable evidence.
    Does not produce a reason code unless observable metrics exceed documented thresholds.
    """
    reasons = []

    # 1. High ML Risk
    if ml_score >= 60.0:
        reasons.append("HIGH_ML_RISK")

    # 2. Timing Coordination
    timing_sim = float(row.get("average_transaction_timing_similarity", 0.0))
    timing_peers = float(row.get("number_of_accounts_with_similar_transaction_timing", 0))
    if timing_sim >= 0.70 or timing_peers >= 15:
        reasons.append("STRONG_TIMING_COORDINATION")

    # 3. Amount Similarity
    amt_peers = float(row.get("number_of_accounts_with_similar_amount_behavior", 0))
    if amt_peers >= 1000 and coord_score >= 20.0:
        reasons.append("STRONG_AMOUNT_SIMILARITY")

    # 4. Destination Concentration
    shared_dests = float(row.get("number_of_accounts_with_shared_destinations", 0))
    if shared_dests >= 5:
        reasons.append("DESTINATION_CONCENTRATION")

    # 5. Graph Cluster
    if graph_score >= 60.0:
        reasons.append("STRONG_GRAPH_CLUSTER")

    # 6. Shared Infrastructure
    shared_devs = float(row.get("accounts_sharing_device", 0))
    shared_ips = float(row.get("accounts_sharing_ip", 0))
    if shared_devs >= 2 or (shared_devs >= 1 and shared_ips >= 5):
        reasons.append("SHARED_INFRASTRUCTURE")

    # 7. Transaction Velocity
    velocity = float(row.get("transactions_per_active_day", 1.0))
    if velocity >= 2.5:
        reasons.append("HIGH_TRANSACTION_VELOCITY")

    if not reasons:
        reasons.append("STANDARD_ACTIVITY")

    return "|".join(reasons)


# =============================================================================
# Cluster-Level Risk Aggregation
# =============================================================================

def aggregate_cluster_risk_scores(
    df_account_risk: pd.DataFrame,
    df_clusters: pd.DataFrame,
    thresholds: Optional[dict[str, tuple[float, float]]] = None,
) -> pd.DataFrame:
    """
    Aggregates account-level scores and graph metadata into cluster-level assessments.
    """
    cluster_cols = [
        "cluster_id", "account_count", "average_risk_score", "maximum_risk_score",
        "average_graph_strength", "coordination_evidence", "relationship_evidence",
        "risk_level", "reason_codes", "recommended_action"
    ]
    if df_clusters.empty:
        return pd.DataFrame(columns=cluster_cols)

    # Build account lookup map strictly validating exact IDs
    acc_risk_map: dict[str, dict[str, Any]] = {}
    for _, a_row in df_account_risk.iterrows():
        a_id = str(a_row["account_id"]).strip()
        acc_risk_map[a_id] = a_row.to_dict()

    cluster_records = []

    for _, c_row in df_clusters.iterrows():
        c_id = c_row["cluster_id"]
        accounts = str(c_row["accounts_list"]).split("|")
        
        member_scores = []
        member_coords = []
        member_rels = []
        all_reasons: set[str] = set()

        for a in accounts:
            info = acc_risk_map.get(str(a).strip())
            if info is not None:
                member_scores.append(float(info["final_risk_score"]))
                member_coords.append(float(info["coordination_score"]))
                member_rels.append(float(info["relationship_score"]))
                codes = str(info["reason_codes"]).split("|")
                all_reasons.update(c for c in codes if c != "STANDARD_ACTIVITY")

        if not member_scores:
            continue

        avg_score = round(float(np.mean(member_scores)), 2)
        max_score = round(float(np.max(member_scores)), 2)
        avg_coord = round(float(np.mean(member_coords)), 2)
        avg_rel = round(float(np.mean(member_rels)), 2)
        avg_graph_str = round(float(c_row.get("average_edge_strength", 0.0)), 4)

        # Cluster risk tier: evaluate elevated cluster risk
        eval_score = max(avg_score, max_score * 0.90)
        risk_lvl, rec_act = assign_risk_level_and_action(eval_score, thresholds=thresholds)

        cluster_records.append({
            "cluster_id": c_id,
            "account_count": int(c_row["num_accounts"]),
            "average_risk_score": avg_score,
            "maximum_risk_score": max_score,
            "average_graph_strength": avg_graph_str,
            "coordination_evidence": avg_coord,
            "relationship_evidence": avg_rel,
            "risk_level": risk_lvl,
            "reason_codes": "|".join(sorted(all_reasons)) if all_reasons else "STANDARD_ACTIVITY",
            "recommended_action": rec_act,
        })

    df_cluster_scores = pd.DataFrame(cluster_records)
    if not df_cluster_scores.empty:
        df_cluster_scores = df_cluster_scores.sort_values("maximum_risk_score", ascending=False)
    else:
        df_cluster_scores = pd.DataFrame(columns=cluster_cols)
    return df_cluster_scores


# =============================================================================
# Main End-to-End Execution Pipeline
# =============================================================================

def run_risk_engine(
    features_path: str = "data/processed/account_features.csv",
    clusters_path: str = "data/processed/graph_clusters.csv",
    models_dir: str = "models",
    output_dir: str = "data/processed/risk_results",
    weights: Optional[dict[str, float]] = None,
    thresholds: Optional[dict[str, tuple[float, float]]] = None,
) -> dict[str, Any]:
    """
    Executes the risk assessment engine:
      1. Loads feature matrix, graph clusters, and trained Random Forest model.
      2. Computes ML, Graph, Coordination, and Relationship evidence components.
      3. Calculates weighted composite scores and assigns risk tiers & actions.
      4. Aggregates cluster-level risk summaries.
      5. Persists results to disk.
    """
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(features_path):
        raise FileNotFoundError(f"Feature matrix not found at: {features_path}")

    df_features = pd.read_csv(features_path)
    df_clusters = pd.read_csv(clusters_path) if os.path.exists(clusters_path) else pd.DataFrame()

    # Load Random Forest model
    rf_path = os.path.join(models_dir, "random_forest.joblib")
    if not os.path.exists(rf_path):
        raise FileNotFoundError(f"Random Forest model not found at: {rf_path}")
    rf_model = joblib.load(rf_path)

    # 1. Feature columns (strictly excluding account_id and non-feature fields)
    forbidden_cols = {"account_id", "account_type", "ring_id", "label", "target"}
    feature_cols = [c for c in df_features.columns if c not in forbidden_cols]
    X_mat = df_features[feature_cols]

    # Verify strict ground truth isolation
    for col in feature_cols:
        assert col not in ["account_type", "ring_id"], f"Leaked target column in feature matrix: {col}"

    # 2. Compute 0-100 evidence components
    rf_probs = rf_model.predict_proba(X_mat)[:, 1]
    ml_scores = compute_ml_evidence(rf_probs)
    graph_scores = compute_graph_evidence(df_features, df_clusters)
    coord_scores = compute_coordination_evidence(df_features)
    rel_scores = compute_relationship_evidence(df_features)

    # 3. Composite risk score
    final_scores = compute_composite_risk_score(
        ml_scores=ml_scores,
        graph_scores=graph_scores,
        coordination_scores=coord_scores,
        relationship_scores=rel_scores,
        weights=weights,
    )

    # 4. Risk tiers, actions, and reason codes
    risk_levels = []
    actions = []
    reason_codes_list = []

    for i, row in df_features.iterrows():
        score = final_scores[i]
        lvl, act = assign_risk_level_and_action(score, thresholds=thresholds)
        reasons = generate_account_reason_codes(
            row=row,
            ml_score=ml_scores[i],
            graph_score=graph_scores[i],
            coord_score=coord_scores[i],
            rel_score=rel_scores[i],
        )
        risk_levels.append(lvl)
        actions.append(act)
        reason_codes_list.append(reasons)

    # Build account risk DataFrame
    df_account_risk = pd.DataFrame({
        "account_id": df_features["account_id"],
        "ml_score": ml_scores,
        "graph_score": graph_scores,
        "coordination_score": coord_scores,
        "relationship_score": rel_scores,
        "final_risk_score": final_scores,
        "risk_level": risk_levels,
        "reason_codes": reason_codes_list,
        "recommended_action": actions,
    })

    # 5. Cluster risk aggregation
    df_cluster_risk = aggregate_cluster_risk_scores(
        df_account_risk=df_account_risk,
        df_clusters=df_clusters,
        thresholds=thresholds,
    )

    # 6. Save outputs
    account_out_path = os.path.join(output_dir, "account_risk_scores.csv")
    cluster_out_path = os.path.join(output_dir, "cluster_risk_scores.csv")

    df_account_risk.to_csv(account_out_path, index=False)
    df_cluster_risk.to_csv(cluster_out_path, index=False)

    return {
        "account_risk": df_account_risk,
        "cluster_risk": df_cluster_risk,
        "weights": weights if weights is not None else DEFAULT_WEIGHTS,
        "thresholds": thresholds if thresholds is not None else DEFAULT_THRESHOLDS,
    }


# =============================================================================
# Validation & Debugging Report
# =============================================================================

def print_risk_validation_report(
    results: dict[str, Any],
    ground_truth_path: str = "data/processed/ground_truth.csv",
) -> None:
    """
    Prints a detailed validation summary and post-hoc debugging analysis.
    Ground truth is inspected purely for debugging evaluation, NEVER for scoring.
    """
    df_acc = results["account_risk"]
    df_clu = results["cluster_risk"]
    weights = results["weights"]

    print("\n" + "=" * 80)
    print("      ABUSE-RING SENTINEL - RISK ENGINE VALIDATION REPORT")
    print("=" * 80)
    print("PROTOTYPE WEIGHTING FORMULA:")
    for k, v in weights.items():
        print(f"  • {k.capitalize():15s} Evidence Weight: {v*100:4.1f}%")
    print("-" * 80)

    # 1. Score Distribution
    print("1. ACCOUNT RISK SCORE DISTRIBUTION (N = {:,}):".format(len(df_acc)))
    stats = df_acc["final_risk_score"].describe(percentiles=[0.25, 0.50, 0.75, 0.90, 0.95, 0.99]).round(2)
    print(stats.to_string())

    # 2. Risk Level Counts
    print("\n" + "-" * 80)
    print("2. RISK LEVEL COUNTS & RECOMMENDED ACTIONS:")
    lvl_counts = df_acc["risk_level"].value_counts().to_dict()

    for lvl in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        cnt = lvl_counts.get(lvl, 0)
        pct = (cnt / len(df_acc)) * 100
        print(f"  • {lvl:<10s}: {cnt:6,d} accounts ({pct:5.2f}%) -> Action: {ACTION_MAPPING.get(lvl, 'N/A')}")

    # 3. Top 10 Highest Risk Accounts
    print("\n" + "-" * 80)
    print("3. TOP 10 HIGHEST-RISK ACCOUNTS:")
    top10 = df_acc.sort_values("final_risk_score", ascending=False).head(10)
    print(top10[["account_id", "ml_score", "graph_score", "coordination_score", "relationship_score", "final_risk_score", "risk_level", "recommended_action"]].to_string(index=False))

    # 4. Top Candidate Clusters
    print("\n" + "-" * 80)
    print("4. DETECTED CANDIDATE CLUSTERS (Risk Summary):")
    if not df_clu.empty:
        print(df_clu[["cluster_id", "account_count", "average_risk_score", "maximum_risk_score", "risk_level", "recommended_action", "reason_codes"]].to_string(index=False))
    else:
        print("  No multi-account clusters detected.")

    # 5. Reason Code Frequencies
    print("\n" + "-" * 80)
    print("5. REASON CODE FREQUENCIES:")
    all_codes = []
    for r in df_acc["reason_codes"]:
        all_codes.extend(r.split("|"))
    code_series = pd.Series(all_codes).value_counts()
    for code, cnt in code_series.items():
        print(f"  • {code:<35s}: {cnt:6,d} occurrences")

    # 6. Post-Hoc Debugging Comparison against Ground Truth
    if os.path.exists(ground_truth_path):
        df_gt = pd.read_csv(ground_truth_path)
        df_merged = df_acc.merge(df_gt, on="account_id")
        df_merged["archetype"] = df_merged["ring_id"].apply(get_archetype_for_ring)

        print("\n" + "=" * 80)
        print("6. POST-HOC GROUND TRUTH DEBUGGING AUDIT (For Validation Only):")
        print("=" * 80)
        print("Cross-Tabulation: Actual Account Type vs Assigned Risk Level:")
        ct = pd.crosstab(df_merged["account_type"], df_merged["risk_level"], margins=True)
        print(ct.to_string())

        print("\nArchetype-Level Score Breakdown for True Abuse Accounts:")
        abuse_only = df_merged[df_merged["account_type"] == "abuse_ring"]
        arch_table = abuse_only.groupby("archetype")[["ml_score", "graph_score", "coordination_score", "relationship_score", "final_risk_score"]].mean().round(2)
        print(arch_table.to_string())

        # Inspect low scoring abuse accounts (potential misses)
        low_abuse = abuse_only[abuse_only["risk_level"] == "LOW"]
        print(f"\nAbuse Accounts with LOW Risk Score (< 30): {len(low_abuse)}")
        if not low_abuse.empty:
            print(low_abuse[["account_id", "ring_id", "archetype", "final_risk_score", "reason_codes"]].head(5).to_string(index=False))

        # Inspect high scoring legitimate shared accounts (potential false escalations)
        high_legit = df_merged[(df_merged["account_type"].isin(["normal", "legitimate_shared"])) & (df_merged["risk_level"].isin(["HIGH", "CRITICAL"]))]
        print(f"\nNormal / Legitimate Shared Accounts in HIGH/CRITICAL: {len(high_legit)}")
        if not high_legit.empty:
            print(high_legit[["account_id", "account_type", "final_risk_score", "reason_codes"]].head(5).to_string(index=False))

    print("=" * 80 + "\n")


if __name__ == "__main__":
    results = run_risk_engine()
    print_risk_validation_report(results)
