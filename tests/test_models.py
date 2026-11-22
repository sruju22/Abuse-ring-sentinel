"""
Unit tests for the Machine Learning baseline modeling pipeline.
"""

import os
import unittest
import numpy as np
import pandas as pd

from src.models.train_model import (
    load_and_prepare_dataset,
    split_data_stratified,
    split_data_temporal,
    train_models,
    optimize_threshold_on_val,
    run_training_pipeline,
)
from src.models.evaluate_model import (
    compute_comprehensive_metrics,
    evaluate_models_on_test,
)


class TestModelPipeline(unittest.TestCase):
    """Test suite for data preparation, model training, thresholding, and metrics."""

    def test_label_creation_and_feature_isolation(self):
        """Verify binary label creation and absence of target columns in feature matrix."""
        X, y, feature_cols = load_and_prepare_dataset()

        self.assertGreaterEqual(len(X), 100)
        self.assertEqual(len(X), len(y))

        # Binary label check (only 0 and 1)
        self.assertTrue(set(y.unique()).issubset({0, 1}))
        self.assertGreater(y.sum(), 0)

        # Ground truth labels must not be in feature columns
        self.assertNotIn("account_type", feature_cols)
        self.assertNotIn("ring_id", feature_cols)
        self.assertNotIn("account_type", X.columns[1:])  # dropping account_id
        self.assertNotIn("ring_id", X.columns[1:])

    def test_deterministic_stratified_split(self):
        """Verify deterministic splitting and preserved class proportions."""
        X, y, _ = load_and_prepare_dataset()

        splits_1 = split_data_stratified(X, y, random_state=42)
        splits_2 = split_data_stratified(X, y, random_state=42)

        # Check identical splits
        self.assertEqual(splits_1["X_train"]["account_id"].tolist(), splits_2["X_train"]["account_id"].tolist())
        self.assertEqual(splits_1["X_val"]["account_id"].tolist(), splits_2["X_val"]["account_id"].tolist())
        self.assertEqual(splits_1["X_test"]["account_id"].tolist(), splits_2["X_test"]["account_id"].tolist())

        # Check split proportions: ~60% train, ~20% val, ~20% test
        n_total = len(X)
        self.assertEqual(len(splits_1["X_train"]) + len(splits_1["X_val"]) + len(splits_1["X_test"]), n_total)
        self.assertEqual(len(splits_1["X_train"]), int(n_total * 0.60))

        # Stratified balance: each split must contain positive and negative samples
        self.assertGreater(splits_1["y_train"].sum(), 0)
        self.assertGreater(splits_1["y_val"].sum(), 0)
        self.assertGreater(splits_1["y_test"].sum(), 0)

    def test_metric_calculation_and_ranges(self):
        """Verify classification metric validity on mock outputs."""
        y_true = np.array([0, 0, 0, 0, 1, 1])
        y_probs = np.array([0.1, 0.2, 0.3, 0.8, 0.7, 0.9])

        metrics = compute_comprehensive_metrics(y_true, y_probs, threshold=0.5)

        for key in ["precision", "recall", "f1", "roc_auc", "pr_auc", "false_positive_rate", "false_negative_rate"]:
            val = metrics[key]
            self.assertGreaterEqual(val, 0.0, f"{key} below 0")
            self.assertLessEqual(val, 1.0, f"{key} above 1")

        # Check confusion matrix consistency
        tn, fp = metrics["confusion_matrix"][0]
        fn, tp = metrics["confusion_matrix"][1]
        self.assertEqual(tn + fp + fn + tp, len(y_true))

    def test_end_to_end_pipeline_and_artifacts(self):
        """Verify pipeline execution and artifact generation."""
        train_res = run_training_pipeline()
        self.assertIn("logistic_regression", train_res["models"])
        self.assertIn("random_forest", train_res["models"])

        eval_res = evaluate_models_on_test()
        self.assertIn("test", eval_res["metrics"])
        self.assertIn("predictions", eval_res)

        # Check files exist
        self.assertTrue(os.path.exists("models/logistic_regression.joblib"))
        self.assertTrue(os.path.exists("models/random_forest.joblib"))
        self.assertTrue(os.path.exists("data/processed/model_results/metrics.json"))
        self.assertTrue(os.path.exists("data/processed/model_results/confusion_matrices.json"))
        self.assertTrue(os.path.exists("data/processed/model_results/predictions.csv"))
        self.assertTrue(os.path.exists("data/processed/model_results/feature_importance.csv"))

        # Verify predictions have no NaN or Inf
        df_preds = eval_res["predictions"]
        self.assertEqual(df_preds["predicted_probability"].isna().sum(), 0)
        self.assertFalse(np.isinf(df_preds["predicted_probability"].values).any())

    def test_chronological_temporal_split(self):
        """Verify strict chronological ordering and boundary non-leakage in temporal splits."""
        X, y, _ = load_and_prepare_dataset()
        splits = split_data_temporal(X, y)

        meta = splits["metadata"]
        train_max = meta["train_time_range"][1]
        val_min = meta["val_time_range"][0]
        val_max = meta["val_time_range"][1]
        test_min = meta["test_time_range"][0]

        # Chronological boundary: train <= val <= test
        self.assertLessEqual(train_max, val_min, "Train time overlaps with val time!")
        self.assertLessEqual(val_max, test_min, "Val time overlaps with test time!")

        # All splits have accounts and positive targets
        self.assertGreater(splits["y_train"].sum(), 0)
        self.assertGreater(splits["y_val"].sum(), 0)
        self.assertGreater(splits["y_test"].sum(), 0)

        # No duplicate accounts across splits
        train_ids = set(splits["X_train"]["account_id"])
        val_ids = set(splits["X_val"]["account_id"])
        test_ids = set(splits["X_test"]["account_id"])
        self.assertEqual(len(train_ids.intersection(val_ids)), 0)
        self.assertEqual(len(train_ids.intersection(test_ids)), 0)
        self.assertEqual(len(val_ids.intersection(test_ids)), 0)

    def test_scaler_fitted_only_on_train(self):
        """Verify that StandardScaler parameters are strictly determined by training fold."""
        X, y, feature_cols = load_and_prepare_dataset()
        splits = split_data_temporal(X, y)

        X_train_mat = splits["X_train"][feature_cols]
        X_val_mat = splits["X_val"][feature_cols]

        models = train_models(X_train_mat, splits["y_train"])
        scaler = models["logistic_regression"].named_steps["scaler"]

        # Scaler mean must match X_train_mat mean, NOT full dataset or val
        expected_train_mean = X_train_mat.mean(axis=0).values
        np.testing.assert_allclose(scaler.mean_, expected_train_mean, rtol=1e-5)

        # Transforming val must NOT change scaler.mean_
        mean_before = scaler.mean_.copy()
        _ = models["logistic_regression"].predict_proba(X_val_mat)
        np.testing.assert_array_equal(scaler.mean_, mean_before)

    def test_validation_threshold_freezing_isolation(self):
        """Verify that validation thresholds are strictly frozen and applied to test data."""
        y_val = np.array([0, 0, 0, 0, 1, 1, 1])
        # Probabilities where best threshold for max F1 is 0.60
        y_val_probs = np.array([0.1, 0.2, 0.3, 0.4, 0.7, 0.8, 0.9])

        best_t, res = optimize_threshold_on_val(y_val, y_val_probs, metric_objective="max_f1")
        self.assertEqual(res["best_threshold"], best_t)

        # Applying frozen threshold to test
        y_test = np.array([0, 0, 1, 1])
        y_test_probs = np.array([0.2, 0.35, 0.65, 0.85])
        test_metrics = compute_comprehensive_metrics(y_test, y_test_probs, threshold=best_t)
        self.assertEqual(test_metrics["threshold"], best_t)
        self.assertEqual(test_metrics["true_positives"], 2)
        self.assertEqual(test_metrics["false_positives"], 0)


if __name__ == "__main__":
    unittest.main()
