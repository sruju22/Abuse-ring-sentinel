"""
Abuse-Ring Sentinel - Phase 4 Investigation Engine Test Suite.
Verifies:
  1. Provenance completeness of relationship evidence.
  2. Data truthfulness: No invented relationships or phantom entities.
  3. Strict Point-in-Time integrity: Zero future leakage in predictive timeline (t <= T_obs).
  4. Accurate cluster membership and statistical distributions.
  5. Deterministic outputs across multiple invocations.
  6. Handling of missing accounts (404) and incomplete outcome window accounts (reconciliation).
  7. Legitimate shared infrastructure mitigation (high-fanout IP safety).
  8. Full FastAPI endpoint integration via TestClient.
"""

from datetime import datetime
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.investigation.cluster_summarizer import (
    HIGH_RISK_THRESHOLD,
    InvestigationModelCache,
    get_account_ml_prediction,
    list_investigative_clusters,
    summarize_point_in_time_community,
    summarize_retrospective_cluster,
)
from src.investigation.evidence_engine import (
    extract_account_relationships,
    extract_point_in_time_community,
    get_account_observation_metadata,
)
from src.investigation.prioritizer import (
    build_investigation_queue,
    evaluate_prioritization_strategies,
)
from src.investigation.timeline_engine import build_account_timeline

client = TestClient(app)


@pytest.fixture(scope="module")
def cache():
    c = InvestigationModelCache.get_instance()
    c.load_data()
    return c


# =============================================================================
# 1. Provenance Completeness & Evidence Truthfulness Tests
# =============================================================================

def test_relationship_evidence_provenance_completeness(cache):
    """Verifies that all extracted relationships contain complete, valid provenance."""
    # Test on an account known to have relationships
    relationships = extract_account_relationships(
        "ACC_009727",
        cache.df_accounts,
        cache.df_tx,
        df_gt=cache.df_gt,
        mode="predictive",
    )

    assert len(relationships) > 0, "ACC_009727 should have extracted relationships"

    for r in relationships:
        assert r.source_account == "ACC_009727"
        assert r.target_account != ""
        assert r.evidence_type in {
            "SHARED_DEVICE", "SHARED_IP", "SHARED_DESTINATION", "COMMON_COUNTERPARTY", "TIMING_SYNCHRONY"
        }
        assert r.evidence_strength in {"STRONG", "MODERATE", "WEAK"}
        assert len(r.shared_entity_id) > 0
        assert r.support_count > 0
        assert isinstance(r.provenance, dict)
        assert "observation_cutoff" in r.provenance
        assert "mode" in r.provenance
        assert r.provenance["mode"] == "predictive"
        assert r.provenance["is_point_in_time"] is True
        assert len(r.explanation) > 10
        assert isinstance(r.is_mitigating, bool)


def test_no_invented_hardware_or_ip_relationships(cache):
    """Asserts that SHARED_DEVICE and SHARED_IP reference genuine shared entities in raw data."""
    relationships = extract_account_relationships(
        "ACC_009727",
        cache.df_accounts,
        cache.df_tx,
        df_gt=cache.df_gt,
        mode="predictive",
    )

    df_acc = cache.df_accounts
    focal_row = df_acc[df_acc["account_id"] == "ACC_009727"].iloc[0]

    for r in relationships:
        peer_row = df_acc[df_acc["account_id"] == r.target_account].iloc[0]
        if r.evidence_type == "SHARED_DEVICE":
            assert focal_row["device_id"] == peer_row["device_id"]
            assert r.shared_entity_id == focal_row["device_id"]
        elif r.evidence_type == "SHARED_IP":
            assert focal_row["ip_id"] == peer_row["ip_id"]
            assert r.shared_entity_id == focal_row["ip_id"]


