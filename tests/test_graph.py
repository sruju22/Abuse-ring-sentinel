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
        self.assertGreaterEqual(A2A["ACC_2"]["ACC_3"]["weight"], 1.5)
        
        # ACC_4 is completely independent and acts at different times, shouldn't connect to 1, 2, or 3
        if A2A.has_node("ACC_4"):
            self.assertEqual(A2A.degree("ACC_4"), 0)

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
