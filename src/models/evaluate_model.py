"""
Abuse-Ring Sentinel - Scaled Model Evaluation & Error Analysis Pipeline.

Evaluates trained baseline models on the strictly held-out test set using
frozen validation thresholds. Computes comprehensive risk detection metrics,
performs granular error analysis across account segments, and produces archetype-level breakdowns.
"""

import json
import os
import sys
from typing import Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.models.train_model import (
    load_and_prepare_dataset,
    split_data_stratified,
    run_training_pipeline,
)


def get_archetype_for_ring(ring_id: str) -> str:
    """Map ring_id to archetype for post-hoc debugging/evaluation only."""
    if not ring_id or ring_id == "nan" or not str(ring_id).startswith("RING_"):
        return "NON_ABUSE"
    try:
        ring_num = int(str(ring_id).split("_")[1])
        archetypes = [
            "INFRASTRUCTURE_LINKED",
            "DISTRIBUTED_FUNNEL",
            "SYNCHRONIZED_BURST",
            "TASK_JOB_SCAM",
            "COVER_TRAFFIC_HYBRID",
            "MIXED_PARTIAL",
        ]
        return archetypes[(ring_num - 1) % len(archetypes)]
    except Exception:
        return "UNKNOWN_ABUSE"


def compute_comprehensive_metrics(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    threshold: float = 0.50,
) -> dict[str, Any]:
    """
    Computes standard and risk-specific classification metrics.
    """
    y_pred = (y_probs >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    acc = float(accuracy_score(y_true, y_pred))
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    try:
        roc_auc = float(roc_auc_score(y_true, y_probs))
    except Exception:
        roc_auc = 0.5

    try:
        pr_auc = float(average_precision_score(y_true, y_probs))
    except Exception:
        pr_auc = 0.0

    return {
        "threshold": float(round(threshold, 4)),
        "accuracy": float(round(acc, 4)),
        "precision": float(round(prec, 4)),
        "recall": float(round(rec, 4)),
        "f1": float(round(f1, 4)),
        "roc_auc": float(round(roc_auc, 4)),
        "pr_auc": float(round(pr_auc, 4)),
        "false_positive_rate": float(round(fpr, 4)),
        "false_negative_rate": float(round(fnr, 4)),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }


def evaluate_models_on_test(
    models_dir: str = "models",
    output_dir: str = "data/processed/model_results",
    features_path: str = "data/processed/account_features_pit.csv",
    ground_truth_path: str = "data/processed/ground_truth_pit.csv",
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Evaluates saved models on the held-out test split using frozen validation thresholds.
    """
    # 1. Ensure models and splits are trained / prepared
    meta_path = os.path.join(output_dir, "split_and_threshold_meta.json")
    if not os.path.exists(meta_path):
        train_res = run_training_pipeline(
            features_path=features_path,
            ground_truth_path=ground_truth_path,
            models_dir=models_dir,
            output_dir=output_dir,
            random_state=random_state,
        )
        frozen_thresholds = train_res["frozen_thresholds"]
    else:
        with open(meta_path, "r") as f:
            splits_meta = json.load(f)
        frozen_thresholds = splits_meta["frozen_thresholds"]

    # 2. Re-create exact deterministic dataset splits
    if os.path.basename(features_path) == "account_features_pit.csv":
        df_feats = pd.read_csv(features_path)
        df_gt = pd.read_csv(ground_truth_path)
        forbidden_cols = {
            "account_id", "account_type", "ring_id", "label", "target",
            "is_complete_window", "attack_event_count", "first_attack_time",
            "created_at", "created_dt", "t_obs", "t_outcome_end"
        }
        feature_cols = [c for c in df_feats.columns if c not in forbidden_cols]
        X = df_feats[["account_id"] + feature_cols].copy()
        y = df_gt.set_index("account_id").loc[X["account_id"]]["target"].astype(int).reset_index(drop=True)
    else:
        X, y, feature_cols = load_and_prepare_dataset(features_path, ground_truth_path, allow_legacy_lifetime=True)
        df_gt = pd.read_csv(ground_truth_path)

    if "val_account_ids" in splits_meta and "test_account_ids" in splits_meta:
        val_set = set(splits_meta["val_account_ids"])
        test_set = set(splits_meta["test_account_ids"])
        X_val = X[X["account_id"].isin(val_set)].copy()
        y_val = y[X["account_id"].isin(val_set)].copy()
        X_test = X[X["account_id"].isin(test_set)].copy()
        y_test = y[X["account_id"].isin(test_set)].copy()
        splits = {"X_val": X_val, "y_val": y_val, "X_test": X_test, "y_test": y_test}
    else:
        splits = split_data_stratified(X, y, random_state=random_state)
        X_val, y_val = splits["X_val"], splits["y_val"]
        X_test, y_test = splits["X_test"], splits["y_test"]

    X_val_mat = X_val[feature_cols]
    X_test_mat = X_test[feature_cols]

    # Load models
    model_names = ["logistic_regression", "random_forest"]
    all_metrics = {"validation": {}, "test": {}}
    all_confusion_matrices = {"validation": {}, "test": {}}
    predictions_records = []

    for name in model_names:
        model_file = os.path.join(models_dir, f"{name}.joblib")
        model = joblib.load(model_file)
        threshold = frozen_thresholds.get(name, 0.50)

        # Validation Metrics
        val_probs = model.predict_proba(X_val_mat)[:, 1]
        val_metrics = compute_comprehensive_metrics(y_val.values, val_probs, threshold=threshold)
        all_metrics["validation"][name] = val_metrics
        all_confusion_matrices["validation"][name] = val_metrics["confusion_matrix"]

        # Held-Out Test Metrics
        test_probs = model.predict_proba(X_test_mat)[:, 1]
        test_metrics = compute_comprehensive_metrics(y_test.values, test_probs, threshold=threshold)
        all_metrics["test"][name] = test_metrics
        all_confusion_matrices["test"][name] = test_metrics["confusion_matrix"]

        # Collect detailed test prediction records for error analysis
        test_preds = (test_probs >= threshold).astype(int)
        for i, acc_id in enumerate(X_test["account_id"].values):
            acc_meta = df_gt[df_gt["account_id"] == acc_id].iloc[0]
            row_feats = X_test[X_test["account_id"] == acc_id].iloc[0]
            r_id = str(acc_meta["ring_id"]) if pd.notna(acc_meta["ring_id"]) else ""

            predictions_records.append({
                "account_id": acc_id,
                "model": name,
                "split": "test",
                "account_type": acc_meta["account_type"],
                "ring_id": r_id,
                "archetype": get_archetype_for_ring(r_id),
                "actual_label": int(y_test.iloc[i]),
                "predicted_label": int(test_preds[i]),
                "predicted_probability": float(round(test_probs[i], 4)),
                "frozen_threshold": float(threshold),
                # Key explanatory feature values
                "accounts_sharing_device": row_feats["accounts_sharing_device"],
                "accounts_sharing_ip": row_feats["accounts_sharing_ip"],
                "number_of_accounts_with_shared_destinations": row_feats["number_of_accounts_with_shared_destinations"],
                "number_of_accounts_with_similar_transaction_timing": row_feats["number_of_accounts_with_similar_transaction_timing"],
                "number_of_accounts_with_similar_amount_behavior": row_feats["number_of_accounts_with_similar_amount_behavior"],
                "average_transaction_timing_similarity": row_feats["average_transaction_timing_similarity"],
            })

    # Save artifacts
    df_preds = pd.DataFrame(predictions_records)
    df_preds.to_csv(os.path.join(output_dir, "predictions.csv"), index=False)

    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(all_metrics, f, indent=2)

    with open(os.path.join(output_dir, "confusion_matrices.json"), "w") as f:
        json.dump(all_confusion_matrices, f, indent=2)

    return {
        "metrics": all_metrics,
        "confusion_matrices": all_confusion_matrices,
        "predictions": df_preds,
        "feature_cols": feature_cols,
        "splits": splits,
    }


def print_evaluation_report(eval_results: dict[str, Any]) -> None:
    """
    Prints a formatted, explainable evaluation report including held-out test
    metrics, confusion matrices, feature importance, and error analysis.
    """
    test_metrics = eval_results["metrics"]["test"]
    df_preds = eval_results["predictions"]

    print("\n" + "=" * 80)
    print("      ABUSE-RING SENTINEL - SCALED ML BASELINE EVALUATION REPORT")
    print("=" * 80)
    print("PROTOTYPE DISCLAIMER:")
    print("  These evaluation results are based on a 10,000-account synthetic dataset.")
    print("  They demonstrate the defensive ML architecture, strict validation protocol,")
    print("  and error inspection workflow, but remain bounded by synthetic assumptions.")
    print("=" * 80)

    # 1. Metrics Comparison Table
    print("\n1. HELD-OUT TEST SET PERFORMANCE (Evaluated on frozen validation thresholds):")
    print("-" * 80)
    headers = ["Model", "Threshold", "Precision", "Recall", "F1 Score", "ROC-AUC", "PR-AUC", "FPR", "FNR", "Accuracy"]
    rows = []
    for name, m in test_metrics.items():
        rows.append([
            name,
            f"{m['threshold']:.2f}",
            f"{m['precision']:.4f}",
            f"{m['recall']:.4f}",
            f"{m['f1']:.4f}",
            f"{m['roc_auc']:.4f}",
            f"{m['pr_auc']:.4f}",
            f"{m['false_positive_rate']:.4f}",
            f"{m['false_negative_rate']:.4f}",
            f"{m['accuracy']:.4f}",
        ])
    df_tab = pd.DataFrame(rows, columns=headers)
    print(df_tab.to_string(index=False))

    # 2. Confusion Matrices
    print("\n" + "-" * 80)
    print("2. TEST CONFUSION MATRICES (2,000 Held-Out Accounts):")
    for name, m in test_metrics.items():
        cm = m["confusion_matrix"]
        print(f"\n  [{name.upper()}] (Threshold = {m['threshold']:.2f})")
        print(f"               Predicted Non-Abuse (0)   Predicted Abuse (1)")
        print(f"    Actual 0:           {cm[0][0]:<12d}            {cm[0][1]:<12d}  (TN, FP)")
        print(f"    Actual 1:           {cm[1][0]:<12d}            {cm[1][1]:<12d}  (FN, TP)")

    # 3. Top Feature Importances (Random Forest)
    feat_imp_path = "data/processed/model_results/feature_importance.csv"
    if os.path.exists(feat_imp_path):
        df_imp = pd.read_csv(feat_imp_path)
        print("\n" + "-" * 80)
        print("3. TOP 8 MOST IMPORTANT FEATURES (Random Forest):")
        for i, row in df_imp.head(8).iterrows():
            print(f"  {i+1:2d}. {row['feature']:<50s} : {row['importance']:.4f}")

    # 4. Standardized Coefficients (Logistic Regression)
    lr_coef_path = "data/processed/model_results/logistic_regression_coefficients.csv"
    if os.path.exists(lr_coef_path):
        df_coef = pd.read_csv(lr_coef_path)
        print("\n" + "-" * 80)
        print("4. TOP 8 STANDARDIZED COEFFICIENTS (Logistic Regression):")
        for i, row in df_coef.head(8).iterrows():
            direction = "(+ Increases Risk)" if row["coefficient"] > 0 else "(- Reduces Risk)"
            print(f"  {i+1:2d}. {row['feature']:<50s} : {row['coefficient']:+.4f} {direction}")

    # 5. Error Analysis
    print("\n" + "-" * 80)
    print("5. DETAILED HELD-OUT TEST ERROR ANALYSIS & SEGMENT INSPECTION:")
    for name in ["random_forest", "logistic_regression"]:
        sub_p = df_preds[df_preds["model"] == name]
        fps = sub_p[(sub_p["actual_label"] == 0) & (sub_p["predicted_label"] == 1)]
        fns = sub_p[(sub_p["actual_label"] == 1) & (sub_p["predicted_label"] == 0)]
        tps = sub_p[(sub_p["actual_label"] == 1) & (sub_p["predicted_label"] == 1)]

        n_actual_abuse = len(sub_p[sub_p["actual_label"] == 1])
        n_actual_legit = len(sub_p[sub_p["actual_label"] == 0])

        print(f"\n  >>> Model: {name.upper()} (Total Test Accounts: {len(sub_p):,})")
        print(f"      • True Positives Detected : {len(tps):>3d} / {n_actual_abuse:,} actual abuse accounts")
        print(f"      • False Positives (Alarms): {len(fps):>3d} / {n_actual_legit:,} legitimate accounts")
        print(f"      • False Negatives (Misses): {len(fns):>3d} / {n_actual_abuse:,} actual abuse accounts")

        if len(fps) > 0:
            fp_type_counts = fps["account_type"].value_counts().to_dict()
            print(f"      • False Positive Breakdown by Type: {fp_type_counts}")

    # 6. Archetype-Level Detection Breakdown
    print("\n" + "-" * 80)
    print("6. DETECTION PERFORMANCE BY ABUSE ARCHETYPE (Held-Out Test Set):")
    sub_rf = df_preds[df_preds["model"] == "random_forest"]
    abuse_test = sub_rf[sub_rf["actual_label"] == 1]
    arch_summary = []
    for arch, grp in abuse_test.groupby("archetype"):
        total_arch = len(grp)
        detected_arch = int((grp["predicted_label"] == 1).sum())
        recall_arch = float(detected_arch / total_arch) if total_arch > 0 else 0.0
        avg_prob = float(grp["predicted_probability"].mean())
        arch_summary.append({
            "Archetype": arch,
            "Total In Test": total_arch,
            "Detected (TP)": detected_arch,
            "Missed (FN)": total_arch - detected_arch,
            "Recall Rate": f"{recall_arch*100:.1f}%",
            "Avg Predicted Prob": f"{avg_prob:.4f}",
        })
    df_arch = pd.DataFrame(arch_summary)
    print(df_arch.to_string(index=False))

    # 7. Qualitative Discussion of Limitations
    print("\n" + "-" * 80)
    print("7. DEFENSIVE DISCUSSION & SYNTHETIC DATA LIMITATIONS:")
    print("  • Hardest Scenario (Cover Traffic & Mixed Partial Coordination):")
    print("    Abuse rings that blend retail shopping with sparse cashouts require longer historical")
    print("    windows to accumulate enough statistical signal to separate from legitimate multi-user households.")
    print("  • Synthetic Separation Warning:")
    print("    In this synthetic benchmark, high AUC is facilitated by clear behavioral formulas")
    print("    (e.g., exact timing windows, amount tiering). In production, adversaries inject deliberate")
    print("    random delays and amount jitter, making graph topology and multimodal embeddings necessary.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    results = evaluate_models_on_test()
    print_evaluation_report(results)