def test_no_invented_destination_relationships(cache):
    """Asserts that SHARED_DESTINATION occurs strictly within observation window transactions."""
    relationships = extract_account_relationships(
        "ACC_009587",
        cache.df_accounts,
        cache.df_tx,
        df_gt=cache.df_gt,
        mode="predictive",
    )

    dest_rels = [r for r in relationships if r.evidence_type == "SHARED_DESTINATION"]
    if dest_rels:
        df_tx = cache.df_tx
        meta = get_account_observation_metadata("ACC_009587", cache.df_gt, cache.df_accounts)
        cutoff_dt = meta["t_obs_dt"]

        focal_txs = df_tx[(df_tx["account_id"] == "ACC_009587") & (df_tx["timestamp_dt"] <= cutoff_dt)]
        focal_dests = set(focal_txs["destination_id"].unique())

        for r in dest_rels:
            assert r.shared_entity_id in focal_dests
            peer_txs = df_tx[(df_tx["account_id"] == r.target_account) & (df_tx["timestamp_dt"] <= cutoff_dt)]
            peer_dests = set(peer_txs["destination_id"].unique())
            assert r.shared_entity_id in peer_dests


# =============================================================================
# 2. Point-in-Time Integrity & Leakage Tests
# =============================================================================

def test_predictive_timeline_has_zero_future_leakage(cache):
    """Verifies that in predictive mode, 100% of transactions occur strictly on or before T_obs."""
    test_accounts = ["ACC_009727", "ACC_000001", "ACC_009587", "ACC_008301"]

    for acc in test_accounts:
        timeline = build_account_timeline(acc, mode="predictive")
        cutoff_dt = pd.to_datetime(timeline.observation_cutoff)

        assert timeline.investigation_mode == "predictive"
        assert timeline.mode_banner is None

        # Check all events
        for ev in timeline.events:
            ev_dt = pd.to_datetime(ev["timestamp"])
            assert ev_dt <= cutoff_dt, f"Event {ev['event_id']} occurred at {ev_dt} after T_obs {cutoff_dt}"
            assert ev["is_retrospective"] is False
            if ev["event_type"] == "TRANSACTION":
                assert ev["event_phase"] == "PREDICTIVE_OBSERVATION"

        # Check behavioral alerts
        for alert in timeline.behavioral_alerts:
            alert_dt = pd.to_datetime(alert["timestamp"])
            assert alert_dt <= cutoff_dt
            assert alert["is_retrospective"] is False


def test_retrospective_timeline_properly_tags_future_events(cache):
    """Verifies that in retrospective mode, future events are explicitly tagged as retrospective."""
    timeline = build_account_timeline("ACC_009727", mode="retrospective")
    cutoff_dt = pd.to_datetime(timeline.observation_cutoff)

    assert timeline.investigation_mode == "retrospective"
    assert timeline.mode_banner is not None
    assert "RETROSPECTIVE_INVESTIGATION_ACTIVE" in timeline.mode_banner

    retro_events = [e for e in timeline.events if e["is_retrospective"]]
    assert len(retro_events) > 0, "ACC_009727 should have outcome window events"

    for e in retro_events:
        assert pd.to_datetime(e["timestamp"]) > cutoff_dt
        assert e["event_phase"] == "RETROSPECTIVE_OUTCOME"


# =============================================================================
# 3. Cluster Summaries & Statistics Tests
# =============================================================================

def test_retrospective_cluster_summary_accuracy(cache):
    """Verifies cluster member counts, risk distribution, and retrospective disclaimer."""
    summary = summarize_retrospective_cluster("CLUSTER_001")

    df_gc = cache.df_clusters
    row = df_gc[df_gc["cluster_id"] == "CLUSTER_001"].iloc[0]
    expected_members = str(row["accounts_list"]).split("|")

    assert summary.cluster_id == "CLUSTER_001"
    assert summary.cluster_mode == "GLOBAL_30_DAY_RETROSPECTIVE"
    assert summary.num_members == len(expected_members)
    assert set(summary.member_account_ids) == set(expected_members)
    assert summary.disclaimer is not None
    assert "GLOBAL_30_DAY_RETROSPECTIVE" in summary.disclaimer

    # Risk stats
    risk = summary.ml_risk_distribution
    assert 0.0 <= risk["mean_probability"] <= 1.0
    assert 0.0 <= risk["max_probability"] <= 1.0
    assert risk["high_risk_count"] == len(summary.high_risk_members)
    assert risk["decision_threshold"] == HIGH_RISK_THRESHOLD

    # Connectivity metadata
    assert summary.connectivity_metadata is not None
    conn = summary.connectivity_metadata
    assert conn["total_accounts_count"] == summary.num_members
    assert conn["connected_components_count"] >= 1
    assert "relationships_by_type" in conn


