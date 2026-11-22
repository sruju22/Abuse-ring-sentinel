"""
Unit tests for the Graph Intelligence pipeline.
"""

import unittest
import pandas as pd
import networkx as nx

from src.graph.build_graph import (
    build_heterogeneous_graph,
    compute_pairwise_behavioral_signals,
    build_a2a_projection_graph,
    extract_candidate_clusters
)

class TestGraphIntelligence(unittest.TestCase):
    
    def setUp(self):
        self.mock_accounts = pd.DataFrame([
            {"account_id": "ACC_1", "device_id": "DEV_1", "ip_id": "IP_1"},
            {"account_id": "ACC_2", "device_id": "DEV_1", "ip_id": "IP_2"},
            {"account_id": "ACC_3", "device_id": "DEV_2", "ip_id": "IP_3"},
            {"account_id": "ACC_4", "device_id": "DEV_3", "ip_id": "IP_4"}
        ])
        
        self.mock_transactions = pd.DataFrame([
            {"account_id": "ACC_1", "merchant_id": "MERCH_1", "destination_id": "", "timestamp": "2026-07-01 10:00:00", "amount": 100},
            {"account_id": "ACC_2", "merchant_id": "", "destination_id": "DEST_1", "timestamp": "2026-07-01 10:05:00", "amount": 105},
            {"account_id": "ACC_3", "merchant_id": "", "destination_id": "DEST_1", "timestamp": "2026-07-01 10:06:00", "amount": 95},
            {"account_id": "ACC_4", "merchant_id": "MERCH_2", "destination_id": "DEST_2", "timestamp": "2026-07-15 12:00:00", "amount": 500}
        ])

    def test_build_heterogeneous_graph(self):
        G = build_heterogeneous_graph(self.mock_accounts, self.mock_transactions)
        
        # Check node presence
        self.assertTrue(G.has_node("ACC_1"))
        self.assertTrue(G.has_node("DEV_1"))
        self.assertTrue(G.has_node("MERCH_1"))
        self.assertTrue(G.has_node("DEST_1"))
        
        # Check edges
        self.assertTrue(G.has_edge("ACC_1", "DEV_1"))
        self.assertTrue(G.has_edge("ACC_2", "DEV_1"))
        self.assertFalse(G.has_edge("ACC_1", "DEV_2"))
        self.assertTrue(G.has_edge("ACC_2", "DEST_1"))
        
        # Check node types
        self.assertEqual(G.nodes["ACC_1"]["type"], "account")
        self.assertEqual(G.nodes["DEV_1"]["type"], "device")
        
    def test_compute_pairwise_behavioral_signals(self):
        t_sim, a_sim, acc_map = compute_pairwise_behavioral_signals(self.mock_accounts, self.mock_transactions)
        
        idx2 = acc_map["ACC_2"]
        idx3 = acc_map["ACC_3"]
        idx4 = acc_map["ACC_4"]
        
        # ACC_2 and ACC_3 are in the exact same hour and have very similar amounts (~100)
        self.assertGreater(t_sim[idx2, idx3], 0.8)
        self.assertGreater(a_sim[idx2, idx3], 0.8)
        
        # ACC_2 and ACC_4 are days apart with different amounts
        self.assertLess(t_sim[idx2, idx4], 0.1)
        self.assertLess(a_sim[idx2, idx4], 0.1)

    def test_build_a2a_projection_graph(self):
        G_base = build_heterogeneous_graph(self.mock_accounts, self.mock_transactions)
        A2A = build_a2a_projection_graph(G_base, self.mock_accounts, self.mock_transactions, min_edge_threshold=0.5)
        
        # ACC_1 and ACC_2 share DEV_1, so they should be connected
        self.assertTrue(A2A.has_edge("ACC_1", "ACC_2"))
        # Edge weight should be at least 1.0 (shared device) plus behavioral similarities
        self.assertGreaterEqual(A2A["ACC_1"]["ACC_2"]["weight"], 1.0)
        
        # ACC_2 and ACC_3 share DEST_1 + high timing + high amount similarity -> Should be connected
        self.assertTrue(A2A.has_edge("ACC_2", "ACC_3"))
        self.assertGreaterEqual(A2A["ACC_2"]["ACC_3"]["weight"], 1.30)
        
        # ACC_4 is completely independent and acts at different times, shouldn't connect to 1, 2, or 3
        if A2A.has_node("ACC_4"):
            self.assertEqual(A2A.degree("ACC_4"), 0)

    def test_destination_collision_does_not_create_edge(self):
        """
        Verify that two unrelated accounts sharing a single destination with disparate
        timing and amounts do NOT form an edge (single collision damping safeguard).
        """
        accounts = pd.DataFrame([
            {"account_id": "ACC_U1", "device_id": "DEV_U1", "ip_id": "IP_U1"},
            {"account_id": "ACC_U2", "device_id": "DEV_U2", "ip_id": "IP_U2"},
        ])
        transactions = pd.DataFrame([
            {"account_id": "ACC_U1", "merchant_id": "", "destination_id": "DEST_COLLISION", "timestamp": "2026-07-01 10:00:00", "amount": 25.0},
            {"account_id": "ACC_U2", "merchant_id": "", "destination_id": "DEST_COLLISION", "timestamp": "2026-07-20 23:00:00", "amount": 950.0},
        ])
        G_base = build_heterogeneous_graph(accounts, transactions)
        A2A = build_a2a_projection_graph(G_base, accounts, transactions, min_edge_threshold=0.5)

        self.assertFalse(
            A2A.has_edge("ACC_U1", "ACC_U2"),
            "Unrelated accounts sharing a single destination collision formed an unexpected edge"
        )

    def test_coordinated_funneling_creates_edge(self):
        """
        Verify that accounts funneling funds into multiple common destinations (shared_count >= 2)
        generate meaningful graph relationships even with unique devices and IPs.
        """
        accounts = pd.DataFrame([
            {"account_id": "ACC_F1", "device_id": "DEV_F1", "ip_id": "IP_F1"},
            {"account_id": "ACC_F2", "device_id": "DEV_F2", "ip_id": "IP_F2"},
        ])
        transactions = pd.DataFrame([
            {"account_id": "ACC_F1", "merchant_id": "", "destination_id": "DEST_MULE_1", "timestamp": "2026-07-05 14:00:00", "amount": 50.0},
            {"account_id": "ACC_F1", "merchant_id": "", "destination_id": "DEST_MULE_2", "timestamp": "2026-07-05 14:30:00", "amount": 50.0},
            {"account_id": "ACC_F2", "merchant_id": "", "destination_id": "DEST_MULE_1", "timestamp": "2026-07-08 11:00:00", "amount": 75.0},
            {"account_id": "ACC_F2", "merchant_id": "", "destination_id": "DEST_MULE_2", "timestamp": "2026-07-08 11:30:00", "amount": 75.0},
        ])
        G_base = build_heterogeneous_graph(accounts, transactions)
        A2A = build_a2a_projection_graph(G_base, accounts, transactions, min_edge_threshold=0.5)

        self.assertTrue(
            A2A.has_edge("ACC_F1", "ACC_F2"),
            "Coordinated multi-destination funneling failed to form a graph edge"
        )
        self.assertGreaterEqual(A2A["ACC_F1"]["ACC_F2"]["weight"], 0.50)

    def test_graph_determinism(self):
        """
        Verify that running graph construction repeatedly produces bit-for-bit identical results.
        """
        G_base = build_heterogeneous_graph(self.mock_accounts, self.mock_transactions)
        A2A_1 = build_a2a_projection_graph(G_base, self.mock_accounts, self.mock_transactions)
        A2A_2 = build_a2a_projection_graph(G_base, self.mock_accounts, self.mock_transactions)

        self.assertEqual(sorted(A2A_1.edges(data=True)), sorted(A2A_2.edges(data=True)))

        clusters_1 = extract_candidate_clusters(A2A_1)
        clusters_2 = extract_candidate_clusters(A2A_2)
        self.assertEqual(clusters_1, clusters_2)

    def test_ground_truth_label_independence(self):
        """
        Verify that passing ground-truth labels ('ring_id', 'account_type') into accounts DataFrame
        does NOT affect graph construction or leak into nodes/edges.
        """
        G_base_clean = build_heterogeneous_graph(self.mock_accounts, self.mock_transactions)
        A2A_clean = build_a2a_projection_graph(G_base_clean, self.mock_accounts, self.mock_transactions)

        mock_labeled = self.mock_accounts.copy()
        mock_labeled["ring_id"] = ["RING_001", "RING_001", "RING_002", ""]
        mock_labeled["account_type"] = ["abuse_ring", "abuse_ring", "legitimate_shared", "normal"]

        G_base_labeled = build_heterogeneous_graph(mock_labeled, self.mock_transactions)
        A2A_labeled = build_a2a_projection_graph(G_base_labeled, mock_labeled, self.mock_transactions)

        self.assertEqual(sorted(A2A_clean.edges(data=True)), sorted(A2A_labeled.edges(data=True)))

    def test_extract_candidate_clusters(self):
        # Create a mock A2A graph
        A2A = nx.Graph()
        A2A.add_edge("A", "B", weight=1.5)
        A2A.add_edge("B", "C", weight=2.0)
        # Separate cluster
        A2A.add_edge("X", "Y", weight=1.0)
        # Isolated node (size 1 community)
        A2A.add_node("Z")
        
        clusters = extract_candidate_clusters(A2A)
        self.assertEqual(len(clusters), 2)
        
        # Largest cluster should be A, B, C
        self.assertEqual(clusters[0]["num_accounts"], 3)
        self.assertEqual(clusters[1]["num_accounts"], 2)


if __name__ == "__main__":
    unittest.main()
