import json
import os
import sys
from typing import Any
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.models.train_model import (
    load_and_prepare_dataset,
    train_models,
    optimize_threshold_on_val,
    DEFAULT_COST_FP,
    DEFAULT_COST_FN
)
from src.models.evaluate_model import (
    compute_comprehensive_metrics,
    get_archetype_for_ring
)

def split_data_ring_holdout(
    X: pd.DataFrame,
    y: pd.Series,
    df_gt: pd.DataFrame,
    train_size: float = 0.60,
    val_size: float = 0.20,
    test_size: float = 0.20,
    random_state: int = 42,
) -> dict[str, Any]:
    assert abs((train_size + val_size + test_size) - 1.0) < 1e-6, "Split sizes must sum to 1.0"
    
    # Merge gt back to X just for splitting
    df_full = X.merge(df_gt[["account_id", "ring_id", "account_type"]], on="account_id")
    
    # Split non-abuse accounts
    non_abuse = df_full[df_full["account_type"] != "abuse_ring"]
    abuse = df_full[df_full["account_type"] == "abuse_ring"]
    
    # Train/Val/Test for non-abuse
    val_test_ratio = val_size + test_size
    na_train, na_temp = train_test_split(non_abuse, test_size=val_test_ratio, random_state=random_state)
    val_rel_ratio = val_size / val_test_ratio
    na_val, na_test = train_test_split(na_temp, test_size=(1.0 - val_rel_ratio), random_state=random_state)
    
    # Train/Val/Test for abuse rings by ring_id
    unique_rings = abuse["ring_id"].dropna().unique()
    rings_train, rings_temp = train_test_split(unique_rings, test_size=val_test_ratio, random_state=random_state)
    rings_val, rings_test = train_test_split(rings_temp, test_size=(1.0 - val_rel_ratio), random_state=random_state)
    
    ab_train = abuse[abuse["ring_id"].isin(rings_train)]
    ab_val = abuse[abuse["ring_id"].isin(rings_val)]
    ab_test = abuse[abuse["ring_id"].isin(rings_test)]
    
    train_df = pd.concat([na_train, ab_train]).sample(frac=1, random_state=random_state)
    val_df = pd.concat([na_val, ab_val]).sample(frac=1, random_state=random_state)
    test_df = pd.concat([na_test, ab_test]).sample(frac=1, random_state=random_state)
    
    # Extract features and targets
    feature_cols = [c for c in X.columns if c != "account_id"]
    
    X_train = train_df[["account_id"] + feature_cols]
    y_train = (train_df["account_type"] == "abuse_ring").astype(int)
    
    X_val = val_df[["account_id"] + feature_cols]
    y_val = (val_df["account_type"] == "abuse_ring").astype(int)
    
    X_test = test_df[["account_id"] + feature_cols]
    y_test = (test_df["account_type"] == "abuse_ring").astype(int)
    
    # Metadata for counts
    counts = {
        "rings_train": len(rings_train),
        "rings_val": len(rings_val),
        "rings_test": len(rings_test),
        "acc_train": len(train_df),
        "acc_val": len(val_df),
        "acc_test": len(test_df),
        "abuse_acc_train": len(ab_train),
        "abuse_acc_val": len(ab_val),
        "abuse_acc_test": len(ab_test),
    }
    
    return {
        "X_train": X_train, "y_train": y_train,
        "X_val": X_val, "y_val": y_val,
        "X_test": X_test, "y_test": y_test,
        "counts": counts,
        "test_df": test_df
    }

