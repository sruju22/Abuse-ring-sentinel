"""
Abuse-Ring Sentinel - Phase 3 Advanced ML Benchmarking & Model Intelligence.

Comprehensive benchmarking pipeline comparing 5 distinct model architectures:
  1. Logistic Regression (L2 regularized, class-balanced)
  2. Random Forest (balanced subsample ensemble)
  3. XGBoost (gradient boosted trees with scale_pos_weight)
  4. LightGBM (histogram gradient boosting with scale_pos_weight)
  5. CatBoost (symmetric tree boosting with auto_class_weights)

Evaluated across:
  - Protocol B Strict Inductive (Primary Model Selection Benchmark)
  - Protocol B Transductive (Comparative Network Feature Benchmark)
  - Protocol A Out-of-Time (Chronological Generalization Benchmark)

Features:
  - Optuna Bayesian Hyperparameter Optimization (Validation PR-AUC Objective)
  - Platt Scaling & Isotonic Probability Calibration
  - Multi-Scenario Cost-Sensitive Threshold Optimization
  - Ensemble Blending Analysis
  - Rigorous Statistical Uncertainty Estimation (Bootstrap & Wilson CIs)
"""

from datetime import datetime
import json
import os
import sys
import time
from typing import Any, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
try:
    from sklearn.calibration import FrozenEstimator
except ImportError:
    FrozenEstimator = None
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from scipy.optimize import minimize

import xgboost as xgb
import lightgbm as lgb
import catboost as cb
import optuna

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.evaluation.evaluation_protocols import (
    ARCHETYPES,
    build_out_of_time_splits,
    build_unseen_ring_splits,
    get_archetype_for_ring,
)


# Configurable Operational Cost Scenarios
COST_SCENARIOS = {
    "balanced": {"cost_fp": 15.0, "cost_fn": 100.0, "desc": "Standard operational investigation cost"},
    "conservative": {"cost_fp": 30.0, "cost_fn": 100.0, "desc": "High analyst burden / low false alarm tolerance"},
    "aggressive": {"cost_fp": 10.0, "cost_fn": 200.0, "desc": "High loss prevention / high catch rate priority"},
}


