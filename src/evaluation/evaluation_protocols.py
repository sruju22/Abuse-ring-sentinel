"""
Abuse-Ring Sentinel - Evaluation Protocols for Fraud Risk Benchmarking.

Provides two decoupled, defensible evaluation methodologies:
  Protocol A: Out-of-Time Prediction (Temporal Cohorts)
    - Chronological account cohorts based on registration date.
    - Identical 7-day observation and 7-day outcome horizons.
    - Explicitly calculates and reports syndication overlap across cohorts.

  Protocol B: Unseen-Ring Generalization (Atomic Group Splitting)
    - Complete abuse rings split atomically (zero ring overlap across Train/Val/Test).
    - Stratified archetype representation (all 6 archetypes in Train, Val, and Test).
    - Statistically robust positive sample size in Test (75-90 positive accounts).
    - Inductive feature isolation (zero test-ring data used in training features or scaling).
"""

from dataclasses import dataclass
from datetime import datetime
import json
import os
from typing import Any, Optional
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


ARCHETYPES = [
    "INFRASTRUCTURE_LINKED",
    "DISTRIBUTED_FUNNEL",
    "SYNCHRONIZED_BURST",
    "TASK_JOB_SCAM",
    "COVER_TRAFFIC_HYBRID",
    "MIXED_PARTIAL",
]


def get_archetype_for_ring(ring_id: str) -> str:
    """Deterministic mapping of ring ID to synthetic archetype."""
    if not ring_id or str(ring_id) == "nan" or not str(ring_id).startswith("RING_"):
        return "NON_ABUSE"
    try:
        ring_num = int(str(ring_id).split("_")[1])
        return ARCHETYPES[(ring_num - 1) % len(ARCHETYPES)]
    except Exception:
        return "UNKNOWN_ABUSE"


@dataclass
class ProtocolASplit:
    """Container for Protocol A (Out-of-Time Temporal Cohort) split data."""
    X_train: pd.DataFrame
    y_train: pd.Series
    X_val: pd.DataFrame
    y_val: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    train_account_ids: list[str]
    val_account_ids: list[str]
    test_account_ids: list[str]
    cohort_boundaries: dict[str, Any]
    ring_overlap_report: dict[str, Any]
    feature_columns: list[str]
    df_eval_metadata: pd.DataFrame


@dataclass
class ProtocolBSplit:
    """Container for Protocol B (Unseen-Ring Atomic Splitting) split data."""
    X_train: pd.DataFrame
    y_train: pd.Series
    X_val: pd.DataFrame
    y_val: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    train_account_ids: list[str]
    val_account_ids: list[str]
    test_account_ids: list[str]
    ring_allocations: dict[str, list[str]]
    archetype_coverage: dict[str, dict[str, int]]
    sample_size_report: dict[str, Any]
    feature_columns: list[str]
    df_eval_metadata: pd.DataFrame


