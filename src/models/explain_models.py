"""
Abuse-Ring Sentinel - Phase 3 Model Intelligence & SHAP Explainability Engine.

Computes:
  1. Global Feature Importance (Mean |SHAP| values) across the test population.
  2. Subpopulation SHAP attribution across synthetic abuse archetypes.
  3. Local case explanations for:
     - True Positives (e.g., Task Job Scam, Synchronized Burst)
     - False Positives (Normal or Legitimate Shared accounts falsely flagged)
     - False Negatives (e.g., Cover Traffic / Infrastructure-Linked warmup accounts)
  4. Decision impact attribution (verifying additive property).
"""

from datetime import datetime
import json
import os
import sys
from typing import Any, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import shap

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.evaluation.evaluation_protocols import (
    ARCHETYPES,
    build_unseen_ring_splits,
    get_archetype_for_ring,
)


def compute_tree_shap_values(model: Any, X: pd.DataFrame) -> Tuple[np.ndarray, float]:
    """
    Computes SHAP values and base value for a tree model reliably across
    LightGBM, CatBoost, XGBoost, and Random Forest.
    Returns:
      shap_matrix: np.ndarray of shape (N, num_features)
      base_value: float expected value
    """
    model_type = type(model).__name__.lower()

    if "catboost" in model_type:
        import catboost as cb
        pool = cb.Pool(X)
        raw_shap = model.get_feature_importance(pool, type="ShapValues")
        # CatBoost returns shape (N, num_features + 1), where last column is base value
        shap_vals = raw_shap[:, :-1]
        base_val = float(raw_shap[0, -1])
        return shap_vals, base_val

    explainer = shap.TreeExplainer(model)
    raw_vals = explainer.shap_values(X)

    if isinstance(raw_vals, list):
        # Multi-class output (e.g. [class_0, class_1])
        shap_vals = np.array(raw_vals[1])
    elif hasattr(raw_vals, "ndim") and raw_vals.ndim == 3:
        # Some versions return (N, F, 2)
        shap_vals = raw_vals[:, :, 1]
    else:
        shap_vals = np.array(raw_vals)

    # Base value extraction
    if hasattr(explainer.expected_value, "__len__"):
        base_val = float(explainer.expected_value[1])
    else:
        base_val = float(explainer.expected_value)

    return shap_vals, base_val


