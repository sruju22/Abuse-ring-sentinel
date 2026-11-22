"""
Abuse-Ring Sentinel - Scalable Machine Learning Training Pipeline.

Trains baseline models (Logistic Regression, Random Forest) for account-level
abuse-risk detection using engineered features. Performs reproducible stratified
train/val/test splitting, threshold selection on validation data based on a
synthetic cost-sensitive risk objective, and persists models and artifacts.

Strictly enforces target label isolation (no ground-truth features).
"""

import json
import os
import pickle
import sys
from typing import Any, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


from src.evaluation.evaluation_protocols import (
    build_out_of_time_splits,
    build_unseen_ring_splits,
    ProtocolASplit,
    ProtocolBSplit,
)

# Configurable Synthetic Cost Assumptions (for threshold optimization)
# NOTE: These are synthetic demonstration values, not real-world Razorpay economics.
DEFAULT_COST_FP = 15.0  # Synthetic analyst investigation cost per false alarm
DEFAULT_COST_FN = 100.0  # Synthetic loss per undetected abuse account


def load_and_prepare_dataset(
    features_path: str = "data/processed/account_features_pit.csv",
    ground_truth_path: str = "data/processed/ground_truth_pit.csv",
    enforce_pit: bool = False,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """
    Loads features and ground-truth metadata, constructs binary target,
    and strictly isolates features from ground truth.

    Enforces refusal of unpartitioned lifetime features when enforce_pit=True.
    """
    if enforce_pit and os.path.basename(features_path) == "account_features.csv":
        raise ValueError(
            "Evaluation Integrity Violation: Refusing to train on unpartitioned lifetime features 'account_features.csv'. "
            "Please use 'data/processed/account_features_pit.csv' and 'data/processed/ground_truth_pit.csv' "
            "for genuine Point-in-Time, leakage-free evaluation."
        )

    if not os.path.exists(features_path):
        raise FileNotFoundError(f"Features file not found at: {features_path}")
    if not os.path.exists(ground_truth_path):
        raise FileNotFoundError(f"Ground truth file not found at: {ground_truth_path}")

    df_feats = pd.read_csv(features_path)
    df_gt = pd.read_csv(ground_truth_path)

    # Merge ONLY to extract the label
    merge_cols = ["account_id"]
    for c in ["account_type", "ring_id", "target", "is_complete_window"]:
        if c in df_gt.columns:
            merge_cols.append(c)

    df_merged = df_feats.merge(df_gt[merge_cols], on="account_id")

    if "target" in df_merged.columns:
        y = df_merged["target"].astype(int)
    else:
        # Construct binary target: 1 for abuse_ring, 0 for legitimate_shared and normal
        y = (df_merged["account_type"] == "abuse_ring").astype(int)

    # Feature columns (strictly excluding account_id and all ground truth labels)
    forbidden_cols = {
        "account_id", "account_type", "ring_id", "label", "target",
        "is_complete_window", "attack_event_count", "first_attack_time",
        "created_at", "created_dt", "t_obs", "t_outcome_end"
    }
    feature_cols = [c for c in df_feats.columns if c not in forbidden_cols]

    # Verify no ground truth leaked into feature columns
    for col in feature_cols:
        assert col in df_feats.columns, f"Unknown column {col}"
        assert col not in ["account_type", "ring_id", "target"], f"Leaked target column: {col}"

    X = df_merged[["account_id"] + feature_cols].copy()
    return X, y, feature_cols


def load_and_prepare_pit_dataset(
    features_path: str = "data/processed/account_features_pit.csv",
    ground_truth_path: str = "data/processed/ground_truth_pit.csv",
) -> tuple[pd.DataFrame, pd.Series, list[str], pd.DataFrame]:
    """
    Loads Point-in-Time features and targets, enforces complete observation windows,
    and returns isolated X, y, feature_cols, and ground truth dataframe.
    """
    if not os.path.exists(features_path):
        raise FileNotFoundError(f"PIT features file not found at: {features_path}")
    if not os.path.exists(ground_truth_path):
        raise FileNotFoundError(f"PIT ground truth file not found at: {ground_truth_path}")

    df_feats = pd.read_csv(features_path)
    df_gt = pd.read_csv(ground_truth_path)

    # Exclude accounts with incomplete observation/outcome windows
    if "is_complete_window" in df_gt.columns:
        complete_ids = set(df_gt[df_gt["is_complete_window"].astype(bool)]["account_id"].unique())
        df_feats = df_feats[df_feats["account_id"].isin(complete_ids)].reset_index(drop=True)
        df_gt = df_gt[df_gt["account_id"].isin(complete_ids)].reset_index(drop=True)

    df_merged = pd.merge(df_feats, df_gt[["account_id", "target"]], on="account_id")

    forbidden_cols = {
        "account_id", "account_type", "ring_id", "label", "target",
        "is_complete_window", "attack_event_count", "first_attack_time",
        "created_at", "created_dt", "t_obs", "t_outcome_end"
    }
    feature_cols = [c for c in df_feats.columns if c not in forbidden_cols]

    X = df_merged[["account_id"] + feature_cols].copy()
    y = df_merged["target"].astype(int).copy()

    return X, y, feature_cols, df_gt


def split_data_temporal(
    X: pd.DataFrame,
    y: pd.Series,
    df_accounts: Optional[pd.DataFrame] = None,
    train_size: float = 0.60,
    val_size: float = 0.20,
    test_size: float = 0.20,
) -> dict[str, Any]:
    """
    Performs reproducible chronological (temporal) train / validation / test splitting
    based on account registration timestamp (created_at).

    Ensures zero future-to-past leakage by maintaining strict chronological boundaries:
      Train (earliest ~60%) < Validation (middle ~20%) < Test OOT (latest ~20%).
    """
    assert abs((train_size + val_size + test_size) - 1.0) < 1e-6, "Split sizes must sum to 1.0"

    if df_accounts is None:
        accounts_path = "data/raw/accounts.csv"
        if not os.path.exists(accounts_path):
            raise FileNotFoundError(f"Accounts file not found at: {accounts_path}")
        df_accounts = pd.read_csv(accounts_path)

    acc_time = df_accounts[["account_id", "created_at"]].copy()
    acc_time["created_at_dt"] = pd.to_datetime(acc_time["created_at"])

    # Merge with X and y preserving integrity
    df_merged = X.copy()
    df_merged["_target"] = y.values
    df_merged = df_merged.merge(acc_time[["account_id", "created_at_dt"]], on="account_id")

    # Sort chronologically by registration timestamp, break ties deterministically with account_id
    df_sorted = df_merged.sort_values(["created_at_dt", "account_id"]).reset_index(drop=True)

    n_total = len(df_sorted)
    idx_train = int(n_total * train_size)
    idx_val = int(n_total * (train_size + val_size))

    train_df = df_sorted.iloc[:idx_train].copy()
    val_df = df_sorted.iloc[idx_train:idx_val].copy()
    test_df = df_sorted.iloc[idx_val:].copy()

    feature_cols = [c for c in X.columns if c not in ["account_id", "_target", "created_at_dt"]]

    X_train = train_df[["account_id"] + feature_cols]
    y_train = train_df["_target"]

    X_val = val_df[["account_id"] + feature_cols]
    y_val = val_df["_target"]

    X_test = test_df[["account_id"] + feature_cols]
    y_test = test_df["_target"]

    split_meta = {
        "strategy": "temporal",
        "train_time_range": [
            train_df["created_at_dt"].min().strftime("%Y-%m-%d %H:%M:%S"),
            train_df["created_at_dt"].max().strftime("%Y-%m-%d %H:%M:%S"),
        ],
        "val_time_range": [
            val_df["created_at_dt"].min().strftime("%Y-%m-%d %H:%M:%S"),
            val_df["created_at_dt"].max().strftime("%Y-%m-%d %H:%M:%S"),
        ],
        "test_time_range": [
            test_df["created_at_dt"].min().strftime("%Y-%m-%d %H:%M:%S"),
            test_df["created_at_dt"].max().strftime("%Y-%m-%d %H:%M:%S"),
        ],
        "train_size": len(train_df),
        "val_size": len(val_df),
        "test_size": len(test_df),
        "train_abuse_count": int(y_train.sum()),
        "val_abuse_count": int(y_val.sum()),
        "test_abuse_count": int(y_test.sum()),
    }

    return {
        "X_train": X_train,
        "y_train": y_train,
        "X_val": X_val,
        "y_val": y_val,
        "X_test": X_test,
        "y_test": y_test,
        "metadata": split_meta,
    }


def split_data_stratified(
    X: pd.DataFrame,
    y: pd.Series,
    train_size: float = 0.60,
    val_size: float = 0.20,
    test_size: float = 0.20,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Performs reproducible stratified train / validation / test splitting.
    """
    assert abs((train_size + val_size + test_size) - 1.0) < 1e-6, "Split sizes must sum to 1.0"

    # Step 1: Split train vs (val + test)
    val_test_ratio = val_size + test_size
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y,
        test_size=val_test_ratio,
        stratify=y,
        random_state=random_state,
    )

    # Step 2: Split temp into val and test
    val_rel_ratio = val_size / val_test_ratio
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp,
        test_size=(1.0 - val_rel_ratio),
        stratify=y_temp,
        random_state=random_state,
    )

    return {
        "X_train": X_train,
        "y_train": y_train,
        "X_val": X_val,
        "y_val": y_val,
        "X_test": X_test,
        "y_test": y_test,
    }


def train_models(
    X_train_features: pd.DataFrame,
    y_train: pd.Series,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Fits Logistic Regression (with StandardScaler) and Random Forest models.
    """
    # 1. Logistic Regression Baseline
    lr_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(class_weight="balanced", random_state=random_state, max_iter=1000)),
    ])
    lr_pipe.fit(X_train_features, y_train)

    # 2. Random Forest Comparison
    rf_clf = RandomForestClassifier(
        n_estimators=150,
        max_depth=8,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
    rf_clf.fit(X_train_features, y_train)

    return {
        "logistic_regression": lr_pipe,
        "random_forest": rf_clf,
    }


def optimize_threshold_on_val(
    y_val: np.ndarray,
    y_val_probs: np.ndarray,
    cost_fp: float = DEFAULT_COST_FP,
    cost_fn: float = DEFAULT_COST_FN,
    metric_objective: str = "min_cost",  # 'min_cost' or 'max_f1'
) -> tuple[float, dict[str, Any]]:
    """
    Finds the optimal probability threshold on the validation set based on
    a cost-sensitive risk objective or F1 maximization.
    """
    thresholds = np.linspace(0.02, 0.98, 97)
    best_thresh = 0.50
    best_cost = float("inf")
    best_f1 = -1.0
    records = []

    for t in thresholds:
        y_pred = (y_val_probs >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_val, y_pred, labels=[0, 1]).ravel()
        cost = (fp * cost_fp) + (fn * cost_fn)
        f1 = f1_score(y_val, y_pred, zero_division=0)
        prec = precision_score(y_val, y_pred, zero_division=0)
        rec = recall_score(y_val, y_pred, zero_division=0)

        records.append({
            "threshold": float(round(t, 2)),
            "cost": float(cost),
            "f1": float(round(f1, 4)),
            "precision": float(round(prec, 4)),
            "recall": float(round(rec, 4)),
            "fp": int(fp),
            "fn": int(fn),
        })

        if metric_objective == "min_cost":
            if cost < best_cost:
                best_cost = cost
                best_thresh = float(round(t, 2))
        elif metric_objective == "max_f1":
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = float(round(t, 2))

    return best_thresh, {"best_cost": best_cost, "best_threshold": best_thresh, "curve": records}


def run_training_pipeline(
    features_path: str = "data/processed/account_features_pit.csv",
    ground_truth_path: str = "data/processed/ground_truth_pit.csv",
    models_dir: str = "models",
    output_dir: str = "data/processed/model_results",
    split_strategy: str = "protocol_b",  # 'protocol_b', 'protocol_a', 'temporal', or 'stratified'
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Executes end-to-end training and validation threshold freezing pipeline.
    Defaults to Protocol B (Unseen-Ring Generalization) on Point-in-Time features.
    """
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    if split_strategy in ["protocol_b", "protocol_a"]:
        if os.path.basename(features_path) == "account_features.csv":
            raise ValueError(
                "Evaluation Integrity Violation: Refusing to train on unpartitioned lifetime features 'account_features.csv'. "
                "Point-in-time features ('account_features_pit.csv') are required for defensible protocol evaluation."
            )
        df_feats = pd.read_csv(features_path)
        df_gt = pd.read_csv(ground_truth_path)
        if split_strategy == "protocol_b":
            split_obj = build_unseen_ring_splits(df_feats, df_gt, random_state=random_state)
        else:
            split_obj = build_out_of_time_splits(df_feats, df_gt)

        X_train, y_train = split_obj.X_train, split_obj.y_train
        X_val, y_val = split_obj.X_val, split_obj.y_val
        X_test, y_test = split_obj.X_test, split_obj.y_test
        feature_cols = split_obj.feature_columns
        splits = {
            "X_train": X_train, "y_train": y_train,
            "X_val": X_val, "y_val": y_val,
            "X_test": X_test, "y_test": y_test,
            "split_obj": split_obj,
        }
    else:
        # 1. Load data
        X, y, feature_cols = load_and_prepare_dataset(features_path, ground_truth_path, allow_legacy_lifetime=True)

        # 2. Split data according to requested strategy
        if split_strategy == "temporal":
            splits = split_data_temporal(X, y)
        elif split_strategy == "stratified":
            splits = split_data_stratified(X, y, random_state=random_state)
        else:
            raise ValueError(f"Unknown split_strategy '{split_strategy}'. Choose 'protocol_b', 'protocol_a', 'temporal', or 'stratified'.")

        X_train, y_train = splits["X_train"], splits["y_train"]
        X_val, y_val = splits["X_val"], splits["y_val"]
        X_test, y_test = splits["X_test"], splits["y_test"]

    # Extract feature matrices (dropping account_id)
    X_train_mat = X_train[feature_cols]
    X_val_mat = X_val[feature_cols]

    # 3. Train models strictly on training split
    models = train_models(X_train_mat, y_train, random_state=random_state)

    # 4. Tune and freeze thresholds exclusively on Validation Set
    frozen_thresholds = {}
    val_summaries = {}

    for name, model in models.items():
        val_probs = model.predict_proba(X_val_mat)[:, 1]
        best_thresh, opt_res = optimize_threshold_on_val(
            y_val.values, val_probs, cost_fp=DEFAULT_COST_FP, cost_fn=DEFAULT_COST_FN, metric_objective="min_cost"
        )
        frozen_thresholds[name] = best_thresh
        val_summaries[name] = opt_res

        # Save model artifact
        model_file = os.path.join(models_dir, f"{name}.joblib")
        joblib.dump(model, model_file)

    # Save Random Forest feature importances
    rf_model = models["random_forest"]
    rf_importances = pd.DataFrame({
        "feature": feature_cols,
        "importance": rf_model.feature_importances_,
    }).sort_values("importance", ascending=False)
    rf_importances.to_csv(os.path.join(output_dir, "feature_importance.csv"), index=False)

    # Save Logistic Regression standardized coefficients
    lr_pipe = models["logistic_regression"]
    lr_coefs = lr_pipe.named_steps["clf"].coef_[0]
    lr_importance_df = pd.DataFrame({
        "feature": feature_cols,
        "coefficient": lr_coefs,
        "abs_magnitude": np.abs(lr_coefs),
    }).sort_values("abs_magnitude", ascending=False)
    lr_importance_df.to_csv(os.path.join(output_dir, "logistic_regression_coefficients.csv"), index=False)

    # Save split indices / metadata for exact evaluation
    splits_meta = {
        "split_strategy": split_strategy,
        "train_account_ids": X_train["account_id"].tolist(),
        "val_account_ids": X_val["account_id"].tolist(),
        "test_account_ids": X_test["account_id"].tolist(),
        "feature_columns": feature_cols,
        "frozen_thresholds": frozen_thresholds,
        "synthetic_costs": {"cost_fp": DEFAULT_COST_FP, "cost_fn": DEFAULT_COST_FN},
        "class_balance": {
            "train": {"total": len(X_train), "abuse": int(y_train.sum()), "abuse_pct": round(float(y_train.mean()) * 100, 2)},
            "val": {"total": len(X_val), "abuse": int(y_val.sum()), "abuse_pct": round(float(y_val.mean()) * 100, 2)},
            "test": {"total": len(X_test), "abuse": int(y_test.sum()), "abuse_pct": round(float(y_test.mean()) * 100, 2)},
        },
    }
    if "metadata" in splits:
        splits_meta["temporal_metadata"] = splits["metadata"]
    if "split_obj" in splits:
        obj = splits["split_obj"]
        if hasattr(obj, "ring_allocations"):
            splits_meta["ring_allocations"] = obj.ring_allocations
            splits_meta["archetype_coverage"] = obj.archetype_coverage
            splits_meta["sample_size_report"] = obj.sample_size_report
        if hasattr(obj, "ring_overlap_report"):
            splits_meta["ring_overlap_report"] = obj.ring_overlap_report
            splits_meta["cohort_boundaries"] = obj.cohort_boundaries

    with open(os.path.join(output_dir, "split_and_threshold_meta.json"), "w") as f:
        json.dump(splits_meta, f, indent=2)

    return {
        "models": models,
        "splits": splits,
        "feature_cols": feature_cols,
        "frozen_thresholds": frozen_thresholds,
        "val_summaries": val_summaries,
    }


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("      ABUSE-RING SENTINEL - ML TRAINING & THRESHOLD TUNING")
    print("=" * 70)
    results = run_training_pipeline()
    print(f"Total Features Used: {len(results['feature_cols'])}")
    print(f"Train Set Size     : {len(results['splits']['X_train']):,} (Abuse: {results['splits']['y_train'].sum()})")
    print(f"Val Set Size       : {len(results['splits']['X_val']):,} (Abuse: {results['splits']['y_val'].sum()})")
    print(f"Test Set Size      : {len(results['splits']['X_test']):,} (Abuse: {results['splits']['y_test'].sum()})")
    print("-" * 70)
    print("Validation Selected & Frozen Thresholds (Min Synthetic Cost Objective):")
    for m_name, t_val in results["frozen_thresholds"].items():
        print(f"  - {m_name:20s}: Threshold = {t_val:.2f}")
    print("=" * 70 + "\n")