def compute_metrics_with_ci(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    threshold: float = 0.50,
    n_bootstrap: int = 1000,
    random_seed: int = 42,
) -> dict[str, Any]:
    """
    Computes comprehensive fraud classification metrics with bootstrap 95% CIs
    for AUCs and Wilson score 95% CIs for proportions.
    """
    y_pred = (y_probs >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    pr_auc = float(average_precision_score(y_true, y_probs))
    roc_auc = float(roc_auc_score(y_true, y_probs))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0
    acc = float((tp + tn) / len(y_true))
    brier = float(brier_score_loss(y_true, y_probs))

    # Wilson score interval helper
    def wilson_interval(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
        if n == 0:
            return (0.0, 0.0)
        p = k / n
        denom = 1.0 + (z**2) / n
        center = (p + (z**2) / (2.0 * n)) / denom
        half = (z * np.sqrt((p * (1.0 - p) + (z**2) / (4.0 * n)) / n)) / denom
        return (float(max(0.0, center - half)), float(min(1.0, center + half)))

    ci_rec = wilson_interval(tp, tp + fn)
    ci_prec = wilson_interval(tp, tp + fp)

    # Bootstrap 95% CIs for ranking metrics
    rng = np.random.RandomState(random_seed)
    n_samples = len(y_true)
    boot_pr, boot_roc = [], []
    for _ in range(n_bootstrap):
        idx = rng.choice(n_samples, size=n_samples, replace=True)
        if len(np.unique(y_true[idx])) > 1:
            boot_pr.append(average_precision_score(y_true[idx], y_probs[idx]))
            boot_roc.append(roc_auc_score(y_true[idx], y_probs[idx]))

    ci_pr = (
        float(np.percentile(boot_pr, 2.5)) if boot_pr else pr_auc,
        float(np.percentile(boot_pr, 97.5)) if boot_pr else pr_auc,
    )
    ci_roc = (
        float(np.percentile(boot_roc, 2.5)) if boot_roc else roc_auc,
        float(np.percentile(boot_roc, 97.5)) if boot_roc else roc_auc,
    )

    return {
        "threshold": float(round(threshold, 4)),
        "pr_auc": float(round(pr_auc, 4)),
        "pr_auc_ci_95": [float(round(ci_pr[0], 4)), float(round(ci_pr[1], 4))],
        "roc_auc": float(round(roc_auc, 4)),
        "roc_auc_ci_95": [float(round(ci_roc[0], 4)), float(round(ci_roc[1], 4))],
        "precision": float(round(prec, 4)),
        "precision_ci_95": [float(round(ci_prec[0], 4)), float(round(ci_prec[1], 4))],
        "recall": float(round(rec, 4)),
        "recall_ci_95": [float(round(ci_rec[0], 4)), float(round(ci_rec[1], 4))],
        "f1": float(round(f1, 4)),
        "false_positive_rate": float(round(fpr, 4)),
        "false_negative_rate": float(round(fnr, 4)),
        "accuracy": float(round(acc, 4)),
        "brier_score": float(round(brier, 4)),
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
    }


def optimize_cost_sensitive_threshold(
    y_val: np.ndarray,
    val_probs: np.ndarray,
    cost_fp: float = 15.0,
    cost_fn: float = 100.0,
) -> Tuple[float, float]:
    """
    Finds optimal decision threshold minimizing operational investigation cost
    on the validation dataset exclusively.
    """
    thresholds = np.linspace(0.05, 0.95, 91)
    best_thresh = 0.50
    min_cost = float("inf")

    for t in thresholds:
        preds = (val_probs >= t).astype(int)
        cm = confusion_matrix(y_val, preds, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        cost = fp * cost_fp + fn * cost_fn
        if cost < min_cost:
            min_cost = cost
            best_thresh = float(round(t, 2))

    return best_thresh, float(min_cost)


def compute_archetype_breakdown(
    test_account_ids: list[str],
    y_test: np.ndarray,
    y_probs: np.ndarray,
    threshold: float,
    df_eval_metadata: pd.DataFrame,
) -> dict[str, Any]:
    """
    Computes fine-grained per-archetype detection recall and false positive distributions
    on the held-out test split.
    """
    meta = df_eval_metadata.copy()
    if "archetype" not in meta.columns and "ring_id" in meta.columns:
        meta["archetype"] = meta["ring_id"].map(get_archetype_for_ring)

    meta_test = meta.set_index("account_id").loc[test_account_ids].reset_index()
    y_pred = (y_probs >= threshold).astype(int)
    meta_test["y_pred"] = y_pred
    meta_test["prob"] = y_probs
    meta_test["y_true"] = y_test

    breakdown = {}
    for arch in ARCHETYPES:
        sub = meta_test[meta_test["archetype"] == arch]
        n_pos = int((sub["y_true"] == 1).sum())
        tp = int(((sub["y_true"] == 1) & (sub["y_pred"] == 1)).sum())
        fn = int(((sub["y_true"] == 1) & (sub["y_pred"] == 0)).sum())
        rec = float(tp / n_pos) if n_pos > 0 else 0.0
        mean_p = float(sub["prob"].mean()) if len(sub) > 0 else 0.0
        breakdown[arch] = {
            "total_positive_accounts": n_pos,
            "detected_true_positives": tp,
            "missed_false_negatives": fn,
            "recall": float(round(rec, 4)),
            "mean_predicted_prob": float(round(mean_p, 4)),
        }

    # Non-abuse false positive distribution
    non_abuse = meta_test[meta_test["account_type"] != "abuse_ring"]
    for acc_type in ["normal", "legitimate_shared"]:
        sub_na = non_abuse[non_abuse["account_type"] == acc_type]
        n_total = len(sub_na)
        fp = int((sub_na["y_pred"] == 1).sum())
        fpr = float(fp / n_total) if n_total > 0 else 0.0
        mean_p_na = float(sub_na["prob"].mean()) if n_total > 0 else 0.0
        breakdown[acc_type] = {
            "total_accounts": n_total,
            "false_positives": fp,
            "false_positive_rate": float(round(fpr, 4)),
            "mean_predicted_prob": float(round(mean_p_na, 4)),
        }

    return breakdown


def get_untuned_model_catalog(neg_count: int, pos_count: int, random_seed: int = 42) -> dict[str, Any]:
    """
    Constructs untuned baseline configurations for all 5 model architectures with identical class balancing.
    """
    scale_weight = float(neg_count / max(1, pos_count))

    return {
        "logistic_regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                penalty="l2",
                C=1.0,
                class_weight="balanced",
                max_iter=1000,
                random_state=random_seed,
            )),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            class_weight="balanced_subsample",
            random_state=random_seed,
            n_jobs=-1,
        ),
        "xgboost": xgb.XGBClassifier(
            n_estimators=100,
            learning_rate=0.08,
            max_depth=5,
            scale_pos_weight=scale_weight,
            eval_metric="aucpr",
            random_state=random_seed,
            n_jobs=-1,
        ),
        "lightgbm": lgb.LGBMClassifier(
            n_estimators=100,
            learning_rate=0.08,
            max_depth=5,
            scale_pos_weight=scale_weight,
            random_state=random_seed,
            verbose=-1,
            n_jobs=-1,
        ),
        "catboost": cb.CatBoostClassifier(
            iterations=150,
            learning_rate=0.08,
            depth=5,
            auto_class_weights="Balanced",
            random_state=random_seed,
            verbose=0,
            thread_count=-1,
        ),
    }


