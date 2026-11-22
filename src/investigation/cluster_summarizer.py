"""
Abuse-Ring Sentinel - Evidence-Backed Graph Investigation Engine.
Module: Investigative Cluster Summarizer.

Provides explainable, evidence-backed summaries for:
  1. Global 30-Day Retrospective Clusters (from Louvain graph clustering).
     - Carries explicit retrospective disclaimer.
     - Never used as point-in-time predictive features.
  2. Point-in-Time Observation Window Communities (ego-networks bounded by t <= T_obs).
     - Strictly respects temporal boundary of focal accounts.

Reconciles all 10,000 accounts with 9,990 valid predictive accounts, clearly
flagging accounts with incomplete outcome windows.
Ground truth (ring_id, archetype) is strictly isolated to optional evaluation metadata.
"""

from dataclasses import asdict, dataclass
import os
from typing import Any, Optional
import joblib
import networkx as nx
import numpy as np
import pandas as pd

from src.evaluation.evaluation_protocols import build_unseen_ring_splits
from src.investigation.evidence_engine import (
    extract_account_relationships,
    extract_point_in_time_community,
    get_account_observation_metadata,
)

DEFAULT_MODEL_PATH = "data/processed/benchmark_results/models/catboost_baseline_platt_calibrated.joblib"
DEFAULT_FEATURES_PATH = "data/processed/account_features_pit_inductive.csv"
DEFAULT_GROUND_TRUTH_PATH = "data/processed/ground_truth_pit.csv"
DEFAULT_ACCOUNTS_PATH = "data/raw/accounts.csv"
DEFAULT_TRANSACTIONS_PATH = "data/raw/transactions.csv"
DEFAULT_CLUSTERS_PATH = "data/processed/graph_clusters.csv"

HIGH_RISK_THRESHOLD = 0.35  # Validation-frozen CatBoost decision threshold


@dataclass
class InvestigativeClusterSummary:
    """Structured cluster investigation summary for fraud analysts."""
    cluster_id: str
    cluster_mode: str          # POINT_IN_TIME_OBSERVATION_WINDOW | GLOBAL_30_DAY_RETROSPECTIVE
    num_members: int
    member_account_ids: list[str]
    excluded_members: list[str]  # Incomplete outcome window accounts
    ml_risk_distribution: dict[str, Any]
    high_risk_members: list[dict[str, Any]]
    top_relationships: list[dict[str, Any]]
    temporal_span: dict[str, Any]
    disclaimer: Optional[str] = None
    evaluation_meta: Optional[dict[str, Any]] = None
    connectivity_metadata: Optional[dict[str, Any]] = None


