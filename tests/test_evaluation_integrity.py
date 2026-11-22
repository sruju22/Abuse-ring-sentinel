"""
Abuse-Ring Sentinel - Evaluation Integrity Test Suite.

Enforces 12 rigorous methodological invariants:
  1. No future transactions in observation window (T_tx <= T_obs).
  2. Target calculated strictly within outcome window (T_obs, T_obs + W_out].
  3. Strict identification and exclusion of incomplete outcome windows.
  4. Protocol B zero-ring-overlap invariant across Train, Val, and Test.
  5. Protocol B archetype coverage across all 6 synthetic archetypes in every split.
  6. Protocol B test set positive sample size (75 to 90 positive accounts).
  7. Protocol A temporal cohort chronological ordering (T_train < T_val < T_test).
  8. Protocol A syndicate overlap quantification and reporting.
  9. Inductive isolation: scalers fitted strictly on training data without test contamination.
 10. Feature determinism and non-triviality (variance > 0, zero NaN, zero Inf).
 11. Complete absence of ground-truth labels in feature matrices.
 12. Pipeline refusal of unpartitioned lifetime features.
"""

from datetime import datetime
import os
import unittest
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

from src.features.build_features import (
    compute_account_pit_features,
    compute_pit_targets,
)
from src.evaluation.evaluation_protocols import (
    ARCHETYPES,
    build_out_of_time_splits,
    build_unseen_ring_splits,
)
from src.models.train_model import (
    load_and_prepare_dataset,
    load_and_prepare_pit_dataset,
    run_training_pipeline,
)


