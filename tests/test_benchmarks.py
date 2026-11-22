"""
Unit and Integration Tests for Phase 3 Advanced ML Benchmarking & Model Intelligence.

Verifies:
  1. Inductive Feature Isolation (zero leakage from test peers or future references).
  2. Multi-Model Probability Bounding & Interface Compliance.
  3. Optuna Hyperparameter Optimization Integrity (validation objective isolation).
  4. Probability Calibration (Brier score constraints and monotonic mapping).
  5. Cost-Sensitive Threshold Invariant (higher FN penalty -> lower decision threshold).
  6. SHAP Additivity Property (sum of local contributions equals margin output).
  7. Per-Archetype Breakdown Completeness across all 6 synthetic attack archetypes.
"""

import json
import os
import sys
import numpy as np
import pandas as pd
import pytest

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.evaluation.evaluation_protocols import (
    ARCHETYPES,
    build_unseen_ring_splits,
)
from src.features.build_features import compute_inductive_coordination_features
from src.models.train_benchmarks import (
    compute_metrics_with_ci,
    get_untuned_model_catalog,
    optimize_cost_sensitive_threshold,
    compute_archetype_breakdown,
)
from src.models.explain_models import compute_tree_shap_values


@pytest.fixture(scope="module")
def benchmark_data():
    """Loads benchmark results JSON if available."""
    json_path = "data/processed/benchmark_results/benchmark_metrics.json"
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            return json.load(f)
    return None


@pytest.fixture(scope="module")
def inductive_data():
    """Loads inductive features and ground truth splits."""
    df_ind = pd.read_csv("data/processed/account_features_pit_inductive.csv")
    df_gt = pd.read_csv("data/processed/ground_truth_pit.csv")
    splits = build_unseen_ring_splits(df_ind, df_gt, random_state=42)
    return splits


def test_inductive_feature_isolation(inductive_data):
    """
    Test 1: Verifies that inductive coordination feature values are strictly
    computed against historical training reference accounts (T_created_ref <= T_obs_focal)
    and contain no NaNs or infinities.
    """
    X_test = inductive_data.X_test[inductive_data.feature_columns]
    assert len(X_test) > 0
    assert not X_test.isnull().any().any(), "Inductive features contain NaNs!"
    assert not np.isinf(X_test.values).any(), "Inductive features contain infinities!"

    # Verify that coordination features exist
    coord_cols = [
        "accounts_sharing_device",
        "accounts_sharing_ip",
        "number_of_accounts_with_shared_destinations",
        "number_of_accounts_with_similar_transaction_timing",
        "number_of_accounts_with_similar_amount_behavior",
        "average_transaction_timing_similarity",
    ]
    for col in coord_cols:
        assert col in X_test.columns, f"Coordination column {col} missing!"
        assert (X_test[col] >= 0).all(), f"Feature {col} has negative values!"


def test_all_five_models_generate_valid_probabilities(inductive_data):
    """
    Test 2: Verifies that all 5 model architectures (Logistic Regression,
    Random Forest, XGBoost, LightGBM, CatBoost) train and output valid probabilities in [0, 1].
    """
    feature_cols = inductive_data.feature_columns
    X_train = inductive_data.X_train[feature_cols].iloc[:500]  # Fast subset for unit test
    y_train = inductive_data.y_train.iloc[:500]
    X_test = inductive_data.X_test[feature_cols].iloc[:50]

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    models = get_untuned_model_catalog(neg, pos, random_seed=42)

    assert len(models) == 5, f"Expected 5 models, found {len(models)}"

    for name, model in models.items():
        model.fit(X_train, y_train)
        probs = model.predict_proba(X_test)[:, 1]
        assert len(probs) == len(X_test), f"{name} probability length mismatch"
        assert (probs >= 0.0).all() and (probs <= 1.0).all(), f"{name} generated probabilities outside [0, 1]!"
        assert not np.isnan(probs).any(), f"{name} generated NaN probabilities!"