def run_ring_holdout_evaluation():
    features_path = "data/processed/account_features.csv"
    ground_truth_path = "data/processed/ground_truth.csv"
    output_dir = "data/processed/model_results"
    
    os.makedirs(output_dir, exist_ok=True)
    
    X, y, feature_cols = load_and_prepare_dataset(features_path, ground_truth_path)
    df_gt = pd.read_csv(ground_truth_path)
    
    splits = split_data_ring_holdout(X, y, df_gt, random_state=42)
    
    X_train_mat = splits["X_train"][feature_cols]
    y_train = splits["y_train"]
    X_val_mat = splits["X_val"][feature_cols]
    y_val = splits["y_val"]
    X_test_mat = splits["X_test"][feature_cols]
    y_test = splits["y_test"]
    
    print("Training models on Ring-Held-Out train split...")
    models = train_models(X_train_mat, y_train, random_state=42)
    
    frozen_thresholds = {}
    val_summaries = {}
    test_metrics = {}
    predictions_records = []
    
    for name, model in models.items():
        # Validate and optimize threshold
        val_probs = model.predict_proba(X_val_mat)[:, 1]
        best_thresh, opt_res = optimize_threshold_on_val(
            y_val.values, val_probs, cost_fp=DEFAULT_COST_FP, cost_fn=DEFAULT_COST_FN, metric_objective="min_cost"
        )
        frozen_thresholds[name] = best_thresh
        val_summaries[name] = opt_res
        
        # Test evaluation
        test_probs = model.predict_proba(X_test_mat)[:, 1]
        t_metrics = compute_comprehensive_metrics(y_test.values, test_probs, threshold=best_thresh)
        test_metrics[name] = t_metrics
        
        # Predictions for error analysis
        test_preds = (test_probs >= best_thresh).astype(int)
        test_df = splits["test_df"]
        
        for i, acc_id in enumerate(splits["X_test"]["account_id"].values):
            acc_meta = df_gt[df_gt["account_id"] == acc_id].iloc[0]
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
                "frozen_threshold": float(best_thresh),
            })
            
    # Save outputs
    metrics_out = {
        "counts": splits["counts"],
        "thresholds": frozen_thresholds,
        "test_metrics": test_metrics
    }
    
    with open(os.path.join(output_dir, "ring_holdout_metrics.json"), "w") as f:
        json.dump(metrics_out, f, indent=2)
        
    df_preds = pd.DataFrame(predictions_records)
    df_preds.to_csv(os.path.join(output_dir, "ring_holdout_predictions.csv"), index=False)
    
    print("\n" + "=" * 80)
    print("      RING-HELD-OUT EVALUATION REPORT")
    print("=" * 80)
    print(f"Rings in Train: {splits['counts']['rings_train']}, Val: {splits['counts']['rings_val']}, Test: {splits['counts']['rings_test']}")
    print(f"Accounts in Train: {splits['counts']['acc_train']}, Val: {splits['counts']['acc_val']}, Test: {splits['counts']['acc_test']}")
    
    for name, m in test_metrics.items():
        print(f"\n[{name.upper()}] (Threshold = {m['threshold']:.2f})")
        print(f"Precision: {m['precision']:.4f}, Recall: {m['recall']:.4f}, F1: {m['f1']:.4f}")
        print(f"ROC-AUC: {m['roc_auc']:.4f}, PR-AUC: {m['pr_auc']:.4f}")
        print(f"FPR: {m['false_positive_rate']:.4f}, FNR: {m['false_negative_rate']:.4f}")
        print(f"Confusion Matrix: {m['confusion_matrix']}")
        
    # Error analysis and comparison
    print("\n--- COMPARISON ---")
    print("Account-Stratified vs Ring-Held-Out:")
    print("In Account-Stratified, parts of a single abuse ring could be in both Train and Test.")
    print("In Ring-Held-Out, Test contains COMPLETELY UNSEEN rings.")
    print("A drop in performance on Ring-Held-Out indicates the model memorized the synthetic archetypes or specific members rather than learning general coordination patterns.")
    
    sub_rf = df_preds[df_preds["model"] == "random_forest"]
    abuse_test = sub_rf[sub_rf["actual_label"] == 1]
    
    print("\n--- ERROR ANALYSIS (Random Forest on Unseen Rings) ---")
    arch_summary = []
    for arch, grp in abuse_test.groupby("archetype"):
        total_arch = len(grp)
        detected_arch = int((grp["predicted_label"] == 1).sum())
        recall_arch = float(detected_arch / total_arch) if total_arch > 0 else 0.0
        arch_summary.append({
            "Archetype": arch,
            "Total In Test": total_arch,
            "Detected": detected_arch,
            "Missed (FN)": total_arch - detected_arch,
            "Recall Rate": f"{recall_arch*100:.1f}%",
        })
    df_arch = pd.DataFrame(arch_summary)
    print(df_arch.to_string(index=False))

    fps = sub_rf[(sub_rf["actual_label"] == 0) & (sub_rf["predicted_label"] == 1)]
    print(f"\nFalse Positives (Random Forest): {len(fps)}")
    if len(fps) > 0:
        print(fps["account_type"].value_counts().to_dict())
        
    print("\nIf performance dropped substantially, the model may be relying too much on specific graph shapes rather than generalizable behavior.")
        
if __name__ == "__main__":
    run_ring_holdout_evaluation()