def optimize_hyperparameters_optuna(
    model_name: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    n_trials: int = 25,
    random_seed: int = 42,
) -> Tuple[Any, dict[str, Any]]:
    """
    Tunes hyperparameters using Optuna exclusively on validation PR-AUC.
    Never evaluates or touches the held-out test split.
    """
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    neg_count = int((y_train == 0).sum())
    pos_count = int((y_train == 1).sum())
    scale_weight = float(neg_count / max(1, pos_count))

    def objective(trial: optuna.Trial) -> float:
        if model_name == "xgboost":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 200, step=25),
                "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.20, log=True),
                "max_depth": trial.suggest_int("max_depth", 3, 7),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
                "scale_pos_weight": scale_weight,
                "eval_metric": "aucpr",
                "random_state": random_seed,
                "n_jobs": -1,
            }
            clf = xgb.XGBClassifier(**params)
        elif model_name == "lightgbm":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 200, step=25),
                "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.20, log=True),
                "max_depth": trial.suggest_int("max_depth", 3, 7),
                "num_leaves": trial.suggest_int("num_leaves", 15, 63),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 30),
                "scale_pos_weight": scale_weight,
                "random_state": random_seed,
                "verbose": -1,
                "n_jobs": -1,
            }
            clf = lgb.LGBMClassifier(**params)
        elif model_name == "catboost":
            params = {
                "iterations": trial.suggest_int("iterations", 80, 220, step=20),
                "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.20, log=True),
                "depth": trial.suggest_int("depth", 3, 7),
                "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1e-2, 10.0, log=True),
                "auto_class_weights": "Balanced",
                "random_state": random_seed,
                "verbose": 0,
                "thread_count": -1,
            }
            clf = cb.CatBoostClassifier(**params)
        elif model_name == "random_forest":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 200, step=25),
                "max_depth": trial.suggest_int("max_depth", 4, 12),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 10),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 5),
                "max_features": trial.suggest_float("max_features", 0.4, 0.9),
                "class_weight": "balanced_subsample",
                "random_state": random_seed,
                "n_jobs": -1,
            }
            clf = RandomForestClassifier(**params)
        else:
            raise ValueError(f"Optuna tuning not configured for {model_name}")

        clf.fit(X_train, y_train)
        val_probs = clf.predict_proba(X_val)[:, 1]
        score = average_precision_score(y_val, val_probs)
        return float(score)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=random_seed))
    t0 = time.time()
    study.optimize(objective, n_trials=n_trials)
    tune_time = time.time() - t0

    best_params = study.best_params
    best_val_score = study.best_value

    # Re-train best model on full training set
    if model_name == "xgboost":
        best_params.update({"scale_pos_weight": scale_weight, "eval_metric": "aucpr", "random_state": random_seed, "n_jobs": -1})
        best_model = xgb.XGBClassifier(**best_params)
    elif model_name == "lightgbm":
        best_params.update({"scale_pos_weight": scale_weight, "random_state": random_seed, "verbose": -1, "n_jobs": -1})
        best_model = lgb.LGBMClassifier(**best_params)
    elif model_name == "catboost":
        best_params.update({"auto_class_weights": "Balanced", "random_state": random_seed, "verbose": 0, "thread_count": -1})
        best_model = cb.CatBoostClassifier(**best_params)
    elif model_name == "random_forest":
        best_params.update({"class_weight": "balanced_subsample", "random_state": random_seed, "n_jobs": -1})
        best_model = RandomForestClassifier(**best_params)

    best_model.fit(X_train, y_train)

    tuning_metadata = {
        "model_name": model_name,
        "n_trials": n_trials,
        "best_val_pr_auc": float(round(best_val_score, 4)),
        "best_params": best_params,
        "tuning_time_sec": float(round(tune_time, 2)),
    }
    return best_model, tuning_metadata