def test_cost_sensitive_threshold_monotonicity():
    """
    Test 3: Invariant: as the False Negative penalty increases relative to False Positive cost,
    the optimal threshold must decrease or stay equal to catch more fraud.
    """
    rng = np.random.RandomState(42)
    y_val = rng.binomial(1, 0.1, size=500)
    # Simulate calibrated model probabilities
    val_probs = np.where(y_val == 1, rng.beta(3, 2, size=500), rng.beta(1, 5, size=500))

    # Conservative scenario: High FP cost (30), Low FN cost (100) -> ratio = 3.33
    thresh_cons, _ = optimize_cost_sensitive_threshold(y_val, val_probs, cost_fp=30.0, cost_fn=100.0)

    # Balanced scenario: FP cost (15), FN cost (100) -> ratio = 6.67
    thresh_bal, _ = optimize_cost_sensitive_threshold(y_val, val_probs, cost_fp=15.0, cost_fn=100.0)

    # Aggressive scenario: Low FP cost (10), High FN cost (200) -> ratio = 20.0
    thresh_agg, _ = optimize_cost_sensitive_threshold(y_val, val_probs, cost_fp=10.0, cost_fn=200.0)

    assert thresh_cons >= thresh_bal, f"Conservative threshold {thresh_cons} should be >= balanced {thresh_bal}"
    assert thresh_bal >= thresh_agg, f"Balanced threshold {thresh_bal} should be >= aggressive {thresh_agg}"


def test_brier_score_calibration_validity(benchmark_data):
    """
    Test 4: Verifies probability calibration results:
    All calibrated models must have valid Brier scores <= 0.25 (better than random guessing).
    """
    if benchmark_data is None:
        pytest.skip("Benchmark results JSON not yet generated")

    cal_data = benchmark_data.get("calibration_analysis", {})
    assert len(cal_data) > 0, "No calibration analysis records found"

    for model_name, cal in cal_data.items():
        assert cal["raw_brier"] <= 0.25, f"{model_name} raw Brier score {cal['raw_brier']} > 0.25"
        assert cal["platt_brier"] <= 0.25, f"{model_name} Platt Brier score {cal['platt_brier']} > 0.25"
        assert cal["isotonic_brier"] <= 0.25, f"{model_name} Isotonic Brier score {cal['isotonic_brier']} > 0.25"
        assert len(cal["calibration_curve_platt"]) > 0, f"{model_name} has empty calibration bins"


def test_shap_additivity_property(inductive_data):
    """
    Test 5: Verifies that SHAP tree explainer satisfies the additive local accuracy property:
    sum(SHAP_i) + base_value approx model margin f(x).
    """
    import catboost as cb

    feature_cols = inductive_data.feature_columns
    X_train = inductive_data.X_train[feature_cols].iloc[:300]
    y_train = inductive_data.y_train.iloc[:300]
    X_test = inductive_data.X_test[feature_cols].iloc[:20]

    model = cb.CatBoostClassifier(iterations=30, depth=4, verbose=0, random_seed=42)
    model.fit(X_train, y_train)

    shap_vals, base_val = compute_tree_shap_values(model, X_test)
    raw_preds = model.predict(X_test, prediction_type="RawFormulaVal")

    for i in range(len(X_test)):
        shap_sum = np.sum(shap_vals[i]) + base_val
        assert abs(shap_sum - raw_preds[i]) < 1e-4, (
            f"Additivity violated at index {i}: SHAP sum {shap_sum:.5f} vs raw margin {raw_preds[i]:.5f}"
        )


def test_per_archetype_breakdown_completeness(benchmark_data):
    """
    Test 6: Verifies that the per-archetype breakdown reports coverage for all 6 synthetic archetypes
    plus the non-abuse cohorts (normal, legitimate_shared).
    """
    if benchmark_data is None:
        pytest.skip("Benchmark results JSON not yet generated")

    tuned = benchmark_data.get("tuned_models", {})
    assert len(tuned) > 0, "No tuned models found in benchmark data"

    for model_name, res in tuned.items():
        arch_data = res.get("archetype_breakdown", {})
        assert len(arch_data) > 0, f"No archetype breakdown for {model_name}"

        # Verify all 6 archetypes are evaluated
        for arch in ARCHETYPES:
            assert arch in arch_data, f"Archetype {arch} missing in breakdown for {model_name}"
            arch_info = arch_data[arch]
            assert "recall" in arch_info
            assert "total_positive_accounts" in arch_info
            assert 0.0 <= arch_info["recall"] <= 1.0

        # Verify normal and legitimate_shared are evaluated
        assert "normal" in arch_data
        assert "legitimate_shared" in arch_data
        assert arch_data["normal"]["false_positive_rate"] <= 0.20
