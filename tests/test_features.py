"""
Unit and integration tests for the Abuse-Ring Sentinel feature engineering pipeline.
Supports execution via pytest or python3 -m unittest.
"""

from datetime import datetime
import os
import unittest
import numpy as np
import pandas as pd

from src.features.build_features import (
    compute_behavioral_features,
    compute_entity_sharing_features,
    compute_behavioral_coordination_features,
    compute_point_in_time_features,
    build_feature_pipeline,
)


class TestFeatureEngineering(unittest.TestCase):
    """Test suite for feature extraction correctness, robustness, and ground-truth isolation."""

    def setUp(self):
        """Set up mock accounts and transactions."""
        self.mock_accounts = pd.DataFrame([
            {
                "account_id": "ACC_0001",
                "created_at": "2026-07-01 10:00:00",
                "device_id": "DEV_SHARED_1",
                "ip_id": "IP_SHARED_1",
                "country": "US",
                "ring_id": "RING_001",
                "account_type": "abuse_ring",
            },
            {
                "account_id": "ACC_0002",
                "created_at": "2026-07-01 11:00:00",
                "device_id": "DEV_SHARED_1",
                "ip_id": "IP_SHARED_1",
                "country": "US",
                "ring_id": "RING_001",
                "account_type": "abuse_ring",
            },
            {
                "account_id": "ACC_0003",
                "created_at": "2026-07-05 12:00:00",
                "device_id": "DEV_UNIQUE_3",
                "ip_id": "IP_UNIQUE_3",
                "country": "GB",
                "ring_id": "",
                "account_type": "normal",
            },
        ])

        self.mock_transactions = pd.DataFrame([
            # ACC_0001 transactions
            {
                "transaction_id": "TX_001",
                "account_id": "ACC_0001",
                "timestamp": "2026-07-02 02:00:00",  # night tx (< 6am)
                "amount": 100.0,
                "merchant_id": "MERCH_1",
                "destination_id": "",
                "transaction_type": "payment",
                "status": "SUCCESS",
            },
            {
                "transaction_id": "TX_002",
                "account_id": "ACC_0001",
                "timestamp": "2026-07-02 04:00:00",
                "amount": 200.0,
                "merchant_id": "",
                "destination_id": "DEST_SHARED_1",
                "transaction_type": "transfer",
                "status": "SUCCESS",
            },
            # ACC_0002 transactions
            {
                "transaction_id": "TX_003",
                "account_id": "ACC_0002",
                "timestamp": "2026-07-02 04:30:00",
                "amount": 200.0,
                "merchant_id": "",
                "destination_id": "DEST_SHARED_1",
                "transaction_type": "transfer",
                "status": "FAILED",
            },
            # ACC_0003 has no transactions (edge case)
        ])

    def test_behavioral_features_calculation(self):
        """Test calculations of behavioral metrics including edge cases with 0 transactions."""
        ref_time = datetime(2026, 7, 10, 0, 0, 0)
        feats = compute_behavioral_features(self.mock_accounts, self.mock_transactions, reference_time=ref_time)

        self.assertEqual(len(feats), 3)
        self.assertEqual(set(feats["account_id"]), {"ACC_0001", "ACC_0002", "ACC_0003"})

        # Check ACC_0001
        f1 = feats[feats["account_id"] == "ACC_0001"].iloc[0]
        self.assertEqual(f1["transaction_count"], 2)
        self.assertEqual(f1["total_transaction_amount"], 300.0)
        self.assertEqual(f1["average_transaction_amount"], 150.0)
        self.assertEqual(f1["successful_transaction_rate"], 1.0)
        self.assertEqual(f1["failed_transaction_rate"], 0.0)
        self.assertEqual(f1["night_transaction_ratio"], 1.0)
        self.assertEqual(f1["unique_merchants"], 1)
        self.assertEqual(f1["unique_destinations"], 1)
        self.assertEqual(f1["transfer_transaction_ratio"], 0.5)

        # Check ACC_0002 (single failed tx, std should be 0.0)
        f2 = feats[feats["account_id"] == "ACC_0002"].iloc[0]
        self.assertEqual(f2["transaction_count"], 1)
        self.assertEqual(f2["failed_transaction_rate"], 1.0)
        self.assertEqual(f2["successful_transaction_rate"], 0.0)
        self.assertEqual(f2["transaction_amount_std"], 0.0)

        # Check ACC_0003 (zero transactions edge case)
        f3 = feats[feats["account_id"] == "ACC_0003"].iloc[0]
        self.assertEqual(f3["transaction_count"], 0)
        self.assertEqual(f3["total_transaction_amount"], 0.0)
        self.assertEqual(f3["average_transaction_amount"], 0.0)
        self.assertEqual(f3["failed_transaction_rate"], 0.0)

    def test_entity_sharing_features_calculation(self):
        """Test device and IP sharing count calculations."""
        feats = compute_entity_sharing_features(self.mock_accounts)

        self.assertEqual(len(feats), 3)

        f1 = feats[feats["account_id"] == "ACC_0001"].iloc[0]
        self.assertEqual(f1["accounts_sharing_device"], 1)  # ACC_0002 shares DEV_SHARED_1
        self.assertEqual(f1["accounts_sharing_ip"], 1)      # ACC_0002 shares IP_SHARED_1
        self.assertEqual(f1["device_reuse_ratio"], 1.0)
        self.assertEqual(f1["ip_reuse_ratio"], 1.0)

        f3 = feats[feats["account_id"] == "ACC_0003"].iloc[0]
        self.assertEqual(f3["accounts_sharing_device"], 0)  # Unique device
        self.assertEqual(f3["accounts_sharing_ip"], 0)      # Unique IP
        self.assertEqual(f3["device_reuse_ratio"], 0.0)
        self.assertEqual(f3["ip_reuse_ratio"], 0.0)

    def test_behavioral_coordination_features(self):
        """Test destination sharing and coordination metrics."""
        feats = compute_behavioral_coordination_features(self.mock_accounts, self.mock_transactions)

        self.assertEqual(len(feats), 3)

        # ACC_0001 and ACC_0002 share DEST_SHARED_1
        f1 = feats[feats["account_id"] == "ACC_0001"].iloc[0]
        self.assertEqual(f1["number_of_accounts_with_shared_destinations"], 1)

        f2 = feats[feats["account_id"] == "ACC_0002"].iloc[0]
        self.assertEqual(f2["number_of_accounts_with_shared_destinations"], 1)

        # ACC_0003 has no shared destinations
        f3 = feats[feats["account_id"] == "ACC_0003"].iloc[0]
        self.assertEqual(f3["number_of_accounts_with_shared_destinations"], 0)

    def test_full_pipeline_validation(self):
        """Test full pipeline on mock dataset."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_tmp = os.path.join(tmpdir, "raw")
            proc_tmp = os.path.join(tmpdir, "processed")
            os.makedirs(raw_tmp, exist_ok=True)
            self.mock_accounts.to_csv(os.path.join(raw_tmp, "accounts.csv"), index=False)
            self.mock_transactions.to_csv(os.path.join(raw_tmp, "transactions.csv"), index=False)

            df_features, df_ground_truth = build_feature_pipeline(
                raw_dir=raw_tmp,
                processed_dir=proc_tmp,
            )

            # 1. Match account count
            self.assertEqual(len(df_features), 3)
            self.assertEqual(len(df_ground_truth), 3)
            self.assertEqual(df_features["account_id"].nunique(), 3)

            # 2. No NaN / Inf
            self.assertEqual(df_features.isna().sum().sum(), 0)
            numeric_cols = [c for c in df_features.columns if c != "account_id"]
            self.assertFalse(np.isinf(df_features[numeric_cols].values).any())

            # 3. Label isolation
            self.assertNotIn("account_type", df_features.columns)
            self.assertNotIn("ring_id", df_features.columns)
            self.assertIn("account_type", df_ground_truth.columns)
            self.assertIn("ring_id", df_ground_truth.columns)

    def test_point_in_time_cutoff_enforcement(self):
        """Verify that transactions occurring after observation_cutoff are strictly excluded."""
        # Create a transaction after cutoff date (2026-07-03)
        future_tx = pd.DataFrame([
            {
                "transaction_id": "TX_FUTURE_1",
                "account_id": "ACC_0001",
                "timestamp": "2026-07-04 12:00:00",
                "amount": 9999.0,
                "merchant_id": "MERCH_FUTURE",
                "destination_id": "",
                "transaction_type": "payment",
                "status": "SUCCESS",
            }
        ])
        all_tx = pd.concat([self.mock_transactions, future_tx], ignore_index=True)

        cutoff = datetime(2026, 7, 3, 0, 0, 0)
        feats = compute_point_in_time_features(self.mock_accounts, all_tx, observation_cutoff=cutoff)

        f1 = feats[feats["account_id"] == "ACC_0001"].iloc[0]
        # Pre-cutoff ACC_0001 had 2 transactions totaling 300.0
        self.assertEqual(f1["transaction_count"], 2)
        self.assertEqual(f1["total_transaction_amount"], 300.0)
        # Account age must be calculated relative to cutoff, not now or dataset end
        # ACC_0001 created 2026-07-01 10:00:00 -> cutoff 2026-07-03 00:00:00 = 1.58 days
        self.assertAlmostEqual(f1["account_age_days"], 1.58, places=1)

        # Future account (ACC_0003 was created 2026-07-05 12:00:00) should NOT be in output
        self.assertNotIn("ACC_0003", feats["account_id"].values)

    def test_no_constant_features_in_matrix(self):
        """Verify that constant features (unique_devices_used, unique_ips_used) are absent and all have variance > 0."""
        entity_feats = compute_entity_sharing_features(self.mock_accounts)
        self.assertNotIn("unique_devices_used", entity_feats.columns)
        self.assertNotIn("unique_ips_used", entity_feats.columns)

        # Check processed dataset on disk
        features_path = "data/processed/account_features.csv"
        if os.path.exists(features_path):
            df_feats = pd.read_csv(features_path)
            num_cols = [c for c in df_feats.columns if c != "account_id"]
            self.assertEqual(len(num_cols), 24)
            stds = df_feats[num_cols].std()
            zero_var_cols = stds[stds == 0].index.tolist()
            self.assertEqual(zero_var_cols, [], f"Found zero-variance features: {zero_var_cols}")


if __name__ == "__main__":
    unittest.main()