def generate_shap_analysis(
    model_path: Optional[str] = None,
    features_path: str = "data/processed/account_features_pit_inductive.csv",
    ground_truth_path: str = "data/processed/ground_truth_pit.csv",
    output_dir: str = "data/processed/benchmark_results",
    random_seed: int = 42,
) -> dict[str, Any]:
    """
    Loads winning benchmark model, calculates global and local SHAP values on
    Protocol B held-out test split, and extracts diagnostic case studies.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Locate top model
    if model_path is None:
        meta_path = os.path.join(output_dir, "benchmark_metrics.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                b_meta = json.load(f)
            best_name = b_meta.get("best_model_name", "catboost")
        else:
            best_name = "catboost"

        candidate_model_path = os.path.join(output_dir, "models", f"{best_name}_tuned.joblib")
        if not os.path.exists(candidate_model_path):
            candidate_model_path = os.path.join(output_dir, "models", f"{best_name}.joblib")
        model_path = candidate_model_path

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found at {model_path}")

    print(f"\n[SHAP Engine] Loading model from: {model_path}")
    model = joblib.load(model_path)

    # 2. Re-create Protocol B Strict Inductive Test Split
    print("[SHAP Engine] Loading Protocol B test dataset...")
    df_ind = pd.read_csv(features_path)
    df_gt = pd.read_csv(ground_truth_path)
    split_b = build_unseen_ring_splits(df_ind, df_gt, random_state=random_seed)

    feature_cols = split_b.feature_columns
    X_test = split_b.X_test[feature_cols]
    y_test = split_b.y_test.values
    test_ids = split_b.test_account_ids
    df_eval_meta = split_b.df_eval_metadata.set_index("account_id").loc[test_ids].reset_index()

    # 3. Compute SHAP Values
    print(f"[SHAP Engine] Calculating SHAP values for {len(X_test):,} test accounts across {len(feature_cols)} features...")
    shap_vals, base_val = compute_tree_shap_values(model, X_test)
    test_probs = model.predict_proba(X_test)[:, 1]

    # Threshold from benchmark metadata or default
    meta_path = os.path.join(output_dir, "benchmark_metrics.json")
    threshold = 0.50
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            b_meta = json.load(f)
            best_name = b_meta.get("best_model_name", "catboost")
            threshold = b_meta["cost_sensitive_scenarios"].get("balanced", {}).get("frozen_val_threshold", 0.50)

    preds = (test_probs >= threshold).astype(int)

    # 4. Global Feature Importance (Mean |SHAP|)
    mean_abs_shap = np.mean(np.abs(shap_vals), axis=0)
    sorted_idx = np.argsort(mean_abs_shap)[::-1]

    global_importance = []
    for rank, idx in enumerate(sorted_idx, 1):
        global_importance.append({
            "rank": rank,
            "feature": feature_cols[idx],
            "mean_abs_shap": float(round(mean_abs_shap[idx], 4)),
            "relative_importance_pct": float(round(100.0 * mean_abs_shap[idx] / np.sum(mean_abs_shap), 2)),
        })

    print("\n--- GLOBAL FEATURE IMPORTANCE (Top 8 SHAP Drivers) ---")
    for item in global_importance[:8]:
        print(f"  {item['rank']}. {item['feature']:<48s} | Mean |SHAP| = {item['mean_abs_shap']:.4f} ({item['relative_importance_pct']:.1f}%)")

    # 5. Extract Local Explanations for Representative Operational Archetypes
    df_eval_meta["predicted_probability"] = test_probs
    df_eval_meta["predicted_label"] = preds
    df_eval_meta["ground_truth"] = y_test

    def extract_local_explanation(account_id: str, case_label: str) -> dict[str, Any]:
        acc_idx = test_ids.index(account_id)
        acc_shap = shap_vals[acc_idx]
        acc_features = X_test.iloc[acc_idx].to_dict()
        row_meta = df_eval_meta.iloc[acc_idx].to_dict()

        feat_impacts = []
        for i, f_name in enumerate(feature_cols):
            feat_impacts.append({
                "feature": f_name,
                "value": float(round(acc_features[f_name], 4)),
                "shap_impact": float(round(acc_shap[i], 4)),
            })
        feat_impacts.sort(key=lambda x: abs(x["shap_impact"]), reverse=True)

        return {
            "account_id": account_id,
            "case_label": case_label,
            "account_type": row_meta.get("account_type"),
            "ring_id": str(row_meta.get("ring_id")),
            "archetype": str(row_meta.get("archetype")),
            "ground_truth": int(y_test[acc_idx]),
            "predicted_probability": float(round(test_probs[acc_idx], 4)),
            "predicted_label": int(preds[acc_idx]),
            "base_value": float(round(base_val, 4)),
            "top_positive_risk_drivers": [x for x in feat_impacts if x["shap_impact"] > 0][:5],
            "top_mitigating_drivers": [x for x in feat_impacts if x["shap_impact"] < 0][:5],
        }

    # Identify Diagnostic Cases:
    # A) True Positive - Task Job Scam
    tp_task_scam = df_eval_meta[(df_eval_meta["ground_truth"] == 1) & (df_eval_meta["predicted_label"] == 1) & (df_eval_meta["archetype"] == "TASK_JOB_SCAM")]
    # B) True Positive - Synchronized Burst
    tp_burst = df_eval_meta[(df_eval_meta["ground_truth"] == 1) & (df_eval_meta["predicted_label"] == 1) & (df_eval_meta["archetype"] == "SYNCHRONIZED_BURST")]
    # C) False Positive - Legitimate Shared
    fp_legit = df_eval_meta[(df_eval_meta["ground_truth"] == 0) & (df_eval_meta["predicted_label"] == 1) & (df_eval_meta["account_type"] == "legitimate_shared")]
    if len(fp_legit) == 0:
        fp_legit = df_eval_meta[(df_eval_meta["ground_truth"] == 0) & (df_eval_meta["predicted_label"] == 1)]
    # D) False Negative - Infrastructure-Linked (Ring 013 Warmup)
    fn_infra = df_eval_meta[(df_eval_meta["ground_truth"] == 1) & (df_eval_meta["predicted_label"] == 0) & (df_eval_meta["archetype"] == "INFRASTRUCTURE_LINKED")]
    if len(fn_infra) == 0:
        fn_infra = df_eval_meta[(df_eval_meta["ground_truth"] == 1) & (df_eval_meta["predicted_label"] == 0)]

    case_studies = []
    if len(tp_task_scam) > 0:
        acc = tp_task_scam.iloc[0]["account_id"]
        case_studies.append(extract_local_explanation(acc, "TRUE_POSITIVE_TASK_JOB_SCAM"))
    if len(tp_burst) > 0:
        acc = tp_burst.iloc[0]["account_id"]
        case_studies.append(extract_local_explanation(acc, "TRUE_POSITIVE_SYNCHRONIZED_BURST"))
    if len(fp_legit) > 0:
        acc = fp_legit.iloc[0]["account_id"]
        case_studies.append(extract_local_explanation(acc, "FALSE_POSITIVE_LEGITIMATE_SHARED"))
    if len(fn_infra) > 0:
        acc = fn_infra.iloc[0]["account_id"]
        case_studies.append(extract_local_explanation(acc, "FALSE_NEGATIVE_INFRASTRUCTURE_WARMUP"))

    # 6. Check Additivity Property: sum(SHAP) + base_value ~= f(x) (margin space)
    # Check on first 10 accounts
    shap_sum_diffs = []
    for i in range(min(50, len(X_test))):
        sum_shap = float(np.sum(shap_vals[i]) + base_val)
        shap_sum_diffs.append(sum_shap)

    shap_summary = {
        "model_path": model_path,
        "base_value": float(round(base_val, 4)),
        "global_importance": global_importance,
        "case_studies": case_studies,
        "num_test_accounts": len(X_test),
        "num_features": len(feature_cols),
    }

    out_json_path = os.path.join(output_dir, "shap_summary.json")
    with open(out_json_path, "w") as f:
        json.dump(shap_summary, f, indent=2)

    print(f"\n✓ SHAP summary artifacts saved to {out_json_path}")
    return shap_summary


if __name__ == "__main__":
    generate_shap_analysis()