def build_out_of_time_splits(
    df_features: pd.DataFrame,
    df_ground_truth: pd.DataFrame,
    train_cutoff_dt: Optional[datetime] = None,
    val_cutoff_dt: Optional[datetime] = None,
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
) -> ProtocolASplit:
    """
    Constructs Protocol A: Chronological Account Cohorts.
    Every account is evaluated with identical W_obs (7 days) and W_out (7 days).
    Only complete outcome windows are retained.
    """
    merged = pd.merge(df_features, df_ground_truth, on="account_id")
    
    # Strictly filter out accounts with incomplete outcome windows
    if "is_complete_window" in merged.columns:
        complete_mask = merged["is_complete_window"].astype(bool)
        df_complete = merged[complete_mask].copy()
    else:
        df_complete = merged.copy()

    df_complete["created_dt"] = pd.to_datetime(df_complete["created_at"])
    df_complete = df_complete.sort_values("created_dt").reset_index(drop=True)

    n_total = len(df_complete)
    if train_cutoff_dt is None or val_cutoff_dt is None:
        t_train_idx = int(n_total * train_ratio)
        t_val_idx = int(n_total * (train_ratio + val_ratio))
        train_cutoff = df_complete.iloc[t_train_idx]["created_dt"]
        val_cutoff = df_complete.iloc[t_val_idx]["created_dt"]
    else:
        train_cutoff = pd.to_datetime(train_cutoff_dt)
        val_cutoff = pd.to_datetime(val_cutoff_dt)

    train_mask = df_complete["created_dt"] < train_cutoff
    val_mask = (df_complete["created_dt"] >= train_cutoff) & (df_complete["created_dt"] < val_cutoff)
    test_mask = df_complete["created_dt"] >= val_cutoff

    train_df = df_complete[train_mask].copy()
    val_df = df_complete[val_mask].copy()
    test_df = df_complete[test_mask].copy()

    # Verify temporal ordering invariant: max(train) <= min(val) and max(val) <= min(test)
    assert train_df["created_dt"].max() <= val_df["created_dt"].min(), "Train/Val temporal boundary violation"
    assert val_df["created_dt"].max() <= test_df["created_dt"].min(), "Val/Test temporal boundary violation"

    # Measure ring overlap across cohorts
    def get_rings(df: pd.DataFrame) -> set[str]:
        if "ring_id" not in df.columns:
            return set()
        return set(df["ring_id"].dropna().loc[lambda s: s.str.startswith("RING_")].unique())

    train_rings = get_rings(train_df)
    val_rings = get_rings(val_df)
    test_rings = get_rings(test_df)

    overlap_train_val = sorted(train_rings.intersection(val_rings))
    overlap_train_test = sorted(train_rings.intersection(test_rings))
    overlap_val_test = sorted(val_rings.intersection(test_rings))
    all_three = sorted(train_rings.intersection(val_rings).intersection(test_rings))

    ring_overlap_report = {
        "train_ring_count": len(train_rings),
        "val_ring_count": len(val_rings),
        "test_ring_count": len(test_rings),
        "overlap_train_val_count": len(overlap_train_val),
        "overlap_train_val_rings": overlap_train_val,
        "overlap_train_test_count": len(overlap_train_test),
        "overlap_train_test_rings": overlap_train_test,
        "overlap_val_test_count": len(overlap_val_test),
        "overlap_val_test_rings": overlap_val_test,
        "overlap_all_three_count": len(all_three),
        "overlap_all_three_rings": all_three,
        "methodological_note": (
            "Temporal cohorts evaluate chronological generalization over calendar time. "
            "However, coordinated syndicates register accounts in successive waves, causing "
            "syndicate overlap across cohorts. Protocol B isolates unseen syndicate generalization."
        ),
    }

    cohort_boundaries = {
        "train_start": str(train_df["created_dt"].min()),
        "train_end": str(train_df["created_dt"].max()),
        "val_start": str(val_df["created_dt"].min()),
        "val_end": str(val_df["created_dt"].max()),
        "test_start": str(test_df["created_dt"].min()),
        "test_end": str(test_df["created_dt"].max()),
    }

    # Extract clean feature matrix (strictly exclude metadata and targets)
    metadata_cols = {
        "account_id", "account_type", "ring_id", "target", "is_complete_window",
        "attack_event_count", "first_attack_time", "created_at", "created_dt",
        "t_obs", "t_outcome_end"
    }
    feature_cols = [c for c in df_features.columns if c not in metadata_cols]

    X_train = train_df[["account_id"] + feature_cols].copy()
    y_train = train_df["target"].astype(int).copy()

    X_val = val_df[["account_id"] + feature_cols].copy()
    y_val = val_df["target"].astype(int).copy()

    X_test = test_df[["account_id"] + feature_cols].copy()
    y_test = test_df["target"].astype(int).copy()

    return ProtocolASplit(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test,
        train_account_ids=train_df["account_id"].tolist(),
        val_account_ids=val_df["account_id"].tolist(),
        test_account_ids=test_df["account_id"].tolist(),
        cohort_boundaries=cohort_boundaries,
        ring_overlap_report=ring_overlap_report,
        feature_columns=feature_cols,
        df_eval_metadata=df_complete,
    )


