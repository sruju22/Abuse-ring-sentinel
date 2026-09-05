"""
Unit and Integration Tests for the Risk Assessment & Decision Engine.
"""

import os
import unittest
import numpy as np
import pandas as pd

from src.scoring.risk_engine import (
    compute_ml_evidence,
    compute_graph_evidence,
    compute_coordination_evidence,
    compute_relationship_evidence,
    compute_composite_risk_score,
    assign_risk_level_and_action,
    generate_account_reason_codes,
    aggregate_cluster_risk_scores,
    run_risk_engine,
    DEFAULT_WEIGHTS,
    DEFAULT_THRESHOLDS,
    ACTION_MAPPING,
)


class TestRiskEngine(unittest.TestCase):
    """Comprehensive test suite for the Risk Engine."""

    def setUp(self):
        """Create clean mock feature datasets strictly without ground-truth labels."""
        self.mock_features = pd.DataFrame([
            {
                "account_id": "ACC_001",
                "average_transaction_timing_similarity": 0.95,
                "number_of_accounts_with_similar_transaction_timing": 25,
                "number_of_accounts_with_similar_amount_behavior": 1500,
                "transactions_per_active_day": 3.5,
                "number_of_accounts_with_shared_destinations": 8,
                "accounts_sharing_device": 3,
                "accounts_sharing_ip": 10,
            },
            {
                "account_id": "ACC_002",
                "average_transaction_timing_similarity": 0.30,
                "number_of_accounts_with_similar_transaction_timing": 1,
                "number_of_accounts_with_similar_amount_behavior": 200,
                "transactions_per_active_day": 1.2,
                "number_of_accounts_with_shared_destinations": 0,
                "accounts_sharing_device": 0,
                "accounts_sharing_ip": 0,
            },
            {
                "account_id": "ACC_003",
                "average_transaction_timing_similarity": 0.35,
                "number_of_accounts_with_similar_transaction_timing": 0,
                "number_of_accounts_with_similar_amount_behavior": 50,
                "transactions_per_active_day": 1.0,
                "number_of_accounts_with_shared_destinations": 1,
                "accounts_sharing_device": 1,
                "accounts_sharing_ip": 8,
            },
        ])

        self.mock_clusters = pd.DataFrame([
            {
                "cluster_id": "CLUSTER_001",
                "num_accounts": 2,
                "average_edge_strength": 1.8,
                "graph_density": 0.95,
                "accounts_list": "ACC_001|ACC_003",
            }
        ])

    def test_score_bounds_and_validity(self):
        """Verify all individual and composite scores fall strictly within [0.0, 100.0]."""
        probs = np.array([0.0, 0.45, 0.99, 1.0, -0.2, 1.5])
        ml_scores = compute_ml_evidence(probs)
        for s in ml_scores:
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 100.0)

        graph_scores = compute_graph_evidence(self.mock_features, self.mock_clusters)
        coord_scores = compute_coordination_evidence(self.mock_features)
        rel_scores = compute_relationship_evidence(self.mock_features)

        for arr in [graph_scores, coord_scores, rel_scores]:
            for s in arr:
                self.assertGreaterEqual(s, 0.0)
                self.assertLessEqual(s, 100.0)

        composite = compute_composite_risk_score(
            ml_scores=ml_scores[:3],
            graph_scores=graph_scores,
            coordination_scores=coord_scores,
            relationship_scores=rel_scores,
        )
        for s in composite:
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 100.0)

    def test_deterministic_output(self):
        """Verify that identical inputs produce identical scores across multiple runs."""
        probs = np.array([0.85, 0.10, 0.40])
        
        ml_1 = compute_ml_evidence(probs)
        ml_2 = compute_ml_evidence(probs)
        np.testing.assert_array_equal(ml_1, ml_2)

        g_1 = compute_graph_evidence(self.mock_features, self.mock_clusters)
        g_2 = compute_graph_evidence(self.mock_features, self.mock_clusters)
        np.testing.assert_array_equal(g_1, g_2)

        c_1 = compute_composite_risk_score(ml_1, g_1, g_1, g_1)
        c_2 = compute_composite_risk_score(ml_1, g_1, g_1, g_1)
        np.testing.assert_array_equal(c_1, c_2)

    def test_weights_behavior_and_normalization(self):
        """Verify customizable weights adjust composite score and auto-normalize if needed."""
        ml = np.array([100.0])
        graph = np.array([0.0])
        coord = np.array([0.0])
        rel = np.array([0.0])

        # 100% ML weight
        w_ml_only = {"ml": 1.0, "graph": 0.0, "coordination": 0.0, "relationship": 0.0}
        score = compute_composite_risk_score(ml, graph, coord, rel, weights=w_ml_only)
        self.assertEqual(score[0], 100.0)

        # 50% ML, 50% Graph
        w_half = {"ml": 0.5, "graph": 0.5, "coordination": 0.0, "relationship": 0.0}
        score_half = compute_composite_risk_score(ml, graph, coord, rel, weights=w_half)
        self.assertEqual(score_half[0], 50.0)

        # Unnormalized weights (e.g. sum to 10 instead of 1.0)
        w_unnorm = {"ml": 5.0, "graph": 5.0, "coordination": 0.0, "relationship": 0.0}
        score_unnorm = compute_composite_risk_score(ml, graph, coord, rel, weights=w_unnorm)
        self.assertEqual(score_unnorm[0], 50.0)

    def test_risk_levels_and_action_mapping(self):
        """Verify exact boundary mapping for LOW, MEDIUM, HIGH, and CRITICAL tiers."""
        test_cases = [
            (0.0, "LOW", "monitor"),
            (15.5, "LOW", "monitor"),
            (29.99, "LOW", "monitor"),
            (30.0, "MEDIUM", "enhanced monitoring"),
            (45.0, "MEDIUM", "enhanced monitoring"),
            (59.99, "MEDIUM", "enhanced monitoring"),
            (60.0, "HIGH", "human review"),
            (75.0, "HIGH", "human review"),
            (79.99, "HIGH", "human review"),
            (80.0, "CRITICAL", "priority human review"),
            (99.5, "CRITICAL", "priority human review"),
            (100.0, "CRITICAL", "priority human review"),
        ]

        for score, expected_lvl, expected_action in test_cases:
            lvl, act = assign_risk_level_and_action(score)
            self.assertEqual(lvl, expected_lvl, f"Score {score} got {lvl} instead of {expected_lvl}")
            self.assertEqual(act, expected_action, f"Score {score} got action {act} instead of {expected_action}")

    def test_ground_truth_isolation(self):
        """Verify that ground-truth labels ('ring_id', 'account_type') are never required."""
        self.assertNotIn("account_type", self.mock_features.columns)
        self.assertNotIn("ring_id", self.mock_features.columns)

        # Verify all components compute cleanly without ground truth columns
        ml = compute_ml_evidence(np.array([0.5, 0.1, 0.9]))
        graph = compute_graph_evidence(self.mock_features, self.mock_clusters)
        coord = compute_coordination_evidence(self.mock_features)
        rel = compute_relationship_evidence(self.mock_features)
        final = compute_composite_risk_score(ml, graph, coord, rel)

        self.assertEqual(len(final), len(self.mock_features))

    def test_reason_codes_generation_and_vocabulary(self):
        """Verify explainable reason codes trigger properly and contain no forbidden terms."""
        row_high = self.mock_features.iloc[0]
        reasons_high = generate_account_reason_codes(
            row=row_high,
            ml_score=90.0,
            graph_score=75.0,
            coord_score=65.0,
            rel_score=70.0,
        )

        # Expected triggers for high-risk mock row
        self.assertIn("HIGH_ML_RISK", reasons_high)
        self.assertIn("STRONG_TIMING_COORDINATION", reasons_high)
        self.assertIn("STRONG_AMOUNT_SIMILARITY", reasons_high)
        self.assertIn("DESTINATION_CONCENTRATION", reasons_high)
        self.assertIn("STRONG_GRAPH_CLUSTER", reasons_high)
        self.assertIn("SHARED_INFRASTRUCTURE", reasons_high)
        self.assertIn("HIGH_TRANSACTION_VELOCITY", reasons_high)

        # Low-risk normal mock row
        row_low = self.mock_features.iloc[1]
        reasons_low = generate_account_reason_codes(
            row=row_low,
            ml_score=5.0,
            graph_score=0.0,
            coord_score=0.0,
            rel_score=0.0,
        )
        self.assertEqual(reasons_low, "STANDARD_ACTIVITY")

        # Verify no defamatory / uncalibrated language
        for text in [reasons_high, reasons_low]:
            lower_text = text.lower()
            self.assertNotIn("fraud", lower_text)
            self.assertNotIn("scam", lower_text)
            self.assertNotIn("criminal", lower_text)

    def test_cluster_aggregation(self):
        """Verify cluster risk calculation and aggregation consistency."""
        df_acc_risk = pd.DataFrame({
            "account_id": ["ACC_001", "ACC_002", "ACC_003"],
            "final_risk_score": [80.0, 10.0, 60.0],
            "coordination_score": [70.0, 5.0, 30.0],
            "relationship_score": [60.0, 0.0, 40.0],
            "reason_codes": [
                "HIGH_ML_RISK|STRONG_TIMING_COORDINATION",
                "STANDARD_ACTIVITY",
                "SHARED_INFRASTRUCTURE",
            ],
        })

        df_cluster_res = aggregate_cluster_risk_scores(df_acc_risk, self.mock_clusters)
        self.assertEqual(len(df_cluster_res), 1)

        c_row = df_cluster_res.iloc[0]
        self.assertEqual(c_row["cluster_id"], "CLUSTER_001")
        self.assertEqual(c_row["account_count"], 2)
        # Avg of 80 and 60 = 70.0
        self.assertEqual(c_row["average_risk_score"], 70.0)
        self.assertEqual(c_row["maximum_risk_score"], 80.0)
        self.assertEqual(c_row["risk_level"], "HIGH")
        self.assertEqual(c_row["recommended_action"], "human review")
        self.assertIn("HIGH_ML_RISK", c_row["reason_codes"])
        self.assertIn("SHARED_INFRASTRUCTURE", c_row["reason_codes"])

    def test_end_to_end_pipeline_artifacts(self):
        """Verify end-to-end execution generates valid CSV outputs without NaNs or Infs."""
        results = run_risk_engine()
        df_acc = results["account_risk"]
        df_clu = results["cluster_risk"]

        # Check files exist
        self.assertTrue(os.path.exists("data/processed/risk_results/account_risk_scores.csv"))
        self.assertTrue(os.path.exists("data/processed/risk_results/cluster_risk_scores.csv"))

        # Verify account scores integrity
        self.assertEqual(len(df_acc), 10000)
        self.assertEqual(df_acc.isna().sum().sum(), 0, "Found NaNs in account risk output")
        numeric_cols = ["ml_score", "graph_score", "coordination_score", "relationship_score", "final_risk_score"]
        self.assertFalse(np.isinf(df_acc[numeric_cols].values).any(), "Found Infinite values in account risk")

        # Verify cluster scores integrity
        self.assertGreaterEqual(len(df_clu), 1)
        self.assertEqual(df_clu.isna().sum().sum(), 0, "Found NaNs in cluster risk output")


if __name__ == "__main__":
    unittest.main()