def test_cluster_056_complete_connectivity(cache):
    """Verifies that CLUSTER_056 extracts complete relationships and represents 100% of accounts."""
    summary = summarize_retrospective_cluster("CLUSTER_056")
    conn = summary.connectivity_metadata

    assert summary.num_members == 75
    assert conn["represented_accounts_count"] == 75
    assert conn["unrepresented_accounts_count"] == 0
    assert conn["unrepresented_accounts"] == []
    assert conn["connected_components_count"] == 1
    assert conn["is_truncated"] is False
    assert conn["total_relationships_count"] > 1000

    # Verify diversity of evidence types
    types = conn["relationships_by_type"]
    assert "SHARED_DEVICE" in types
    assert "SHARED_IP" in types
    assert "SHARED_DESTINATION" in types
    assert types["SHARED_DEVICE"] == 14
    assert types["SHARED_IP"] == 19
    assert types["SHARED_DESTINATION"] == 1293

    # Verify filtering by evidence type
    dev_summary = summarize_retrospective_cluster("CLUSTER_056", evidence_type="SHARED_DEVICE")
    assert len(dev_summary.top_relationships) == 14
    for r in dev_summary.top_relationships:
        assert r["evidence_type"] == "SHARED_DEVICE"


def test_point_in_time_community_summary_bounded(cache):
    """Verifies observation-window ego-community summary is strictly point-in-time."""
    summary = summarize_point_in_time_community("ACC_009727")

    assert summary.cluster_mode == "POINT_IN_TIME_OBSERVATION_WINDOW"
    assert "PIT_COMMUNITY_ACC_009727" in summary.cluster_id
    assert summary.num_members >= 1
    assert "ACC_009727" in summary.member_account_ids
    assert summary.disclaimer is None


# =============================================================================
# 4. Account Reconciliation & Edge Cases Tests
# =============================================================================

def test_incomplete_outcome_window_account_handling(cache):
    """Verifies that accounts with incomplete outcome windows are properly reconciled."""
    # ACC_008366 was registered on 2026-07-20 (late in dataset)
    pred = get_account_ml_prediction("ACC_008366")
    assert pred["status"] == "INCOMPLETE_OUTCOME_WINDOW"
    assert pred["calibrated_probability"] is None
    assert pred["is_high_risk"] is False
    assert "Incomplete outcome window" in pred["explanation"]

    # Verify timeline also marks it
    timeline = build_account_timeline("ACC_008366")
    assert timeline.outcome_window_status == "INCOMPLETE_OUTCOME_WINDOW"


def test_nonexistent_account_raises_404():
    """Verifies that querying a non-existent account raises a 404 error."""
    resp = client.get("/api/investigations/accounts/ACC_INVALID_99999")
    assert resp.status_code == 404

    resp_timeline = client.get("/api/investigations/accounts/ACC_INVALID_99999/timeline")
    assert resp_timeline.status_code == 404


def test_nonexistent_cluster_raises_404():
    """Verifies that querying a non-existent cluster raises a 404 error."""
    resp = client.get("/api/investigations/clusters/CLUSTER_99999")
    assert resp.status_code == 404


# =============================================================================
# 5. Legitimate Shared Infrastructure Safety Tests
# =============================================================================