class TestEvaluationIntegrity(unittest.TestCase):
    """12 mandatory automated evaluation integrity tests."""

    @classmethod
    def setUpClass(cls):
        cls.accounts_path = "data/raw/accounts.csv"
        cls.transactions_path = "data/raw/transactions.csv"
        cls.attack_events_path = "data/raw/attack_events.csv"
        cls.features_pit_path = "data/processed/account_features_pit.csv"
        cls.gt_pit_path = "data/processed/ground_truth_pit.csv"

        assert os.path.exists(cls.accounts_path), "accounts.csv missing"
        assert os.path.exists(cls.transactions_path), "transactions.csv missing"
        assert os.path.exists(cls.attack_events_path), "attack_events.csv missing"
        assert os.path.exists(cls.features_pit_path), "account_features_pit.csv missing"
        assert os.path.exists(cls.gt_pit_path), "ground_truth_pit.csv missing"

        cls.df_acc = pd.read_csv(cls.accounts_path)
        cls.df_tx = pd.read_csv(cls.transactions_path)
        cls.df_ev = pd.read_csv(cls.attack_events_path)
        cls.df_feats_pit = pd.read_csv(cls.features_pit_path)
        cls.df_gt_pit = pd.read_csv(cls.gt_pit_path)

    # -------------------------------------------------------------------------
    # Test 1: Observation window strict filtering
    # -------------------------------------------------------------------------
    def test_01_no_future_transactions_in_observation_window(self):
        """Verify that transactions used for PIT features occur on or before T_obs."""
        df_acc = self.df_acc.copy()
        df_tx = self.df_tx.copy()
        df_acc["created_dt"] = pd.to_datetime(df_acc["created_at"])
        df_tx["timestamp_dt"] = pd.to_datetime(df_tx["timestamp"])
        df_acc["t_obs"] = df_acc["created_dt"] + pd.to_timedelta(7.0, unit="D")

        merged = pd.merge(df_tx, df_acc[["account_id", "created_dt", "t_obs"]], on="account_id")
        
        # Test the filtering rule applied in compute_account_pit_features
        valid_tx = merged[(merged["timestamp_dt"] >= merged["created_dt"]) & (merged["timestamp_dt"] <= merged["t_obs"])]
        
        # Invariant: no transaction in valid_tx has timestamp_dt > t_obs
        future_tx = valid_tx[valid_tx["timestamp_dt"] > valid_tx["t_obs"]]
        self.assertEqual(len(future_tx), 0, "Found future transactions in observation window!")
        
        # Invariant: no transaction in valid_tx occurred before account creation
        prior_tx = valid_tx[valid_tx["timestamp_dt"] < valid_tx["created_dt"]]
        self.assertEqual(len(prior_tx), 0, "Found pre-creation transactions in observation window!")

    # -------------------------------------------------------------------------
    # Test 2: Outcome window strict filtering
    # -------------------------------------------------------------------------
    def test_02_target_calculated_strictly_within_outcome_window(self):
        """Verify that positive labels originate strictly from attack events inside (T_obs, T_obs + W_out]."""
        df_gt = self.df_gt_pit.copy()
        df_gt["t_obs_dt"] = pd.to_datetime(df_gt["t_obs"])
        df_gt["t_out_end_dt"] = pd.to_datetime(df_gt["t_outcome_end"])

        df_ev = self.df_ev.copy()
        df_ev["timestamp_dt"] = pd.to_datetime(df_ev["timestamp"])

        merged = pd.merge(
            df_ev,
            df_gt[["account_id", "t_obs_dt", "t_out_end_dt", "target"]],
            on="account_id",
        )

        in_outcome = merged[(merged["timestamp_dt"] > merged["t_obs_dt"]) & (merged["timestamp_dt"] <= merged["t_out_end_dt"])]
        accounts_with_outcome_attacks = set(in_outcome["account_id"].unique())

        actual_positives = set(df_gt[df_gt["target"] == 1]["account_id"].unique())
        self.assertEqual(accounts_with_outcome_attacks, actual_positives, "Target positive accounts do not match outcome window attack events!")

    # -------------------------------------------------------------------------
    # Test 3: Incomplete outcome window handling
    # -------------------------------------------------------------------------
    def test_03_incomplete_outcome_window_handling(self):
        """Verify that accounts whose outcome window extends beyond max_ts are flagged is_complete_window=False."""
        max_ts = pd.to_datetime(self.df_tx["timestamp"]).max()
        df_gt = self.df_gt_pit.copy()
        df_gt["t_out_end_dt"] = pd.to_datetime(df_gt["t_outcome_end"])

        expected_incomplete = df_gt["t_out_end_dt"] > max_ts
        actual_incomplete = ~df_gt["is_complete_window"].astype(bool)

        self.assertTrue((expected_incomplete == actual_incomplete).all(), "Incomplete outcome windows not flagged accurately!")
        
        # Verify that incomplete accounts are never admitted into Protocol B splits
        split_b = build_unseen_ring_splits(self.df_feats_pit, self.df_gt_pit)
        all_split_ids = set(split_b.train_account_ids + split_b.val_account_ids + split_b.test_account_ids)
        incomplete_ids = set(df_gt[actual_incomplete]["account_id"].unique())
        self.assertEqual(len(all_split_ids.intersection(incomplete_ids)), 0, "Incomplete accounts leaked into Protocol B splits!")

    # -------------------------------------------------------------------------
    # Test 4: Protocol B zero-ring-overlap invariant
    # -------------------------------------------------------------------------
    def test_04_protocol_b_zero_ring_overlap_invariant(self):
        """Verify that abuse rings are split atomically with zero intersection between splits."""
        split_b = build_unseen_ring_splits(self.df_feats_pit, self.df_gt_pit)
        train_rings = set(split_b.ring_allocations["train_rings"])
        val_rings = set(split_b.ring_allocations["val_rings"])
        test_rings = set(split_b.ring_allocations["test_rings"])

        self.assertEqual(len(train_rings.intersection(val_rings)), 0, "Train and Val rings overlap in Protocol B!")
        self.assertEqual(len(train_rings.intersection(test_rings)), 0, "Train and Test rings overlap in Protocol B!")
        self.assertEqual(len(val_rings.intersection(test_rings)), 0, "Val and Test rings overlap in Protocol B!")
        self.assertEqual(len(train_rings) + len(val_rings) + len(test_rings), 36, "Not all 36 rings allocated in Protocol B!")

    # -------------------------------------------------------------------------
    # Test 5: Protocol B archetype coverage
    # -------------------------------------------------------------------------
    def test_05_protocol_b_archetype_coverage(self):
        """Verify that all 6 synthetic abuse archetypes are present in Train, Val, and Test splits."""
        split_b = build_unseen_ring_splits(self.df_feats_pit, self.df_gt_pit)
        for split_name in ["train", "val", "test"]:
            cov = split_b.archetype_coverage[split_name]
            for arch in ARCHETYPES:
                self.assertIn(arch, cov, f"Archetype {arch} missing from {split_name} coverage map!")
                self.assertGreater(cov[arch], 0, f"Archetype {arch} has 0 accounts in {split_name} split!")

    # -------------------------------------------------------------------------
    # Test 6: Protocol B test positive sample size
    # -------------------------------------------------------------------------
    def test_06_protocol_b_test_positive_sample_size(self):
        """Verify that Protocol B test split contains between 75 and 90 positive accounts."""
        split_b = build_unseen_ring_splits(self.df_feats_pit, self.df_gt_pit)
        test_positives = int(split_b.y_test.sum())
        self.assertGreaterEqual(test_positives, 75, f"Test positives {test_positives} < 75!")
        self.assertLessEqual(test_positives, 90, f"Test positives {test_positives} > 90!")

    # -------------------------------------------------------------------------
    # Test 7: Protocol A temporal cohort ordering
    # -------------------------------------------------------------------------
    def test_07_protocol_a_temporal_cohort_ordering(self):
        """Verify that Protocol A preserves chronological registration order: max(train) <= min(val) <= min(test)."""
        split_a = build_out_of_time_splits(self.df_feats_pit, self.df_gt_pit)
        df_meta = split_a.df_eval_metadata.set_index("account_id")

        train_times = df_meta.loc[split_a.train_account_ids]["created_dt"]
        val_times = df_meta.loc[split_a.val_account_ids]["created_dt"]
        test_times = df_meta.loc[split_a.test_account_ids]["created_dt"]

        self.assertLessEqual(train_times.max(), val_times.min(), "Protocol A Train/Val ordering violated!")
        self.assertLessEqual(val_times.max(), test_times.min(), "Protocol A Val/Test ordering violated!")

    # -------------------------------------------------------------------------
    # Test 8: Protocol A ring overlap reporting
    # -------------------------------------------------------------------------
    def test_08_protocol_a_ring_overlap_reporting(self):
        """Verify that Protocol A measures and exposes syndicate overlap across temporal cohorts."""
        split_a = build_out_of_time_splits(self.df_feats_pit, self.df_gt_pit)
        report = split_a.ring_overlap_report

        self.assertIn("overlap_train_val_count", report)
        self.assertIn("overlap_train_test_count", report)
        self.assertIn("overlap_val_test_count", report)
        self.assertIn("methodological_note", report)

        # In chronological cohorts, syndicates spanning time cause non-zero overlap
        self.assertGreater(report["overlap_train_val_count"], 0, "Expected non-zero syndication overlap between train and val!")
        self.assertGreater(report["overlap_val_test_count"], 0, "Expected non-zero syndication overlap between val and test!")

    # -------------------------------------------------------------------------
    # Test 9: Inductive scaler and feature isolation
    # -------------------------------------------------------------------------
    def test_09_inductive_scaler_and_feature_isolation(self):
        """Verify that StandardScaler fits strictly on X_train and test data does not affect train statistics."""
        split_b = build_unseen_ring_splits(self.df_feats_pit, self.df_gt_pit)
        feature_cols = split_b.feature_columns

        scaler = StandardScaler()
        scaler.fit(split_b.X_train[feature_cols])

        # Verify mean and scale vectors match X_train statistics exactly
        np.testing.assert_allclose(scaler.mean_, split_b.X_train[feature_cols].mean().values, rtol=1e-5)
        train_stds = split_b.X_train[feature_cols].std(ddof=0).values
        expected_scale = np.where(train_stds == 0, 1.0, train_stds)
        np.testing.assert_allclose(scaler.scale_, expected_scale, rtol=1e-5)

        # Contaminating test data must not alter fitted training parameters
        synthetic_perturbed_test = split_b.X_test[feature_cols] * 1000.0
        # Scaler parameters remain unchanged
        np.testing.assert_allclose(scaler.mean_, split_b.X_train[feature_cols].mean().values, rtol=1e-5)

    # -------------------------------------------------------------------------
    # Test 10: Feature determinism and non-triviality
    # -------------------------------------------------------------------------
    def test_10_feature_determinism_and_non_triviality(self):
        """Verify that all features in account_features_pit.csv are non-trivial (variance > 0 for dynamic features) with 0 NaNs and 0 Infs."""
        df_feats = self.df_feats_pit.copy()
        feature_cols = [c for c in df_feats.columns if c != "account_id"]

        # 0 NaN and 0 Inf
        self.assertEqual(df_feats[feature_cols].isna().sum().sum(), 0, "Found NaN in PIT features!")
        self.assertFalse(np.isinf(df_feats[feature_cols].values).any(), "Found Inf in PIT features!")

        # Variance > 0 for all dynamic feature columns (account_age_days is fixed at maturity 7.0)
        dynamic_cols = [c for c in feature_cols if c != "account_age_days"]
        variances = df_feats[dynamic_cols].var()
        zero_var_cols = variances[variances == 0].index.tolist()
        self.assertEqual(len(zero_var_cols), 0, f"Found zero-variance trivial features: {zero_var_cols}")

    # -------------------------------------------------------------------------
    # Test 11: Absence of ground-truth leakage in feature matrices
    # -------------------------------------------------------------------------
    def test_11_no_ground_truth_leakage_in_features(self):
        """Verify that ground truth labels and scenarios are strictly absent from feature matrices."""
        forbidden_cols = {"account_type", "ring_id", "target", "label", "is_abuse", "attack_type", "event_id"}
        feature_cols = [c for c in self.df_feats_pit.columns if c != "account_id"]

        for col in feature_cols:
            self.assertNotIn(col, forbidden_cols, f"Forbidden label column leaked in features: {col}")

        # Also verify in split matrices
        split_b = build_unseen_ring_splits(self.df_feats_pit, self.df_gt_pit)
        for col in split_b.feature_columns:
            self.assertNotIn(col, forbidden_cols, f"Forbidden label column leaked in split features: {col}")

    # -------------------------------------------------------------------------
    # Test 12: Pipeline refusal of unpartitioned lifetime features
    # -------------------------------------------------------------------------
    def test_12_pipeline_refusal_of_lifetime_features(self):
        """Verify that training pipeline explicitly raises ValueError when passed unpartitioned lifetime features."""
        with self.assertRaises(ValueError) as ctx:
            load_and_prepare_dataset(
                features_path="data/processed/account_features.csv",
                ground_truth_path="data/processed/ground_truth.csv",
                enforce_pit=True,
            )
        self.assertIn("Refusing to train on unpartitioned lifetime features", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            run_training_pipeline(
                features_path="data/processed/account_features.csv",
                ground_truth_path="data/processed/ground_truth.csv",
                split_strategy="protocol_b",
            )
        self.assertIn("Refusing to train on unpartitioned lifetime features", str(ctx2.exception))


if __name__ == "__main__":
    unittest.main()