class InvestigationModelCache:
    """Thread-safe cache for precomputed model probabilities and dataset tables."""
    _instance: Optional["InvestigationModelCache"] = None

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        features_path: str = DEFAULT_FEATURES_PATH,
        gt_path: str = DEFAULT_GROUND_TRUTH_PATH,
        accounts_path: str = DEFAULT_ACCOUNTS_PATH,
        tx_path: str = DEFAULT_TRANSACTIONS_PATH,
        clusters_path: str = DEFAULT_CLUSTERS_PATH,
    ):
        self.model_path = model_path
        self.features_path = features_path
        self.gt_path = gt_path
        self.accounts_path = accounts_path
        self.tx_path = tx_path
        self.clusters_path = clusters_path

        self._probabilities: Optional[dict[str, float]] = None
        self._df_features: Optional[pd.DataFrame] = None
        self._df_gt: Optional[pd.DataFrame] = None
        self._df_accounts: Optional[pd.DataFrame] = None
        self._df_tx: Optional[pd.DataFrame] = None
        self._df_clusters: Optional[pd.DataFrame] = None
        self._excluded_accounts: Optional[set[str]] = None

    @classmethod
    def get_instance(cls) -> "InvestigationModelCache":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_data(self) -> None:
        """Loads and precomputes probabilities across all accounts."""
        if self._probabilities is not None:
            return

        if os.path.exists(self.accounts_path):
            self._df_accounts = pd.read_csv(self.accounts_path)
            self._df_accounts["account_id"] = self._df_accounts["account_id"].astype(str).str.strip()
        else:
            self._df_accounts = pd.DataFrame()

        if os.path.exists(self.gt_path):
            self._df_gt = pd.read_csv(self.gt_path)
            self._df_gt["account_id"] = self._df_gt["account_id"].astype(str).str.strip()
        else:
            self._df_gt = pd.DataFrame()

        if os.path.exists(self.features_path):
            self._df_features = pd.read_csv(self.features_path)
            self._df_features["account_id"] = self._df_features["account_id"].astype(str).str.strip()
        else:
            self._df_features = pd.DataFrame()

        if os.path.exists(self.tx_path):
            self._df_tx = pd.read_csv(self.tx_path)
            self._df_tx["account_id"] = self._df_tx["account_id"].astype(str).str.strip()
            self._df_tx["timestamp_dt"] = pd.to_datetime(self._df_tx["timestamp"])
        else:
            self._df_tx = pd.DataFrame()

        if os.path.exists(self.clusters_path):
            self._df_clusters = pd.read_csv(self.clusters_path)
            self._df_clusters["cluster_id"] = self._df_clusters["cluster_id"].astype(str).str.strip()
        else:
            self._df_clusters = pd.DataFrame()

        # Identify excluded accounts (present in accounts.csv but not in valid prediction features)
        all_accs = set(self._df_accounts["account_id"].unique()) if not self._df_accounts.empty else set()
        valid_accs = set(self._df_features["account_id"].unique()) if not self._df_features.empty else set()
        self._excluded_accounts = all_accs - valid_accs

        # Precompute CatBoost calibrated probabilities
        if os.path.exists(self.model_path) and not self._df_features.empty and not self._df_gt.empty:
            try:
                model = joblib.load(self.model_path)
                # Retrieve feature columns defined in benchmark splits
                split_b = build_unseen_ring_splits(self._df_features, self._df_gt, random_state=42)
                feature_cols = split_b.feature_columns
                X = self._df_features[feature_cols]
                probs = model.predict_proba(X)[:, 1]
                self._probabilities = {}
                for acc, p in zip(self._df_features["account_id"], probs):
                    self._probabilities[acc] = float(p)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"CRITICAL: CatBoost model inference failed ({e}). "
                    "Ensure you are running under the project virtual environment (.venv) where catboost is installed: "
                    "Run: source .venv/bin/activate or .venv/bin/python dashboard/run_dashboard.py"
                )
                self._probabilities = None
                raise

    @property
    def probabilities(self) -> dict[str, float]:
        self.load_data()
        return self._probabilities or {}

    @property
    def df_features(self) -> pd.DataFrame:
        self.load_data()
        return self._df_features

    @property
    def df_accounts(self) -> pd.DataFrame:
        self.load_data()
        return self._df_accounts

    @property
    def df_gt(self) -> pd.DataFrame:
        self.load_data()
        return self._df_gt

    @property
    def df_tx(self) -> pd.DataFrame:
        self.load_data()
        return self._df_tx

    @property
    def df_clusters(self) -> pd.DataFrame:
        self.load_data()
        return self._df_clusters

    @property
    def excluded_accounts(self) -> set[str]:
        self.load_data()
        return self._excluded_accounts or set()