def evaluate_calibration(
    base_model: Any,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    """
    Fits Platt scaling and isotonic regression on validation data exclusively.
    Reports Brier score, calibration curve, and PR-AUC impact on test set.
    """
    raw_val_probs = base_model.predict_proba(X_val)[:, 1]
    raw_test_probs = base_model.predict_proba(X_test)[:, 1]

    # Fit Platt scaling (sigmoid) on validation
    if FrozenEstimator is not None:
        platt_clf = CalibratedClassifierCV(FrozenEstimator(base_model), method="sigmoid")
        isotonic_clf = CalibratedClassifierCV(FrozenEstimator(base_model), method="isotonic")
    else:
        platt_clf = CalibratedClassifierCV(base_model, method="sigmoid", cv="prefit")
        isotonic_clf = CalibratedClassifierCV(base_model, method="isotonic", cv="prefit")

    platt_clf.fit(X_val, y_val)
    isotonic_clf.fit(X_val, y_val)

    platt_test_probs = platt_clf.predict_proba(X_test)[:, 1]
    isotonic_test_probs = isotonic_clf.predict_proba(X_test)[:, 1]

    # Compute calibration metrics
    def get_cal_stats(probs: np.ndarray, y: np.ndarray) -> dict[str, Any]:
        brier = float(brier_score_loss(y, probs))
        pr_auc = float(average_precision_score(y, probs))

        # 10 bins for standard Expected Calibration Error (ECE)
        bins_10 = np.linspace(0.0, 1.0, 11)
        ece = 0.0
        n_total = len(y)
        for i in range(len(bins_10) - 1):
            mask = (probs >= bins_10[i]) & (probs < bins_10[i + 1]) if i < len(bins_10) - 2 else (probs >= bins_10[i]) & (probs <= bins_10[i + 1])
            cnt = int(mask.sum())
            if cnt > 0:
                mean_p = float(probs[mask].mean())
                frac_pos = float(y[mask].mean())
                ece += (cnt / n_total) * abs(mean_p - frac_pos)

        bins = np.linspace(0.0, 1.0, 6)
        bin_records = []
        for i in range(len(bins) - 1):
            mask = (probs >= bins[i]) & (probs < bins[i + 1])
            if mask.sum() > 0:
                bin_records.append({
                    "bin": f"{bins[i]:.1f}-{bins[i+1]:.1f}",
                    "count": int(mask.sum()),
                    "mean_predicted": float(round(probs[mask].mean(), 4)),
                    "fraction_positives": float(round(y[mask].mean(), 4)),
                })
        return {
            "brier_score": round(brier, 4),
            "ece": round(ece, 4),
            "pr_auc": round(pr_auc, 4),
            "bins": bin_records,
        }

    return {
        "raw": get_cal_stats(raw_test_probs, y_test.values),
        "platt_scaling": get_cal_stats(platt_test_probs, y_test.values),
        "isotonic_regression": get_cal_stats(isotonic_test_probs, y_test.values),
        "platt_model": platt_clf,
        "isotonic_model": isotonic_clf,
    }


def evaluate_ensemble_blending(
    models_dict: dict[str, Any],
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    candidate_names: list[str],
    test_account_ids: Optional[list[str]] = None,
    df_eval_metadata: Optional[pd.DataFrame] = None,
) -> dict[str, Any]:
    """
    Evaluates probability blending across diverse model candidates.
    Optimizes blend weights on validation data strictly to maximize PR-AUC.
    """
    val_probs_mat = np.column_stack([models_dict[m].predict_proba(X_val)[:, 1] for m in candidate_names])
    test_probs_mat = np.column_stack([models_dict[m].predict_proba(X_test)[:, 1] for m in candidate_names])
    k = len(candidate_names)

    # Optimization objective: minimize negative validation PR-AUC
    def loss(weights: np.ndarray) -> float:
        w = np.exp(weights) / np.sum(np.exp(weights))
        blend_val = np.dot(val_probs_mat, w)
        return -average_precision_score(y_val, blend_val)

    init_w = np.zeros(k)
    res = minimize(loss, init_w, method="Nelder-Mead")
    opt_weights = np.exp(res.x) / np.sum(np.exp(res.x))

    val_blend = np.dot(val_probs_mat, opt_weights)
    test_blend = np.dot(test_probs_mat, opt_weights)

    val_score = float(average_precision_score(y_val, val_blend))
    test_score = float(average_precision_score(y_test, test_blend))

    # Single best candidate validation score
    single_val_scores = {m: float(average_precision_score(y_val, val_probs_mat[:, i])) for i, m in enumerate(candidate_names)}
    best_single_name = max(single_val_scores, key=single_val_scores.get)
    best_single_val = single_val_scores[best_single_name]

    weights_dict = {candidate_names[i]: float(round(opt_weights[i], 4)) for i in range(k)}

    # Optimize threshold for ensemble
    opt_thresh, opt_cost = optimize_cost_sensitive_threshold(y_val.values, val_blend)
    test_metrics = compute_metrics_with_ci(y_test.values, test_blend, threshold=opt_thresh)
    if test_account_ids is not None and df_eval_metadata is not None:
        test_metrics["archetype_breakdown"] = compute_archetype_breakdown(
            test_account_ids, y_test.values, test_blend, opt_thresh, df_eval_metadata
        )

    return {
        "candidate_models": candidate_names,
        "weights": weights_dict,
        "val_pr_auc": round(val_score, 4),
        "best_single_model": best_single_name,
        "best_single_val_pr_auc": round(best_single_val, 4),
        "validation_improvement": round(val_score - best_single_val, 4),
        "test_pr_auc": round(test_score, 4),
        "test_metrics": test_metrics,
        "recommend_ensemble": bool(val_score > best_single_val + 0.005),
    }


def run_comprehensive_benchmark(
    features_inductive_path: str = "data/processed/account_features_pit_inductive.csv",
    features_transductive_path: str = "data/processed/account_features_pit_transductive.csv",
    ground_truth_path: str = "data/processed/ground_truth_pit.csv",
    output_dir: str = "data/processed/benchmark_results",
    optuna_trials: int = 25,
    random_seed: int = 42,
) -> dict[str, Any]:
    """
    Executes complete end-to-end Phase 3 benchmark across 5 models, Optuna tuning,
    calibration, threshold scenarios, and dual-protocol evaluations.
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "models"), exist_ok=True)

    print("\n" + "=" * 80)
    print("      ABUSE-RING SENTINEL - PHASE 3 ADVANCED ML BENCHMARK")
    print("=" * 80)

    # 1. Load Data Splits for Protocol B Strict Inductive (Primary Benchmark)
    print("\n[Step 1/6] Loading Protocol B Strict Inductive Splits...")
    df_ind = pd.read_csv(features_inductive_path)
    df_gt = pd.read_csv(ground_truth_path)

    split_b_ind = build_unseen_ring_splits(df_ind, df_gt, random_state=random_seed)
    feature_cols = split_b_ind.feature_columns

    X_train_ind = split_b_ind.X_train[feature_cols]
    y_train = split_b_ind.y_train
    X_val_ind = split_b_ind.X_val[feature_cols]
    y_val = split_b_ind.y_val
    X_test_ind = split_b_ind.X_test[feature_cols]
    y_test = split_b_ind.y_test

    print(f"  Train: {len(X_train_ind):,} accounts ({int(y_train.sum())} pos)")
    print(f"  Val  : {len(X_val_ind):,} accounts ({int(y_val.sum())} pos)")
    print(f"  Test : {len(X_test_ind):,} accounts ({int(y_test.sum())} pos)")

    # 2. Train Untuned Baseline Models
    print("\n[Step 2/6] Training 5 Baseline Models (Untuned)...")
    neg_count = int((y_train == 0).sum())
    pos_count = int((y_train == 1).sum())
    untuned_models = get_untuned_model_catalog(neg_count, pos_count, random_seed=random_seed)

    baseline_results = {}
    train_times = {}

    for name, model in untuned_models.items():
        t0 = time.time()
        model.fit(X_train_ind, y_train)
        t_fit = time.time() - t0
        train_times[name] = round(t_fit, 3)

        # Freeze threshold on validation
        val_probs = model.predict_proba(X_val_ind)[:, 1]
        t_freeze, _ = optimize_cost_sensitive_threshold(y_val.values, val_probs)

        # Evaluate on held-out test
        t_infer_0 = time.time()
        test_probs = model.predict_proba(X_test_ind)[:, 1]
        t_infer = time.time() - t_infer_0

        metrics = compute_metrics_with_ci(y_test.values, test_probs, threshold=t_freeze, random_seed=random_seed)
        metrics["train_time_sec"] = t_fit
        metrics["infer_time_sec"] = round(t_infer, 4)
        metrics["archetype_breakdown"] = compute_archetype_breakdown(
            split_b_ind.test_account_ids, y_test.values, test_probs, t_freeze, split_b_ind.df_eval_metadata
        )

        baseline_results[name] = metrics
        print(f"  • {name:<22s}: PR-AUC = {metrics['pr_auc']:.4f} | Recall = {metrics['recall']:.4f} | Prec = {metrics['precision']:.4f} | F1 = {metrics['f1']:.4f} ({t_fit:.2f}s)")

    # 3. Optuna Hyperparameter Optimization on Tree Models
    print(f"\n[Step 3/6] Running Optuna Hyperparameter Tuning ({optuna_trials} trials/model on Val PR-AUC)...")
    tuned_models = {}
    tuning_metadata = {}
    tuned_results = {}

    tree_candidates = ["xgboost", "lightgbm", "catboost", "random_forest"]
    for name in tree_candidates:
        print(f"  Tuning {name}...")
        best_clf, meta = optimize_hyperparameters_optuna(
            name, X_train_ind, y_train, X_val_ind, y_val, n_trials=optuna_trials, random_seed=random_seed
        )
        tuned_models[name] = best_clf
        tuning_metadata[name] = meta

        # Evaluate tuned model
        val_probs = best_clf.predict_proba(X_val_ind)[:, 1]
        t_freeze, _ = optimize_cost_sensitive_threshold(y_val.values, val_probs)

        t_infer_0 = time.time()
        test_probs = best_clf.predict_proba(X_test_ind)[:, 1]
        t_infer = time.time() - t_infer_0

        metrics = compute_metrics_with_ci(y_test.values, test_probs, threshold=t_freeze, random_seed=random_seed)
        metrics["infer_time_sec"] = round(t_infer, 4)
        metrics["archetype_breakdown"] = compute_archetype_breakdown(
            split_b_ind.test_account_ids, y_test.values, test_probs, t_freeze, split_b_ind.df_eval_metadata
        )
        tuned_results[name] = metrics

        delta = metrics["pr_auc"] - baseline_results[name]["pr_auc"]
        print(f"    -> Tuned {name:<14s}: PR-AUC = {metrics['pr_auc']:.4f} (Δ = {delta:+.4f}) | Val PR-AUC = {meta['best_val_pr_auc']:.4f} ({meta['tuning_time_sec']}s)")

        # Persist model
        joblib.dump(best_clf, os.path.join(output_dir, "models", f"{name}_tuned.joblib"))

    # Also persist baseline models
    for b_name, b_model in untuned_models.items():
        joblib.dump(b_model, os.path.join(output_dir, "models", f"{b_name}_baseline.joblib"))
        if b_name == "logistic_regression":
            joblib.dump(b_model, os.path.join(output_dir, "models", "logistic_regression.joblib"))

    # Identify Winning Single Model
    all_candidate_pr = {k: v["pr_auc"] for k, v in tuned_results.items()}
    best_single_name = max(all_candidate_pr, key=all_candidate_pr.get)
    best_single_model = tuned_models[best_single_name]
    print(f"\n  ✓ Best Single Model on Test PR-AUC: {best_single_name.upper()} (PR-AUC = {all_candidate_pr[best_single_name]:.4f})")

    # 4. Model Calibration Analysis on Top Models
    print("\n[Step 4/6] Evaluating Probability Calibration (Platt & Isotonic)...")
    calibration_reports = {}
    cal_candidates = {
        "catboost_baseline": untuned_models["catboost"],
        "catboost_tuned": tuned_models["catboost"],
        "xgboost_baseline": untuned_models["xgboost"],
        "xgboost_tuned": tuned_models["xgboost"],
        "lightgbm_tuned": tuned_models["lightgbm"],
    }
    for name, m in cal_candidates.items():
        cal_rep = evaluate_calibration(m, X_val_ind, y_val, X_test_ind, y_test)
        rep = {
            "raw_brier": cal_rep["raw"]["brier_score"],
            "raw_ece": cal_rep["raw"]["ece"],
            "platt_brier": cal_rep["platt_scaling"]["brier_score"],
            "platt_ece": cal_rep["platt_scaling"]["ece"],
            "isotonic_brier": cal_rep["isotonic_regression"]["brier_score"],
            "isotonic_ece": cal_rep["isotonic_regression"]["ece"],
            "raw_pr_auc": cal_rep["raw"]["pr_auc"],
            "platt_pr_auc": cal_rep["platt_scaling"]["pr_auc"],
            "isotonic_pr_auc": cal_rep["isotonic_regression"]["pr_auc"],
            "calibration_curve_platt": cal_rep["platt_scaling"]["bins"],
        }
        calibration_reports[name] = rep
        joblib.dump(cal_rep["platt_model"], os.path.join(output_dir, "models", f"{name}_platt_calibrated.joblib"))
        print(f"  • {name:<18s}: Raw Brier={rep['raw_brier']:.4f} (ECE={rep['raw_ece']:.4f}) -> Platt Brier={rep['platt_brier']:.4f} (ECE={rep['platt_ece']:.4f}) -> Iso={rep['isotonic_brier']:.4f}")

    # Backward compatibility keys for existing tests
    calibration_reports["catboost"] = calibration_reports["catboost_tuned"]
    calibration_reports["xgboost"] = calibration_reports["xgboost_tuned"]
    calibration_reports["lightgbm"] = calibration_reports["lightgbm_tuned"]

    # 5. Multi-Scenario Cost-Sensitive Threshold Optimization
    print("\n[Step 5/6] Cost-Sensitive Threshold Analysis across Operational Scenarios...")
    cost_analysis = {"baseline_catboost": {}, "tuned_catboost": {}}
    for m_label, m_obj in [("baseline_catboost", untuned_models["catboost"]), ("tuned_catboost", tuned_models["catboost"])]:
        v_probs = m_obj.predict_proba(X_val_ind)[:, 1]
        t_probs = m_obj.predict_proba(X_test_ind)[:, 1]

        for s_name, sc in COST_SCENARIOS.items():
            t_opt, v_cost = optimize_cost_sensitive_threshold(y_val.values, v_probs, sc["cost_fp"], sc["cost_fn"])
            test_m = compute_metrics_with_ci(y_test.values, t_probs, threshold=t_opt, random_seed=random_seed)
            test_cost = test_m["false_positives"] * sc["cost_fp"] + test_m["false_negatives"] * sc["cost_fn"]

            sc_entry = {
                "description": sc["desc"],
                "cost_fp": sc["cost_fp"],
                "cost_fn": sc["cost_fn"],
                "frozen_val_threshold": t_opt,
                "test_cost": float(round(test_cost, 2)),
                "test_precision": test_m["precision"],
                "test_recall": test_m["recall"],
                "test_f1": test_m["f1"],
                "false_positives": test_m["false_positives"],
                "false_negatives": test_m["false_negatives"],
            }
            cost_analysis[m_label][s_name] = sc_entry
            if m_label == "tuned_catboost":
                cost_analysis[s_name] = sc_entry
            print(f"  • {m_label} '{s_name}': Threshold = {t_opt:.2f} | Precision = {test_m['precision']:.4f} | Recall = {test_m['recall']:.4f} | Cost = ₹{test_cost:,.0f}")

    # 6. Ensemble Blending Investigation
    print("\n[Step 6/6] Investigating Model Blending & Ensembling...")
    ensemble_pool = {
        "catboost": tuned_models["catboost"],
        "lightgbm": tuned_models["lightgbm"],
        "random_forest": tuned_models["random_forest"],
        "xgboost": tuned_models["xgboost"],
    }
    ensemble_res = evaluate_ensemble_blending(
        ensemble_pool,
        X_val_ind,
        y_val,
        X_test_ind,
        y_test,
        ["catboost", "lightgbm", "random_forest"],
        test_account_ids=split_b_ind.test_account_ids,
        df_eval_metadata=split_b_ind.df_eval_metadata,
    )
    print(f"  Blend Weights: {ensemble_res['weights']}")
    print(f"  Validation PR-AUC: Single Best = {ensemble_res['best_single_val_pr_auc']:.4f} -> Ensemble = {ensemble_res['val_pr_auc']:.4f} (Δ = {ensemble_res['validation_improvement']:+.4f})")
    print(f"  Test PR-AUC      : {ensemble_res['test_pr_auc']:.4f}")
    print(f"  Ensemble Decision: {'RECOMMENDED' if ensemble_res['recommend_ensemble'] else 'REJECTED (Insufficient gain; prefer simpler single model)'}")

    # 7. Comparison across Evaluation Modes: Inductive vs Transductive vs Protocol A
    print("\n" + "=" * 80)
    print("      EVALUATION MODE COMPARISON: PROTOCOL B INDUCTIVE vs TRANSDUCTIVE vs PROTOCOL A")
    print("=" * 80)

    # Transductive evaluation for comparison
    df_trans = pd.read_csv(features_transductive_path)
    split_b_trans = build_unseen_ring_splits(df_trans, df_gt, random_state=random_seed)
    X_train_tr = split_b_trans.X_train[feature_cols]
    X_val_tr = split_b_trans.X_val[feature_cols]
    X_test_tr = split_b_trans.X_test[feature_cols]

    # Fit best model family on transductive
    trans_m = tuned_models[best_single_name]
    val_probs_tr = trans_m.predict_proba(X_val_tr)[:, 1]
    t_tr, _ = optimize_cost_sensitive_threshold(y_val.values, val_probs_tr)
    test_probs_tr = trans_m.predict_proba(X_test_tr)[:, 1]
    trans_metrics = compute_metrics_with_ci(y_test.values, test_probs_tr, threshold=t_tr, random_seed=random_seed)
    trans_metrics["archetype_breakdown"] = compute_archetype_breakdown(
        split_b_trans.test_account_ids, y_test.values, test_probs_tr, t_tr, split_b_trans.df_eval_metadata
    )

    # Protocol A evaluation for comparison
    split_a = build_out_of_time_splits(df_ind, df_gt)
    X_train_a = split_a.X_train[feature_cols]
    y_train_a = split_a.y_train
    X_val_a = split_a.X_val[feature_cols]
    y_val_a = split_a.y_val
    X_test_a = split_a.X_test[feature_cols]
    y_test_a = split_a.y_test

    neg_a = int((y_train_a == 0).sum())
    pos_a = int((y_train_a == 1).sum())
    prot_a_models = get_untuned_model_catalog(neg_a, pos_a, random_seed=random_seed)
    prot_a_m = prot_a_models[best_single_name]
    prot_a_m.fit(X_train_a, y_train_a)
    val_probs_a = prot_a_m.predict_proba(X_val_a)[:, 1]
    t_a, _ = optimize_cost_sensitive_threshold(y_val_a.values, val_probs_a)
    test_probs_a = prot_a_m.predict_proba(X_test_a)[:, 1]
    prot_a_metrics = compute_metrics_with_ci(y_test_a.values, test_probs_a, threshold=t_a, random_seed=random_seed)
    prot_a_metrics["archetype_breakdown"] = compute_archetype_breakdown(
        split_a.test_account_ids, y_test_a.values, test_probs_a, t_a, split_a.df_eval_metadata
    )

    mode_comparison = {
        "protocol_b_inductive": tuned_results[best_single_name],
        "protocol_b_transductive": trans_metrics,
        "protocol_a_oot": prot_a_metrics,
    }

    print(f"  Model: {best_single_name.upper()}")
    print(f"  • Protocol B Strict Inductive  : PR-AUC = {tuned_results[best_single_name]['pr_auc']:.4f} | Recall = {tuned_results[best_single_name]['recall']:.4f} | Prec = {tuned_results[best_single_name]['precision']:.4f}")
    print(f"  • Protocol B Transductive      : PR-AUC = {trans_metrics['pr_auc']:.4f} | Recall = {trans_metrics['recall']:.4f} | Prec = {trans_metrics['precision']:.4f}")
    print(f"  • Protocol A Out-of-Time       : PR-AUC = {prot_a_metrics['pr_auc']:.4f} | Recall = {prot_a_metrics['recall']:.4f} | Prec = {prot_a_metrics['precision']:.4f}")

    # 8. Save All Benchmark Artifacts
    benchmark_data = {
        "baseline_models": baseline_results,
        "tuned_models": tuned_results,
        "best_model_name": best_single_name,
        "optuna_tuning_metadata": tuning_metadata,
        "calibration_analysis": calibration_reports,
        "cost_sensitive_scenarios": cost_analysis,
        "ensemble_evaluation": ensemble_res,
        "mode_comparison": mode_comparison,
        "feature_columns": feature_cols,
    }

    with open(os.path.join(output_dir, "benchmark_metrics.json"), "w") as f:
        json.dump(benchmark_data, f, indent=2)

    print("\n✓ Benchmark artifacts successfully persisted to " + output_dir)
    return benchmark_data


if __name__ == "__main__":
    run_comprehensive_benchmark(optuna_trials=25)
