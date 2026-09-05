"""
Unit and Integration Tests for End-to-End System Evaluation Pipeline.
"""

import json
import os
import unittest
import numpy as np
import pandas as pd

from src.evaluation.end_to_end_eval import (
    evaluate_ring_level_detection,
    optimize_risk_threshold_on_val,
    run_ablation_study,
    run_end_to_end_evaluation,
)
from src.models.evaluate_model import compute_comprehensive_metrics
from src.models.train_model import DEFAULT_COST_FN, DEFAULT_COST_FP


class TestEndToEndEvaluation(unittest.TestCase):
    """Test suite for the End-to-End Evaluation pipeline."""

    def setUp(self):
        """Create mock prediction records strictly formatted for testing."""
        self.mock_predictions = pd.DataFrame([
            {
                "account_id": "ACC_001",
                "actual_label": 1,
                "account_type": "abuse_ring",
                "ring_id": "RING_001",
                "archetype": "INFRASTRUCTURE_LINKED",
                "final_risk_score": 75.0,
            },
            {
                "account_id": "ACC_002",
                "actual_label": 1,
                "account_type": "abuse_ring",
                "ring_id": "RING_001",
                "archetype": "INFRASTRUCTURE_LINKED",
                "final_risk_score": 65.0,
            },
            {
                "account_id": "ACC_003",
                "actual_label": 1,
                "account_type": "abuse_ring",
                "ring_id": "RING_002",
                "archetype": "DISTRIBUTED_FUNNEL",
                "final_risk_score": 20.0,
            },
            {
                "account_id": "ACC_004",
                "actual_label": 0,
                "account_type": "legitimate_shared",
                "ring_id": "",
                "archetype": "NON_ABUSE",
                "final_risk_score": 25.0,
            },
            {
                "account_id": "ACC_005",
                "actual_label": 0,
                "account_type": "normal",
                "ring_id": "",
                "archetype": "NON_ABUSE",
                "final_risk_score": 10.0,
            },
        ])

    def test_threshold_optimization_logic(self):
        """Verify threshold optimization finds minimum synthetic cost on validation data."""
        y_val = np.array([0, 0, 0, 0, 1, 1])
        # Clear separation between classes at score ~50
        val_scores = np.array([10.0, 20.0, 25.0, 30.0, 70.0, 85.0])

        best_t, best_cost = optimize_risk_threshold_on_val(
            y_val=y_val,
            val_risk_scores=val_scores,
            cost_fp=15.0,
            cost_fn=100.0,
        )

        # Optimal threshold should be between 30 and 70, achieving 0 cost
        self.assertGreater(best_t, 30.0)
        self.assertLessEqual(best_t, 70.0)
        self.assertEqual(best_cost, 0.0)

    def test_cost_calculation(self):
        """Verify synthetic cost formula: Cost = FP * 15 + FN * 100."""
        fp = 4
        fn = 2
        expected_cost = (4 * 15.0) + (2 * 100.0)  # 60 + 200 = 260.0

        actual_cost = (fp * DEFAULT_COST_FP) + (fn * DEFAULT_COST_FN)
        self.assertEqual(actual_cost, expected_cost)
        self.assertEqual(actual_cost, 260.0)

    def test_confusion_matrix_and_metrics_math(self):
        """Verify precision, recall, F1, FPR, FNR, FP, and FN calculations."""
        y_true = np.array([0, 0, 0, 0, 1, 1])
        y_probs = np.array([0.1, 0.2, 0.7, 0.2, 0.3, 0.9])  # 1 FP at 0.7, 1 FN at 0.3 with t=0.5

        metrics = compute_comprehensive_metrics(y_true, y_probs, threshold=0.5)

        self.assertEqual(metrics["true_positives"], 1)
        self.assertEqual(metrics["false_positives"], 1)
        self.assertEqual(metrics["true_negatives"], 3)
        self.assertEqual(metrics["false_negatives"], 1)

        # Precision = 1 / (1 + 1) = 0.50
        self.assertEqual(metrics["precision"], 0.50)
        # Recall = 1 / (1 + 1) = 0.50
        self.assertEqual(metrics["recall"], 0.50)
        # F1 = 0.50
        self.assertEqual(metrics["f1"], 0.50)
        # FPR = FP / (FP + TN) = 1 / 4 = 0.25
        self.assertEqual(metrics["false_positive_rate"], 0.25)
        # FNR = FN / (FN + TP) = 1 / 2 = 0.50
        self.assertEqual(metrics["false_negative_rate"], 0.50)

    def test_ring_level_detection_rules(self):
        """Verify ring detection calculation across 25%, 50%, and 75% consensus thresholds."""
        df_rings, rates = evaluate_ring_level_detection(self.mock_predictions, threshold=60.0)

        self.assertEqual(len(df_rings), 2)
        self.assertEqual(rates["total_rings_in_test"], 2)

        # RING_001 has 2 members, both >= 60.0 -> member recall = 1.0 (Detected under all rules)
        r1 = df_rings[df_rings["ring_id"] == "RING_001"].iloc[0]
        self.assertEqual(r1["ring_members_in_test"], 2)
        self.assertEqual(r1["members_flagged"], 2)
        self.assertEqual(r1["member_recall"], 1.0)
        self.assertTrue(r1["detected_50pct_rule"])

        # RING_002 has 1 member, score 20.0 < 60.0 -> member recall = 0.0 (Not detected)
        r2 = df_rings[df_rings["ring_id"] == "RING_002"].iloc[0]
        self.assertEqual(r2["ring_members_in_test"], 1)
        self.assertEqual(r2["members_flagged"], 0)
        self.assertEqual(r2["member_recall"], 0.0)
        self.assertFalse(r2["detected_50pct_rule"])

        # Overall 50% detection rate: 1 of 2 rings = 0.50 (50.0%)
        self.assertEqual(rates["detection_rate_50pct_rule"], 0.50)
        self.assertEqual(rates["detection_rate_25pct_rule"], 0.50)
        self.assertEqual(rates["detection_rate_75pct_rule"], 0.50)

    def test_no_label_leakage_in_scoring(self):
        """Verify ground-truth fields are never present in scoring inputs."""
        from src.models.train_model import load_and_prepare_dataset
        X, y, feature_cols = load_and_prepare_dataset()

        forbidden_labels = {"account_type", "ring_id", "label", "target"}
        for col in feature_cols:
            self.assertNotIn(col, forbidden_labels)
        for col in X.columns[1:]:  # drop account_id
            self.assertNotIn(col, forbidden_labels)

    def test_deterministic_evaluation_output(self):
        """Verify running evaluation produces identical deterministic metrics."""
        res1 = run_end_to_end_evaluation()
        res2 = run_end_to_end_evaluation()

        self.assertEqual(
            res1["metrics"]["thresholds"]["risk_engine_val_frozen"],
            res2["metrics"]["thresholds"]["risk_engine_val_frozen"]
        )
        self.assertEqual(
            res1["metrics"]["risk_engine_cost_optimal_metrics"]["f1"],
            res2["metrics"]["risk_engine_cost_optimal_metrics"]["f1"]
        )
        self.assertEqual(
            res1["metrics"]["ring_level_detection_rates"]["detection_rate_50pct_rule"],
            res2["metrics"]["ring_level_detection_rates"]["detection_rate_50pct_rule"]
        )

    def test_persisted_artifacts_integrity(self):
        """Verify all 4 required CSV and JSON output artifacts exist and are free of NaNs/Infs."""
        output_dir = "data/processed/risk_results"
        json_path = os.path.join(output_dir, "end_to_end_metrics.json")
        preds_path = os.path.join(output_dir, "end_to_end_predictions.csv")
        rings_path = os.path.join(output_dir, "ring_evaluation.csv")
        abl_path = os.path.join(output_dir, "ablation_results.csv")

        for path in [json_path, preds_path, rings_path, abl_path]:
            self.assertTrue(os.path.exists(path), f"Missing artifact: {path}")

        # Check JSON validity
        with open(json_path, "r") as f:
            metrics_json = json.load(f)
        self.assertIn("ml_only_test_metrics", metrics_json)
        self.assertIn("risk_engine_cost_optimal_metrics", metrics_json)
        self.assertIn("ring_level_detection_rates", metrics_json)

        # Check predictions CSV
        df_preds = pd.read_csv(preds_path)
        self.assertEqual(len(df_preds), 2000)
        self.assertEqual(df_preds.isna().sum().sum(), 0, "Found NaNs in predictions")
        self.assertFalse(np.isinf(df_preds["final_risk_score"].values).any())

        # Check ring evaluation CSV
        df_rings = pd.read_csv(rings_path)
        self.assertEqual(len(df_rings), 31)
        self.assertEqual(df_rings.isna().sum().sum(), 0)

        # Check ablation CSV
        df_abl = pd.read_csv(abl_path)
        self.assertEqual(len(df_abl), 4)
        self.assertEqual(df_abl.isna().sum().sum(), 0)


if __name__ == "__main__":
    unittest.main()