def get_account_ml_prediction(account_id: str) -> dict[str, Any]:
    """
    Returns the calibrated CatBoost baseline prediction for an account.
    Explicitly handles excluded accounts with incomplete outcome windows.
    """
    cache = InvestigationModelCache.get_instance()
    clean_id = str(account_id).strip()

    if clean_id in cache.excluded_accounts:
        return {
            "account_id": clean_id,
            "calibrated_probability": None,
            "is_high_risk": False,
            "threshold": HIGH_RISK_THRESHOLD,
            "status": "INCOMPLETE_OUTCOME_WINDOW",
            "explanation": (
                f"Account {clean_id} registered within 7 days of dataset cutoff. "
                f"Incomplete outcome window; excluded from predictive benchmarking."
            ),
        }

    probs = cache.probabilities
    if clean_id not in probs:
        return {
            "account_id": clean_id,
            "calibrated_probability": None,
            "is_high_risk": False,
            "threshold": HIGH_RISK_THRESHOLD,
            "status": "NOT_FOUND",
            "explanation": f"Account {clean_id} was not found in dataset.",
        }

    p = probs[clean_id]
    is_high = p >= HIGH_RISK_THRESHOLD
    risk_tier = "CRITICAL" if p >= 0.70 else ("HIGH" if p >= 0.35 else ("MEDIUM" if p >= 0.15 else "LOW"))

    return {
        "account_id": clean_id,
        "calibrated_probability": round(p, 4),
        "is_high_risk": is_high,
        "risk_tier": risk_tier,
        "threshold": HIGH_RISK_THRESHOLD,
        "status": "SCORED",
        "explanation": f"CatBoost calibrated probability: {p:.4f} (Threshold: {HIGH_RISK_THRESHOLD}).",
    }