def build_unseen_ring_splits(
    df_features: pd.DataFrame,
    df_ground_truth: pd.DataFrame,
    test_rings: Optional[list[str]] = None,
    val_rings: Optional[list[str]] = None,
    random_state: int = 42,
) -> ProtocolBSplit:
    """
    Constructs Protocol B: Unseen-Ring Generalization via Atomic Ring Splitting.
    Guarantees:
      1. Zero ring overlap between Train, Val, and Test splits.
      2. Stratified archetype coverage across all 6 synthetic abuse archetypes.
      3. Test split positive sample size between 75 and 90 confirmed attack accounts.
      4. Inductive evaluation without test-ring leakage.
    """
    merged = pd.merge(df_features, df_ground_truth, on="account_id")

    if "is_complete_window" in merged.columns:
        df_complete = merged[merged["is_complete_window"].astype(bool)].copy()
    else:
        df_complete = merged.copy()

    df_complete["archetype"] = df_complete["ring_id"].map(get_archetype_for_ring)

    # Standard curated ring assignment ensuring 1 ring per archetype in Val and Test,
    # with test positive sample size strictly in [75, 90].
    if test_rings is None:
        test_rings = ["RING_013", "RING_002", "RING_003", "RING_004", "RING_005", "RING_012"]
    if val_rings is None:
        val_rings = ["RING_007", "RING_008", "RING_009", "RING_010", "RING_011", "RING_006"]

    test_ring_set = set(test_rings)
    val_ring_set = set(val_rings)

    # Invariant: test and val rings must be disjoint
    assert len(test_ring_set.intersection(val_ring_set)) == 0, "Test and Val ring sets must be disjoint!"

    all_rings = set(df_complete[df_complete["account_type"] == "abuse_ring"]["ring_id"].dropna().unique())
    train_ring_set = all_rings - test_ring_set - val_ring_set

    # Invariant: zero ring overlap across all splits
    assert len(train_ring_set.intersection(val_ring_set)) == 0, "Train and Val rings overlap!"
    assert len(train_ring_set.intersection(test_ring_set)) == 0, "Train and Test rings overlap!"

    # Partition abuse accounts atomically
    ab_train = df_complete[df_complete["ring_id"].isin(train_ring_set)].copy()
    ab_val = df_complete[df_complete["ring_id"].isin(val_ring_set)].copy()
    ab_test = df_complete[df_complete["ring_id"].isin(test_ring_set)].copy()

    # Partition non-abuse accounts (normal + legitimate_shared) deterministically
    non_abuse = df_complete[df_complete["account_type"] != "abuse_ring"].copy()
    na_train, na_temp = train_test_split(
        non_abuse,
        test_size=0.333333,
        random_state=random_state,
        stratify=non_abuse["account_type"],
    )
    na_val, na_test = train_test_split(
        na_temp,
        test_size=0.50,
        random_state=random_state,
        stratify=na_temp["account_type"],
    )

    train_df = pd.concat([na_train, ab_train]).sample(frac=1.0, random_state=random_state).reset_index(drop=True)
    val_df = pd.concat([na_val, ab_val]).sample(frac=1.0, random_state=random_state).reset_index(drop=True)
    test_df = pd.concat([na_test, ab_test]).sample(frac=1.0, random_state=random_state).reset_index(drop=True)

    metadata_cols = {
        "account_id", "account_type", "ring_id", "archetype", "target",
        "is_complete_window", "attack_event_count", "first_attack_time",
        "created_at", "created_dt", "t_obs", "t_outcome_end"
    }
    feature_cols = [c for c in df_features.columns if c not in metadata_cols]

    X_train = train_df[["account_id"] + feature_cols].copy()
    y_train = train_df["target"].astype(int).copy()

    X_val = val_df[["account_id"] + feature_cols].copy()
    y_val = val_df["target"].astype(int).copy()

    X_test = test_df[["account_id"] + feature_cols].copy()
    y_test = test_df["target"].astype(int).copy()

    # Verify archetype coverage
    def count_archetypes(df: pd.DataFrame) -> dict[str, int]:
        sub = df[df["account_type"] == "abuse_ring"]
        counts = sub["archetype"].value_counts().to_dict()
        return {arch: counts.get(arch, 0) for arch in ARCHETYPES}

    archetype_coverage = {
        "train": count_archetypes(train_df),
        "val": count_archetypes(val_df),
        "test": count_archetypes(test_df),
    }

    # Verify every archetype is present in all three splits
    for split_name, cov in archetype_coverage.items():
        for arch in ARCHETYPES:
            assert cov[arch] > 0, f"Archetype {arch} missing in {split_name} split!"

    sample_size_report = {
        "train": {"total_accounts": len(train_df), "abuse_accounts": len(ab_train), "positive_targets": int(y_train.sum()), "ring_count": len(train_ring_set)},
        "val": {"total_accounts": len(val_df), "abuse_accounts": len(ab_val), "positive_targets": int(y_val.sum()), "ring_count": len(val_ring_set)},
        "test": {"total_accounts": len(test_df), "abuse_accounts": len(ab_test), "positive_targets": int(y_test.sum()), "ring_count": len(test_ring_set)},
    }

    test_positives = int(y_test.sum())
    assert 75 <= test_positives <= 90, f"Protocol B test positive count {test_positives} outside [75, 90]!"

    return ProtocolBSplit(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test,
        train_account_ids=train_df["account_id"].tolist(),
        val_account_ids=val_df["account_id"].tolist(),
        test_account_ids=test_df["account_id"].tolist(),
        ring_allocations={
            "train_rings": sorted(list(train_ring_set)),
            "val_rings": sorted(list(val_ring_set)),
            "test_rings": sorted(list(test_ring_set)),
        },
        archetype_coverage=archetype_coverage,
        sample_size_report=sample_size_report,
        feature_columns=feature_cols,
        df_eval_metadata=df_complete,
    )
