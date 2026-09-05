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
from typing import Any

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


# Configurable Synthetic Cost Assumptions (for threshold optimization)
# NOTE: These are synthetic demonstration values, not real-world Razorpay economics.
DEFAULT_COST_FP = 15.0  # Synthetic analyst investigation cost per false alarm
DEFAULT_COST_FN = 100.0  # Synthetic loss per undetected abuse account


def load_and_prepare_dataset(
    features_path: str = "data/processed/account_features.csv",
    ground_truth_path: str = "data/processed/ground_truth.csv",
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """
    Loads features and ground-truth metadata, constructs binary target,
    and strictly isolates features from ground truth.

    Target:
      1 = abuse_ring account
      0 = non-abuse account (normal or legitimate_shared)
    """
    if not os.path.exists(features_path):
        raise FileNotFoundError(f"Features file not found at: {features_path}")
    if not os.path.exists(ground_truth_path):
        raise FileNotFoundError(f"Ground truth file not found at: {ground_truth_path}")

    df_feats = pd.read_csv(features_path)
    df_gt = pd.read_csv(ground_truth_path)

    # Merge ONLY to extract the label
    df_merged = df_feats.merge(df_gt[["account_id", "account_type", "ring_id"]], on="account_id")

    # Construct binary target: 1 for abuse_ring, 0 for legitimate_shared and normal
    y = (df_merged["account_type"] == "abuse_ring").astype(int)

    # Feature columns (strictly excluding account_id and all ground truth labels)
    forbidden_cols = {"account_id", "account_type", "ring_id", "label", "target"}
    feature_cols = [c for c in df_feats.columns if c not in forbidden_cols]

    # Verify no ground truth leaked into feature columns
    for col in feature_cols:
        assert col in df_feats.columns, f"Unknown column {col}"
        assert col not in ["account_type", "ring_id"], f"Leaked target column: {col}"

    X = df_merged[["account_id"] + feature_cols].copy()
    return X, y, feature_cols


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
    features_path: str = "data/processed/account_features.csv",
    ground_truth_path: str = "data/processed/ground_truth.csv",
    models_dir: str = "models",
    output_dir: str = "data/processed/model_results",
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Executes end-to-end training and validation threshold freezing pipeline.
    """
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # 1. Load data
    X, y, feature_cols = load_and_prepare_dataset(features_path, ground_truth_path)

    # 2. Stratified Split
    splits = split_data_stratified(X, y, random_state=random_state)
    X_train, y_train = splits["X_train"], splits["y_train"]
    X_val, y_val = splits["X_val"], splits["y_val"]
    X_test, y_test = splits["X_test"], splits["y_test"]

    # Extract feature matrices (dropping account_id)
    X_train_mat = X_train[feature_cols]
    X_val_mat = X_val[feature_cols]

    # 3. Train models
    models = train_models(X_train_mat, y_train, random_state=random_state)

    # 4. Tune and freeze thresholds on Validation Set
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
        "train_account_ids": X_train["account_id"].tolist(),
        "val_account_ids": X_val["account_id"].tolist(),
        "test_account_ids": X_test["account_id"].tolist(),
        "feature_columns": feature_cols,
        "frozen_thresholds": frozen_thresholds,
        "synthetic_costs": {"cost_fp": DEFAULT_COST_FP, "cost_fn": DEFAULT_COST_FN},
    }
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