def extract_cluster_internal_relationships(
    member_accs: list[str],
    df_accounts: pd.DataFrame,
    df_tx: pd.DataFrame,
    max_relationships: Optional[int] = None,
    evidence_type: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Complete, explainable extraction of internal relationships connecting members of a cluster.
    Surfaces shared devices, shared IPs, and shared transaction destinations without silent truncation.
    Preserves relationship diversity across all present infrastructure types.
    """
    members_set = set(member_accs)
    acc_sub = df_accounts[df_accounts["account_id"].isin(members_set)]
    relationships = []

    # 1. Internal Shared Devices
    if "device_id" in acc_sub.columns and (not evidence_type or evidence_type == "SHARED_DEVICE"):
        dev_counts = acc_sub["device_id"].value_counts()
        for dev_id, count in dev_counts[dev_counts > 1].items():
            if str(dev_id) == "nan":
                continue
            shared_members = acc_sub[acc_sub["device_id"] == dev_id]["account_id"].tolist()
            for i in range(len(shared_members)):
                for j in range(i + 1, len(shared_members)):
                    relationships.append({
                        "source_account": str(shared_members[i]),
                        "target_account": str(shared_members[j]),
                        "evidence_type": "SHARED_DEVICE",
                        "evidence_strength": "STRONG" if count <= 4 else "MODERATE",
                        "shared_entity_id": str(dev_id),
                        "support_count": int(count),
                        "explanation": f"Both accounts registered using hardware device {dev_id} ({count} members on device).",
                        "is_mitigating": False,
                    })

    # 2. Internal Shared IPs
    if "ip_id" in acc_sub.columns and (not evidence_type or evidence_type == "SHARED_IP"):
        ip_counts = acc_sub["ip_id"].value_counts()
        for ip_id, count in ip_counts[ip_counts > 1].items():
            if str(ip_id) == "nan":
                continue
            is_mitigating = count > 15
            shared_members = acc_sub[acc_sub["ip_id"] == ip_id]["account_id"].tolist()
            for i in range(len(shared_members)):
                for j in range(i + 1, len(shared_members)):
                    relationships.append({
                        "source_account": str(shared_members[i]),
                        "target_account": str(shared_members[j]),
                        "evidence_type": "SHARED_IP",
                        "evidence_strength": "WEAK" if is_mitigating else ("STRONG" if count <= 4 else "MODERATE"),
                        "shared_entity_id": str(ip_id),
                        "support_count": int(count),
                        "explanation": (
                            f"Shared IP {ip_id} across {count} cluster members. "
                            + ("High fanout: consistent with VPN/Wi-Fi." if is_mitigating else "Low fanout.")
                        ),
                        "is_mitigating": is_mitigating,
                    })

    # 3. Internal Shared Destinations
    tx_sub = df_tx[df_tx["account_id"].isin(members_set)]
    if not tx_sub.empty and "destination_id" in tx_sub.columns and (not evidence_type or evidence_type == "SHARED_DESTINATION"):
        dest_by_acc = tx_sub.groupby("destination_id")["account_id"].unique()
        for dest_id, dest_members in dest_by_acc.items():
            if str(dest_id) == "nan" or len(dest_members) < 2:
                continue
            dest_mem_list = list(dest_members)
            for i in range(len(dest_mem_list)):
                for j in range(i + 1, len(dest_mem_list)):
                    relationships.append({
                        "source_account": str(dest_mem_list[i]),
                        "target_account": str(dest_mem_list[j]),
                        "evidence_type": "SHARED_DESTINATION",
                        "evidence_strength": "STRONG" if len(dest_mem_list) <= 5 else "MODERATE",
                        "shared_entity_id": str(dest_id),
                        "support_count": len(dest_mem_list),
                        "explanation": f"Cluster accounts transferred funds to common destination {dest_id}.",
                        "is_mitigating": False,
                    })

    strength_rank = {"STRONG": 0, "MODERATE": 1, "WEAK": 2}

    # If no truncation requested, sort by strength and return all
    if not max_relationships or max_relationships <= 0 or len(relationships) <= max_relationships:
        relationships.sort(key=lambda r: strength_rank.get(r["evidence_strength"], 9))
        return relationships

    # Stratified selection across evidence types to prevent starvation
    by_type: dict[str, list[dict[str, Any]]] = {}
    for r in relationships:
        by_type.setdefault(r["evidence_type"], []).append(r)

    for t in by_type:
        by_type[t].sort(key=lambda x: strength_rank.get(x["evidence_strength"], 9))

    selected: list[dict[str, Any]] = []
    types = list(by_type.keys())
    idx = 0
    while len(selected) < max_relationships and any(len(by_type[t]) > idx for t in types):
        for t in types:
            if idx < len(by_type[t]) and len(selected) < max_relationships:
                selected.append(by_type[t][idx])
        idx += 1

    return selected


def compute_cluster_connectivity_metadata(
    member_accs: list[str],
    all_relationships: list[dict[str, Any]],
    displayed_relationships: list[dict[str, Any]],
    is_truncated: bool = False,
) -> dict[str, Any]:
    """
    Computes rigorous graph connectivity metrics across cluster accounts:
    - Connected components using NetworkX on complete relationships
    - Represented vs unrepresented accounts
    - Breakdown by evidence type
    """
    members_set = set(member_accs)
    G = nx.Graph()
    G.add_nodes_from(members_set)

    type_counts: dict[str, int] = {}
    for r in all_relationships:
        etype = r.get("evidence_type", "UNKNOWN")
        type_counts[etype] = type_counts.get(etype, 0) + 1
        src = r.get("source_account")
        tgt = r.get("target_account")
        if src in members_set and tgt in members_set:
            G.add_edge(src, tgt)

    comps = [sorted(list(c)) for c in nx.connected_components(G)]
    comps.sort(key=len, reverse=True)

    unrepresented = [a for a in member_accs if G.degree(a) == 0]
    represented = [a for a in member_accs if G.degree(a) > 0]

    displayed_accounts = set()
    for r in displayed_relationships:
        if r.get("source_account") in members_set:
            displayed_accounts.add(r["source_account"])
        if r.get("target_account") in members_set:
            displayed_accounts.add(r["target_account"])

    return {
        "total_relationships_count": len(all_relationships),
        "displayed_relationships_count": len(displayed_relationships),
        "relationships_by_type": type_counts,
        "total_accounts_count": len(member_accs),
        "represented_accounts_count": len(represented),
        "unrepresented_accounts_count": len(unrepresented),
        "unrepresented_accounts": sorted(unrepresented),
        "connected_components_count": len(comps),
        "largest_component_size": len(comps[0]) if comps else 0,
        "connected_components": comps[:10],
        "is_truncated": is_truncated,
        "displayed_accounts_count": len(displayed_accounts),
    }


def summarize_retrospective_cluster(
    cluster_id: str,
    max_relationships: Optional[int] = None,
    evidence_type: Optional[str] = None,
    include_evaluation_meta: bool = False,
) -> InvestigativeClusterSummary:
    """
    Summarizes a global 30-day Louvain cluster from graph_clusters.csv.
    Explicitly labeled as retrospective with analyst disclaimers.
    Returns complete internal relationships and graph connectivity metrics.
    """
    cache = InvestigationModelCache.get_instance()
    df_clusters = cache.df_clusters
    clean_id = str(cluster_id).strip()

    match = df_clusters[df_clusters["cluster_id"] == clean_id]
    if match.empty:
        raise KeyError(f"Cluster '{clean_id}' not found in graph clusters.")

    row = match.iloc[0]
    accounts_raw = str(row["accounts_list"]).split("|")
    member_accs = [str(a).strip() for a in accounts_raw]

    # Reconcile valid vs excluded members
    excluded = [a for a in member_accs if a in cache.excluded_accounts]
    valid_members = [a for a in member_accs if a not in cache.excluded_accounts]

    # Compute ML risk distribution
    probs = [cache.probabilities[a] for a in valid_members if a in cache.probabilities]
    if probs:
        p_mean = float(np.mean(probs))
        p_median = float(np.median(probs))
        p_max = float(np.max(probs))
        p_min = float(np.min(probs))
        high_risk_accs = [
            {"account_id": a, "calibrated_probability": round(cache.probabilities[a], 4), "is_high_risk": True}
            for a in valid_members
            if a in cache.probabilities and cache.probabilities[a] >= HIGH_RISK_THRESHOLD
        ]
        high_risk_accs.sort(key=lambda x: x["calibrated_probability"], reverse=True)
        high_risk_count = len(high_risk_accs)
        high_risk_ratio = high_risk_count / len(valid_members)
    else:
        p_mean = p_median = p_max = p_min = 0.0
        high_risk_accs = []
        high_risk_count = 0
        high_risk_ratio = 0.0

    # Temporal span & transaction statistics
    df_tx = cache.df_tx
    tx_sub = df_tx[df_tx["account_id"].isin(set(member_accs))] if not df_tx.empty else pd.DataFrame()
    if not tx_sub.empty:
        earliest_act = tx_sub["timestamp"].min()
        latest_act = tx_sub["timestamp"].max()
        total_tx = int(len(tx_sub))
        total_vol = float(tx_sub["amount"].sum())
    else:
        earliest_act = latest_act = "N/A"
        total_tx = 0
        total_vol = 0.0

    # Complete internal relationships & connectivity calculation
    all_rels = extract_cluster_internal_relationships(
        member_accs, cache.df_accounts, cache.df_tx, max_relationships=None
    )
    if max_relationships is not None or evidence_type is not None:
        top_rel = extract_cluster_internal_relationships(
            member_accs,
            cache.df_accounts,
            cache.df_tx,
            max_relationships=max_relationships,
            evidence_type=evidence_type,
        )
    else:
        top_rel = all_rels

    connectivity_meta = compute_cluster_connectivity_metadata(
        member_accs,
        all_rels,
        top_rel,
        is_truncated=(len(top_rel) < len(all_rels)),
    )

    # Optional evaluation meta (isolated ground truth)
    eval_meta = None
    if include_evaluation_meta:
        df_gt = cache.df_gt
        gt_sub = df_gt[df_gt["account_id"].isin(set(member_accs))]
        if not gt_sub.empty:
            ring_counts = gt_sub["ring_id"].value_counts().to_dict()
            archetypes = gt_sub["archetype"].value_counts().to_dict() if "archetype" in gt_sub.columns else {}
            attack_events_sum = int(gt_sub["future_attack_events"].sum()) if "future_attack_events" in gt_sub.columns else 0
            eval_meta = {
                "ground_truth_rings": ring_counts,
                "ground_truth_archetypes": archetypes,
                "total_future_attack_events": attack_events_sum,
                "true_positives_in_cluster": int((gt_sub["future_attack_events"] > 0).sum()) if "future_attack_events" in gt_sub.columns else 0,
            }

    disclaimer = (
        "GLOBAL_30_DAY_RETROSPECTIVE: This cluster was constructed globally across the entire 30-day "
        "dataset via Louvain community detection. It represents full retrospective activity and "
        "was NOT available as a point-in-time predictive feature during account scoring."
    )

    return InvestigativeClusterSummary(
        cluster_id=clean_id,
        cluster_mode="GLOBAL_30_DAY_RETROSPECTIVE",
        num_members=len(member_accs),
        member_account_ids=member_accs,
        excluded_members=excluded,
        ml_risk_distribution={
            "mean_probability": round(p_mean, 4),
            "median_probability": round(p_median, 4),
            "max_probability": round(p_max, 4),
            "min_probability": round(p_min, 4),
            "high_risk_count": high_risk_count,
            "high_risk_ratio": round(high_risk_ratio, 4),
            "decision_threshold": HIGH_RISK_THRESHOLD,
        },
        high_risk_members=high_risk_accs,
        top_relationships=top_rel,
        temporal_span={
            "earliest_activity": earliest_act,
            "latest_activity": latest_act,
            "total_transactions": total_tx,
            "total_volume": round(total_vol, 2),
        },
        disclaimer=disclaimer,
        evaluation_meta=eval_meta,
        connectivity_metadata=connectivity_meta,
    )


def summarize_point_in_time_community(
    focal_account_id: str,
    max_hops: int = 2,
    include_evaluation_meta: bool = False,
) -> InvestigativeClusterSummary:
    """
    Constructs and summarizes an observation-window-specific ego-community strictly bounded
    by t <= T_obs of the focal account.
    """
    cache = InvestigationModelCache.get_instance()
    clean_id = str(focal_account_id).strip()

    pit_comm = extract_point_in_time_community(
        clean_id,
        cache.df_accounts,
        cache.df_tx,
        df_gt=cache.df_gt,
        max_hops=max_hops,
    )

    member_accs = pit_comm["member_accounts"]
    excluded = [a for a in member_accs if a in cache.excluded_accounts]
    valid_members = [a for a in member_accs if a not in cache.excluded_accounts]

    # Model probabilities
    probs = [cache.probabilities[a] for a in valid_members if a in cache.probabilities]
    if probs:
        p_mean = float(np.mean(probs))
        p_median = float(np.median(probs))
        p_max = float(np.max(probs))
        p_min = float(np.min(probs))
        high_risk_accs = [
            {"account_id": a, "calibrated_probability": round(cache.probabilities[a], 4), "is_high_risk": True}
            for a in valid_members
            if a in cache.probabilities and cache.probabilities[a] >= HIGH_RISK_THRESHOLD
        ]
        high_risk_accs.sort(key=lambda x: x["calibrated_probability"], reverse=True)
        high_risk_count = len(high_risk_accs)
        high_risk_ratio = high_risk_count / len(valid_members)
    else:
        p_mean = p_median = p_max = p_min = 0.0
        high_risk_accs = []
        high_risk_count = 0
        high_risk_ratio = 0.0

    # Temporal span strictly within observation cutoff
    obs_cutoff_str = pit_comm["observation_cutoff"]
    cutoff_dt = pd.to_datetime(obs_cutoff_str)
    df_tx = cache.df_tx
    if not df_tx.empty:
        tx_sub = df_tx[(df_tx["account_id"].isin(set(member_accs))) & (df_tx["timestamp_dt"] <= cutoff_dt)]
        if not tx_sub.empty:
            earliest_act = tx_sub["timestamp"].min()
            latest_act = tx_sub["timestamp"].max()
            total_tx = int(len(tx_sub))
            total_vol = float(tx_sub["amount"].sum())
        else:
            earliest_act = latest_act = "N/A"
            total_tx = 0
            total_vol = 0.0
    else:
        earliest_act = latest_act = "N/A"
        total_tx = 0
        total_vol = 0.0

    # Evaluation meta if requested
    eval_meta = None
    if include_evaluation_meta:
        df_gt = cache.df_gt
        gt_sub = df_gt[df_gt["account_id"].isin(set(member_accs))]
        if not gt_sub.empty:
            ring_counts = gt_sub["ring_id"].value_counts().to_dict()
            archetypes = gt_sub["archetype"].value_counts().to_dict() if "archetype" in gt_sub.columns else {}
            eval_meta = {
                "ground_truth_rings": ring_counts,
                "ground_truth_archetypes": archetypes,
                "true_positives_in_community": int((gt_sub["future_attack_events"] > 0).sum()) if "future_attack_events" in gt_sub.columns else 0,
            }

    connectivity_meta = compute_cluster_connectivity_metadata(
        member_accs,
        pit_comm["relationships"],
        pit_comm["relationships"],
        is_truncated=False,
    )

    return InvestigativeClusterSummary(
        cluster_id=f"PIT_COMMUNITY_{clean_id}",
        cluster_mode="POINT_IN_TIME_OBSERVATION_WINDOW",
        num_members=len(member_accs),
        member_account_ids=member_accs,
        excluded_members=excluded,
        ml_risk_distribution={
            "mean_probability": round(p_mean, 4),
            "median_probability": round(p_median, 4),
            "max_probability": round(p_max, 4),
            "min_probability": round(p_min, 4),
            "high_risk_count": high_risk_count,
            "high_risk_ratio": round(high_risk_ratio, 4),
            "decision_threshold": HIGH_RISK_THRESHOLD,
        },
        high_risk_members=high_risk_accs,
        top_relationships=pit_comm["relationships"],
        temporal_span={
            "observation_cutoff": obs_cutoff_str,
            "earliest_activity": earliest_act,
            "latest_activity": latest_act,
            "total_transactions": total_tx,
            "total_volume": round(total_vol, 2),
        },
        disclaimer=None,
        evaluation_meta=eval_meta,
        connectivity_metadata=connectivity_meta,
    )


def list_investigative_clusters(
    limit: int = 50,
    sort_by: str = "high_risk_count",
) -> list[dict[str, Any]]:
    """
    Lists global retrospective clusters annotated with CatBoost baseline risk statistics.
    Sorts by high_risk_count, high_risk_ratio, or num_members.
    """
    cache = InvestigationModelCache.get_instance()
    df_clusters = cache.df_clusters
    probs = cache.probabilities

    cluster_summaries = []
    for _, row in df_clusters.iterrows():
        c_id = str(row["cluster_id"]).strip()
        members = [str(a).strip() for a in str(row["accounts_list"]).split("|")]
        valid_members = [a for a in members if a not in cache.excluded_accounts]

        c_probs = [probs[a] for a in valid_members if a in probs]
        if c_probs:
            mean_p = float(np.mean(c_probs))
            max_p = float(np.max(c_probs))
            high_count = sum(1 for p in c_probs if p >= HIGH_RISK_THRESHOLD)
            high_ratio = high_count / len(valid_members)
        else:
            mean_p = max_p = high_ratio = 0.0
            high_count = 0

        cluster_summaries.append({
            "cluster_id": c_id,
            "num_members": len(members),
            "valid_predictive_members": len(valid_members),
            "excluded_members_count": len(members) - len(valid_members),
            "mean_calibrated_probability": round(mean_p, 4),
            "max_calibrated_probability": round(max_p, 4),
            "high_risk_count": high_count,
            "high_risk_ratio": round(high_ratio, 4),
            "graph_density": float(row.get("graph_density", 0.0)),
            "average_edge_strength": float(row.get("average_edge_strength", 0.0)),
        })

    if sort_by == "high_risk_ratio":
        cluster_summaries.sort(key=lambda c: (c["high_risk_ratio"], c["high_risk_count"]), reverse=True)
    elif sort_by == "num_members":
        cluster_summaries.sort(key=lambda c: c["num_members"], reverse=True)
    else:  # default: high_risk_count
        cluster_summaries.sort(key=lambda c: (c["high_risk_count"], c["mean_calibrated_probability"]), reverse=True)

    return cluster_summaries[:limit]