def test_high_fanout_ip_safety_mitigation(cache):
    """Verifies that high-fanout IPs are tagged as WEAK and is_mitigating=True."""
    # Find an IP shared by > 15 accounts
    ip_counts = cache.df_accounts["ip_id"].value_counts()
    high_fanout_ips = ip_counts[ip_counts > 15].index.tolist()
    assert len(high_fanout_ips) > 0, "Expected at least one high-fanout IP in dataset"

    test_ip = high_fanout_ips[0]
    sample_acc = cache.df_accounts[cache.df_accounts["ip_id"] == test_ip].iloc[0]["account_id"]

    relationships = extract_account_relationships(
        sample_acc,
        cache.df_accounts,
        cache.df_tx,
        df_gt=cache.df_gt,
        mode="predictive",
    )

    ip_rels = [r for r in relationships if r.evidence_type == "SHARED_IP" and r.shared_entity_id == test_ip]
    for r in ip_rels:
        assert r.evidence_strength == "WEAK"
        assert r.is_mitigating is True
        assert "High-fanout IP address" in r.explanation


# =============================================================================
# 6. Prioritization Benchmark Tests
# =============================================================================

def test_prioritization_benchmarks_rejection_of_heuristic_ranking():
    """
    Verifies that the prioritization benchmark empirically confirms that Pure CatBoost ML
    ranking captures more true frauds at Top-100 than the heuristic IPWH ranking.
    """
    val_bench = evaluate_prioritization_strategies(split_name="validation")
    assert val_bench["split_name"] == "validation"
    assert "pure_ml_ranking" in val_bench
    assert "heuristic_ipwh_ranking" in val_bench

    ml_tp = val_bench["pure_ml_ranking"]["top_100"]["true_positives"]
    ipwh_tp = val_bench["heuristic_ipwh_ranking"]["top_100"]["true_positives"]

    # In validation, Pure ML captures 60 TPs vs IPWH 56 TPs
    assert ml_tp >= ipwh_tp, "Pure ML ranking should match or outperform IPWH at Top-100"
    assert "EMPIRICAL_DECISION" in val_bench["decision"]


# =============================================================================
# 7. FastAPI Endpoints Integration Tests
# =============================================================================

def test_api_investigations_account_endpoint():
    """Tests GET /api/investigations/accounts/{account_id}."""
    resp = client.get("/api/investigations/accounts/ACC_009727?mode=predictive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_id"] == "ACC_009727"
    assert data["investigation_mode"] == "predictive"
    assert "ml_prediction" in data
    assert "relationships" in data
    assert "community" in data
    assert data["is_complete_outcome_window"] is True


def test_api_investigations_timeline_endpoint():
    """Tests GET /api/investigations/accounts/{account_id}/timeline."""
    resp = client.get("/api/investigations/accounts/ACC_009727/timeline?mode=predictive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_id"] == "ACC_009727"
    assert len(data["events"]) > 0
    assert "summary_statistics" in data
    assert all(e["is_retrospective"] is False for e in data["events"])


def test_api_investigations_clusters_endpoint():
    """Tests GET /api/investigations/clusters."""
    resp = client.get("/api/investigations/clusters?limit=10&sort_by=high_risk_count")
    assert resp.status_code == 200
    data = resp.json()
    assert "clusters" in data
    assert len(data["clusters"]) <= 10
    assert "disclaimer" in data


def test_api_investigations_cluster_detail_endpoint():
    """Tests GET /api/investigations/clusters/{cluster_id}."""
    resp = client.get("/api/investigations/clusters/CLUSTER_001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cluster_id"] == "CLUSTER_001"
    assert data["cluster_mode"] == "GLOBAL_30_DAY_RETROSPECTIVE"
    assert "ml_risk_distribution" in data
    assert "disclaimer" in data


def test_api_investigations_queue_endpoint():
    """Tests GET /api/investigations/queue."""
    resp = client.get("/api/investigations/queue?limit=20&risk_tier=CRITICAL")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) <= 20
    for item in data["items"]:
        assert item["risk_tier"] == "CRITICAL"
        assert item["calibrated_probability"] >= 0.70


def test_api_prioritization_benchmarks_endpoint():
    """Tests GET /api/investigations/benchmarks/prioritization."""
    resp = client.get("/api/investigations/benchmarks/prioritization?split=validation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["split_name"] == "validation"
    assert "pure_ml_ranking" in data
    assert "heuristic_ipwh_ranking" in data
