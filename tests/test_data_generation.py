"""
Unit tests for synthetic dataset generator realism, determinism, and label isolation.
"""

import os
import unittest
import pandas as pd
from src.data_generation.generate_data import PRESETS, generate_synthetic_data


class TestDataGenerationRealism(unittest.TestCase):
    """Test suite for Phase 2 data generator realism requirements."""

    @classmethod
    def setUpClass(cls):
        """Load or verify generated dataset."""
        cls.accounts_path = "data/raw/accounts.csv"
        cls.transactions_path = "data/raw/transactions.csv"
        assert os.path.exists(cls.accounts_path), "accounts.csv missing"
        assert os.path.exists(cls.transactions_path), "transactions.csv missing"
        cls.df_acc = pd.read_csv(cls.accounts_path)
        cls.df_tx = pd.read_csv(cls.transactions_path)

    def test_36_predefined_rings_and_account_counts(self):
        """Verify population counts: exactly 36 rings, 450 abuse accounts, 10,000 total."""
        self.assertEqual(len(self.df_acc), 10000)
        self.assertEqual(len(self.df_acc[self.df_acc["account_type"] == "normal"]), 8300)
        self.assertEqual(len(self.df_acc[self.df_acc["account_type"] == "legitimate_shared"]), 1250)

        abuse_accounts = self.df_acc[self.df_acc["account_type"] == "abuse_ring"]
        self.assertEqual(len(abuse_accounts), 450)

        unique_rings = abuse_accounts["ring_id"].unique()
        self.assertEqual(len(unique_rings), 36)
        expected_ring_ids = {f"RING_{i:03d}" for i in range(1, 37)}
        self.assertEqual(set(unique_rings), expected_ring_ids)

    def test_overlapping_failure_rates(self):
        """Verify that normal, legitimate_shared, and abuse_ring accounts all have non-zero failure rates."""
        merged = self.df_tx.merge(self.df_acc[["account_id", "account_type"]], on="account_id")

        for atype in ["normal", "legitimate_shared", "abuse_ring"]:
            sub = merged[merged["account_type"] == atype]
            failed_count = (sub["status"] == "FAILED").sum()
            success_count = (sub["status"] == "SUCCESS").sum()
            total_count = len(sub)

            self.assertGreater(failed_count, 0, f"Account type {atype} has 0 failed transactions!")
            self.assertGreater(success_count, 0, f"Account type {atype} has 0 success transactions!")

            overall_rate = failed_count / total_count
            # Realistic rate should be between 2% and 8%
            self.assertGreaterEqual(overall_rate, 0.02, f"{atype} failure rate too low: {overall_rate:.4f}")
            self.assertLessEqual(overall_rate, 0.08, f"{atype} failure rate too high: {overall_rate:.4f}")

    def test_overlapping_transaction_types(self):
        """Verify that abuse archetypes contain overlapping payment, refund, and transfer types."""
        archetypes = [
            "INFRASTRUCTURE_LINKED",
            "DISTRIBUTED_FUNNEL",
            "SYNCHRONIZED_BURST",
            "TASK_JOB_SCAM",
            "COVER_TRAFFIC_HYBRID",
            "MIXED_PARTIAL",
        ]

        merged = self.df_tx.merge(self.df_acc[["account_id", "account_type", "ring_id"]], on="account_id")

        def get_arch(ring_id):
            if not isinstance(ring_id, str) or not ring_id.startswith("RING_"):
                return "NORMAL"
            num = int(ring_id.split("_")[1])
            return archetypes[(num - 1) % len(archetypes)]

        merged["archetype"] = merged["ring_id"].apply(get_arch)

        for arch in archetypes:
            sub = merged[merged["archetype"] == arch]
            types_present = set(sub["transaction_type"].unique())
            # Every archetype must have payment and refund cover transactions
            self.assertIn("payment", types_present, f"Archetype {arch} has no payment transactions!")
            self.assertIn("refund", types_present, f"Archetype {arch} has no refund transactions!")
            # No archetype should be 100% of a single transaction type
            dominant_ratio = (sub["transaction_type"].value_counts().max() / len(sub))
            self.assertLess(dominant_ratio, 0.90, f"Archetype {arch} is {dominant_ratio:.2%} single transaction type!")

    def test_label_isolation_in_raw_transactions(self):
        """Verify that transactions do NOT leak ground-truth ring or account_type labels."""
        self.assertNotIn("account_type", self.df_tx.columns)
        self.assertNotIn("ring_id", self.df_tx.columns)
        self.assertNotIn("is_abuse", self.df_tx.columns)
        self.assertNotIn("label", self.df_tx.columns)


if __name__ == "__main__":
    unittest.main()
