"""
Unit and Integration Tests for Abuse-Ring Sentinel Dashboard REST API.
"""

import unittest
from fastapi.testclient import TestClient
from src.api.server import app


class TestDashboardAPI(unittest.TestCase):
    """Test suite for FastAPI backend endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_overview_endpoint(self):
        """Verify /api/overview returns valid KPIs, risk distribution, and signal stack."""
        res = self.client.get("/api/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("kpis", data)
        self.assertEqual(data["kpis"]["accounts_analyzed"], 10000)
        self.assertEqual(data["kpis"]["transactions_analyzed"], 159569)
        self.assertGreater(data["kpis"]["abuse_risk_accounts"], 0)

        self.assertIn("risk_distribution", data)
        self.assertEqual(len(data["risk_distribution"]), 4)

        self.assertIn("signal_stack", data)
        self.assertEqual(len(data["signal_stack"]), 4)

        self.assertIn("priority_investigations", data)
        self.assertGreaterEqual(len(data["priority_investigations"]), 1)

    def test_accounts_search_and_filter(self):
        """Verify /api/accounts pagination, search, and filtering."""
        res = self.client.get("/api/accounts?page=1&page_size=10")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 10000)
        self.assertEqual(len(data["items"]), 10)

        # Filter by CRITICAL
        res_crit = self.client.get("/api/accounts?risk_level=CRITICAL")
        self.assertEqual(res_crit.status_code, 200)
        data_crit = res_crit.json()
        for item in data_crit["items"]:
            self.assertEqual(item["risk_level"], "CRITICAL")
            self.assertGreaterEqual(item["final_risk_score"], 80.0)

        # Search by specific account ID
        res_search = self.client.get("/api/accounts?search=ACC_009937")
        self.assertEqual(res_search.status_code, 200)
        self.assertGreaterEqual(res_search.json()["total"], 1)

    def test_account_detail_isolation(self):
        """Verify /api/accounts/{id} returns clean data without ground-truth fields."""
        res = self.client.get("/api/accounts/ACC_009937")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["account_id"], "ACC_009937")
        self.assertIn("final_risk_score", data)
        self.assertIn("evidence_scores", data)
        self.assertIn("reasons_explained", data)
        self.assertIn("features", data)

        # Strict isolation check: ground truth keys must NOT be present in operational account payload
        self.assertNotIn("account_type", data)
        self.assertNotIn("ring_id", data)

    def test_invalid_account_id_returns_404(self):
        """Verify requesting non-existent account ID or short ID does not zero-pad and returns 404."""
        # Unpadded short ID must return 404 rather than silently mapping to ACC_000001
        res = self.client.get("/api/accounts/ACC_0001")
        self.assertEqual(res.status_code, 404)
        res_nonexistent = self.client.get("/api/accounts/NONEXISTENT_ACCOUNT")
        self.assertEqual(res_nonexistent.status_code, 404)

    def test_clusters_endpoints(self):
        """Verify /api/clusters and /api/clusters/{id} return valid graph network topology."""
        res = self.client.get("/api/clusters")
        self.assertEqual(res.status_code, 200)
        clusters = res.json()
        self.assertGreaterEqual(len(clusters), 1)

        cluster_id = clusters[0]["cluster_id"]
        res_detail = self.client.get(f"/api/clusters/{cluster_id}")
        self.assertEqual(res_detail.status_code, 200)
        data_detail = res_detail.json()

        self.assertIn("summary", data_detail)
        self.assertIn("member_accounts", data_detail)
        self.assertIn("network_graph", data_detail)
        self.assertIn("nodes", data_detail["network_graph"])
        self.assertIn("links", data_detail["network_graph"])

        # Check node types
        node_types = {n["type"] for n in data_detail["network_graph"]["nodes"]}
        self.assertIn("account", node_types)

    def test_transactions_endpoint(self):
        """Verify /api/transactions pagination, search, and filtering."""
        res = self.client.get("/api/transactions?page=1&page_size=20")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 159569)
        self.assertEqual(len(data["items"]), 20)

        # Filter by status
        res_succ = self.client.get("/api/transactions?status=SUCCESS&page_size=10")
        self.assertEqual(res_succ.status_code, 200)
        for item in res_succ.json()["items"]:
            self.assertEqual(item["status"], "SUCCESS")

    def test_models_endpoint(self):
        """Verify /api/models returns test performance and feature importances."""
        res = self.client.get("/api/models")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("baseline_metrics", data)
        self.assertIn("ml_only_metrics", data)
        self.assertIn("top_features", data)
        self.assertIn("ablation_study", data)
        self.assertIn("archetype_generalization", data)
        self.assertGreaterEqual(len(data["top_features"]), 5)

    def test_system_endpoint(self):
        """Verify /api/system returns architecture pipeline and dataset statistics."""
        res = self.client.get("/api/system")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("pipeline_architecture", data)
        self.assertIn("dataset_statistics", data)
        self.assertIn("ground_truth_isolation", data)
        self.assertEqual(data["dataset_statistics"]["total_accounts"], 10000)

    def test_enhanced_investigation_and_neighborhood_graph(self):
        """Verify /api/accounts/{id} returns factual explanations, score formula, and neighborhood graph."""
        res = self.client.get("/api/accounts/ACC_009937")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("factual_explanations", data)
        self.assertGreaterEqual(len(data["factual_explanations"]), 1)

        self.assertIn("score_formula", data)
        self.assertIn("contributions", data["score_formula"])
        self.assertEqual(len(data["score_formula"]["contributions"]), 4)

        self.assertIn("neighborhood_graph", data)
        self.assertIn("nodes", data["neighborhood_graph"])
        self.assertIn("links", data["neighborhood_graph"])

        node_types = {n["type"] for n in data["neighborhood_graph"]["nodes"]}
        self.assertIn("account", node_types)

    def test_cluster_timeline_and_typology(self):
        """Verify /api/clusters/{id} returns coordination timeline and dominant typology."""
        res = self.client.get("/api/clusters/CLUSTER_001")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("coordination_timeline", data)
        self.assertGreaterEqual(len(data["coordination_timeline"]), 1)

        self.assertIn("why_cluster_matters", data)
        self.assertIn("dominant_typology", data["why_cluster_matters"])
        self.assertIn("strongest_relationships", data["why_cluster_matters"])

    def test_audit_log_workflow(self):
        """Verify GET and POST /api/audit-log endpoint."""
        res_get = self.client.get("/api/audit-log")
        self.assertEqual(res_get.status_code, 200)
        logs = res_get.json()
        self.assertIsInstance(logs, list)

        # Post new action
        post_payload = {
            "action": "ESCALATE",
            "target": "ACC_009937",
            "notes": "Escalated for senior risk analyst review.",
            "analyst": "SOC Investigator 4",
            "severity": "HIGH",
        }
        res_post = self.client.post("/api/audit-log", json=post_payload)
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(res_post.json()["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
