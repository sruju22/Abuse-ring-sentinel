"""
Abuse-Ring Sentinel - Evidence-Backed Graph Investigation Engine.
Module: Explainable Relationship Evidence Engine.

Extracts verifiable, provenanced relationship evidence linking focal accounts
to peer accounts across:
  1. Shared Hardware (device_id)
  2. Shared Subnet (ip_id)
  3. Shared Destination Accounts (destination_id)
  4. Specialized Counterparties (merchant_id)
  5. Contemporaneous Burst Timing (transactions within 5 minutes)

Strictly enforces observation cutoff (T_obs) for predictive investigation.
Distinguishes strong multi-event evidence from benign high-fanout collisions
(e.g., corporate VPN, campus Wi-Fi, retail merchant).
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional
import numpy as np
import pandas as pd


@dataclass
class RelationshipEvidence:
    """
    Structured, explainable evidence record linking two accounts.
    Never assumes shared infrastructure proves fraud.
    """
    source_account: str
    target_account: str
    evidence_type: str         # SHARED_DEVICE | SHARED_IP | SHARED_DESTINATION | COMMON_COUNTERPARTY | TIMING_SYNCHRONY
    evidence_strength: str     # STRONG | MODERATE | WEAK
    shared_entity_id: str      # Exact ID (e.g., DEV_RING_14_1, IP_HOME_0001, DEST_0291)
    support_count: int         # Count of transactions, sessions, or occurrences
    provenance: dict[str, Any] # Provenance metadata (timestamps, cutoffs, window bounds)
    explanation: str           # Factual, non-accusatory narrative
    is_mitigating: bool        # True if pattern indicates benign shared infrastructure


def get_account_observation_metadata(
    account_id: str,
    df_gt: pd.DataFrame,
    df_accounts: pd.DataFrame,
) -> dict[str, Any]:
    """
    Retrieves registration and observation window boundaries for an account.
    Standardizes observation cutoff: T_obs = T_created + 7 days.
    """
    clean_id = str(account_id).strip()
    match_gt = df_gt[df_gt["account_id"] == clean_id]

    if not match_gt.empty:
        row_gt = match_gt.iloc[0]
        created_dt = pd.to_datetime(row_gt["created_at"])
        t_obs = pd.to_datetime(row_gt["t_obs"])
        is_complete = bool(row_gt.get("is_complete_window", True))
        t_outcome_end = pd.to_datetime(row_gt.get("t_outcome_end", t_obs + pd.Timedelta(days=7)))
    else:
        match_acc = df_accounts[df_accounts["account_id"] == clean_id]
        if match_acc.empty:
            raise KeyError(f"Account {clean_id} not found in accounts dataset")
        created_dt = pd.to_datetime(match_acc.iloc[0]["created_at"])
        t_obs = created_dt + pd.Timedelta(days=7)
        is_complete = True
        t_outcome_end = t_obs + pd.Timedelta(days=7)

    return {
        "account_id": clean_id,
        "created_at": created_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "created_dt": created_dt,
        "t_obs": t_obs.strftime("%Y-%m-%d %H:%M:%S"),
        "t_obs_dt": t_obs,
        "t_outcome_end": t_outcome_end.strftime("%Y-%m-%d %H:%M:%S"),
        "is_complete_window": is_complete,
        "outcome_window_status": "COMPLETE" if is_complete else "INCOMPLETE_OUTCOME_WINDOW",
    }


def extract_account_relationships(
    account_id: str,
    df_accounts: pd.DataFrame,
    df_transactions: pd.DataFrame,
    df_gt: Optional[pd.DataFrame] = None,
    mode: str = "predictive",
    custom_cutoff_dt: Optional[datetime] = None,
) -> list[RelationshipEvidence]:
    """
    Extracts all verifiable relationship evidence linking focal account to peer accounts.
    
    In 'predictive' mode (default):
      - Strictly restricts transactions to timestamp <= T_obs.
      - Restricts peer account linkages to accounts registered on or before T_obs.
      - Never accesses future transactions or post-cutoff activity.
      
    In 'retrospective' mode:
      - Uses full historical transactions and all accounts.
      - Explicitly tags provenance as retrospective.
    """
    clean_id = str(account_id).strip()
    focal_acc_match = df_accounts[df_accounts["account_id"] == clean_id]
    if focal_acc_match.empty:
        return []

    focal_row = focal_acc_match.iloc[0]
    dev_id = str(focal_row.get("device_id", "")).strip()
    ip_id = str(focal_row.get("ip_id", "")).strip()

    # Determine cutoff
    if custom_cutoff_dt is not None:
        cutoff_dt = pd.to_datetime(custom_cutoff_dt)
        is_complete = True
    elif df_gt is not None:
        obs_meta = get_account_observation_metadata(clean_id, df_gt, df_accounts)
        cutoff_dt = obs_meta["t_obs_dt"] if mode == "predictive" else pd.to_datetime("2099-01-01")
        is_complete = obs_meta["is_complete_window"]
    else:
        created_dt = pd.to_datetime(focal_row["created_at"])
        cutoff_dt = created_dt + pd.Timedelta(days=7) if mode == "predictive" else pd.to_datetime("2099-01-01")
        is_complete = True

    cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Filter transactions based on cutoff
    df_tx = df_transactions.copy()
    if "timestamp_dt" not in df_tx.columns:
        df_tx["timestamp_dt"] = pd.to_datetime(df_tx["timestamp"])

    if mode == "predictive":
        valid_tx = df_tx[df_tx["timestamp_dt"] <= cutoff_dt]
        valid_accs = df_accounts[pd.to_datetime(df_accounts["created_at"]) <= cutoff_dt]
    else:
        valid_tx = df_tx
        valid_accs = df_accounts

    focal_tx = valid_tx[valid_tx["account_id"] == clean_id]

    relationships: list[RelationshipEvidence] = []
    seen_keys: set[tuple[str, str, str]] = set()

    # -------------------------------------------------------------------------
    # 1. SHARED HARDWARE DEVICE EVIDENCE
    # -------------------------------------------------------------------------
    if dev_id and dev_id != "nan":
        peers_dev = valid_accs[
            (valid_accs["device_id"] == dev_id) & (valid_accs["account_id"] != clean_id)
        ]
        total_dev_users = len(df_accounts[df_accounts["device_id"] == dev_id])

        for _, peer in peers_dev.iterrows():
            peer_id = str(peer["account_id"]).strip()
            key = (clean_id, peer_id, f"SHARED_DEVICE_{dev_id}")
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Distinguish strong multi-account clustering from benign household
            if total_dev_users <= 4:
                strength = "STRONG"
                explanation = (
                    f"Account shares hardware device {dev_id} with {peer_id} "
                    f"({total_dev_users} total accounts on device)."
                )
                is_mitigating = False
            else:
                strength = "MODERATE"
                explanation = (
                    f"Account shares device {dev_id} with {peer_id} "
                    f"({total_dev_users} accounts observed on hardware, e.g. shared kiosk or lab computer)."
                )
                is_mitigating = False

            relationships.append(RelationshipEvidence(
                source_account=clean_id,
                target_account=peer_id,
                evidence_type="SHARED_DEVICE",
                evidence_strength=strength,
                shared_entity_id=dev_id,
                support_count=total_dev_users,
                provenance={
                    "observation_cutoff": cutoff_str,
                    "mode": mode,
                    "is_point_in_time": (mode == "predictive"),
                    "device_registration": str(peer.get("created_at")),
                },
                explanation=explanation,
                is_mitigating=is_mitigating,
            ))

    # -------------------------------------------------------------------------
    # 2. SHARED IP ADDRESS EVIDENCE
    # -------------------------------------------------------------------------
    if ip_id and ip_id != "nan":
        peers_ip = valid_accs[
            (valid_accs["ip_id"] == ip_id) & (valid_accs["account_id"] != clean_id)
        ]
        total_ip_users = len(df_accounts[df_accounts["ip_id"] == ip_id])

        # Subnet Fan-Out Safety: High-fanout IPs (> 15 accounts) are mitigated
        if total_ip_users > 15:
            ip_strength = "WEAK"
            is_mitigating_ip = True
            ip_desc = (
                f"High-fanout IP address ({total_ip_users} accounts). "
                f"Consistent with corporate VPN, public Wi-Fi, or ISP CGNAT. "
                f"Does not independently indicate malicious coordination."
            )
        elif total_ip_users <= 4:
            ip_strength = "STRONG"
            is_mitigating_ip = False
            ip_desc = (
                f"Shared low-fanout IP address {ip_id} with {len(peers_ip)} peer accounts "
                f"({total_ip_users} total accounts on IP)."
            )
        else:
            ip_strength = "MODERATE"
            is_mitigating_ip = False
            ip_desc = f"Shared residential/small-office IP {ip_id} with {total_ip_users} accounts."

        for _, peer in peers_ip.iterrows():
            peer_id = str(peer["account_id"]).strip()
            key = (clean_id, peer_id, f"SHARED_IP_{ip_id}")
            if key in seen_keys:
                continue
            seen_keys.add(key)

            relationships.append(RelationshipEvidence(
                source_account=clean_id,
                target_account=peer_id,
                evidence_type="SHARED_IP",
                evidence_strength=ip_strength,
                shared_entity_id=ip_id,
                support_count=total_ip_users,
                provenance={
                    "observation_cutoff": cutoff_str,
                    "mode": mode,
                    "is_point_in_time": (mode == "predictive"),
                    "ip_registration": str(peer.get("created_at")),
                },
                explanation=f"Shares IP {ip_id} with {peer_id}. {ip_desc}",
                is_mitigating=is_mitigating_ip,
            ))

    # -------------------------------------------------------------------------
    # 3. SHARED DESTINATION ACCOUNT EVIDENCE
    # -------------------------------------------------------------------------
    focal_dests = set(focal_tx["destination_id"].dropna().unique())
    if len(focal_dests) > 0:
        # Find peers transferring to same destinations in valid_tx
        peer_tx_dests = valid_tx[
            (valid_tx["destination_id"].isin(focal_dests)) & (valid_tx["account_id"] != clean_id)
        ]

        if not peer_tx_dests.empty:
            peer_grouped = peer_tx_dests.groupby("account_id")["destination_id"].unique()
            # Also get device and IP peers to check corroboration
            corroborated_peers = {r.target_account for r in relationships}

            for peer_id, p_dests in peer_grouped.items():
                peer_id_str = str(peer_id).strip()
                intersection_dests = focal_dests.intersection(set(p_dests))
                if not intersection_dests:
                    continue

                # Compute Jaccard on destinations
                all_p_dests = set(valid_tx[valid_tx["account_id"] == peer_id_str]["destination_id"].dropna().unique())
                union_dests = focal_dests.union(all_p_dests)
                jaccard_dest = len(intersection_dests) / max(1, len(union_dests))

                is_corroborated_by_infra = peer_id_str in corroborated_peers
                is_multi_funnel = len(intersection_dests) >= 2 and jaccard_dest >= 0.20

                # Strictly require either multi-destination funneling or corroboration by shared infra/timing
                if not (is_multi_funnel or is_corroborated_by_infra):
                    continue

                for dest in sorted(intersection_dests):
                    key = (clean_id, peer_id_str, f"SHARED_DEST_{dest}")
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    focal_cnt = int((focal_tx["destination_id"] == dest).sum())
                    peer_cnt = int((peer_tx_dests[(peer_tx_dests["account_id"] == peer_id_str) & (peer_tx_dests["destination_id"] == dest)]).shape[0])
                    total_support = focal_cnt + peer_cnt

                    dest_global_users = valid_tx[valid_tx["destination_id"] == dest]["account_id"].nunique()

                    if is_multi_funnel or is_corroborated_by_infra:
                        dest_strength = "STRONG"
                        dest_expl = (
                            f"Corroborated destination sharing ({dest}): {clean_id} ({focal_cnt} txs) "
                            f"and {peer_id_str} ({peer_cnt} txs). Jaccard overlap: {jaccard_dest:.2f}."
                        )
                    else:
                        dest_strength = "MODERATE"
                        dest_expl = (
                            f"Shared destination {dest}: {clean_id} ({focal_cnt} txs) "
                            f"and {peer_id_str} ({peer_cnt} txs)."
                        )

                    relationships.append(RelationshipEvidence(
                        source_account=clean_id,
                        target_account=peer_id_str,
                        evidence_type="SHARED_DESTINATION",
                        evidence_strength=dest_strength,
                        shared_entity_id=str(dest),
                        support_count=total_support,
                        provenance={
                            "observation_cutoff": cutoff_str,
                            "mode": mode,
                            "is_point_in_time": (mode == "predictive"),
                            "focal_tx_count": focal_cnt,
                            "peer_tx_count": peer_cnt,
                            "shared_destinations_count": len(intersection_dests),
                            "destination_jaccard": round(jaccard_dest, 4),
                        },
                        explanation=dest_expl,
                        is_mitigating=False,
                    ))

    # -------------------------------------------------------------------------
    # 4. CONTEMPORANEOUS BURST TIMING EVIDENCE
    # -------------------------------------------------------------------------
    # Check if focal account had transactions within 5 minutes (300s) of related peers
    if not focal_tx.empty:
        candidate_peer_ids = list({r.target_account for r in relationships})
        if candidate_peer_ids:
            peer_txs = valid_tx[valid_tx["account_id"].isin(candidate_peer_ids)]

            for peer_id in candidate_peer_ids:
                p_tx = peer_txs[peer_txs["account_id"] == peer_id]
                if p_tx.empty:
                    continue

                f_times = focal_tx["timestamp_dt"].values[:, None]
                p_times = p_tx["timestamp_dt"].values[None, :]
                time_diffs_sec = np.abs((f_times - p_times).astype("timedelta64[s]").astype(int))

                close_pairs = int((time_diffs_sec <= 300).sum())
                if close_pairs >= 2:
                    min_diff_sec = int(time_diffs_sec.min())
                    key = (clean_id, peer_id, "TIMING_SYNCHRONY")
                    if key not in seen_keys:
                        seen_keys.add(key)
                        relationships.append(RelationshipEvidence(
                            source_account=clean_id,
                            target_account=peer_id,
                            evidence_type="TIMING_SYNCHRONY",
                            evidence_strength="STRONG" if close_pairs >= 3 else "MODERATE",
                            shared_entity_id="BURST_WINDOW_300S",
                            support_count=close_pairs,
                            provenance={
                                "observation_cutoff": cutoff_str,
                                "mode": mode,
                                "is_point_in_time": (mode == "predictive"),
                                "min_time_delta_seconds": min_diff_sec,
                            },
                            explanation=(
                                f"Observed {close_pairs} contemporaneous transactions within 5 minutes "
                                f"between {clean_id} and {peer_id} (closest delta: {min_diff_sec}s)."
                            ),
                            is_mitigating=False,
                        ))

    return relationships


def extract_point_in_time_community(
    account_id: str,
    df_accounts: pd.DataFrame,
    df_transactions: pd.DataFrame,
    df_gt: Optional[pd.DataFrame] = None,
    max_hops: int = 2,
) -> dict[str, Any]:
    """
    Constructs an observation-window-specific connected component (ego-community)
    for the focal account, strictly using evidence available on or before T_obs.
    Never uses global 30-day Louvain clusters.
    """
    clean_id = str(account_id).strip()
    obs_meta = get_account_observation_metadata(clean_id, df_gt, df_accounts) if df_gt is not None else {
        "t_obs": "2099-01-01 00:00:00",
        "t_obs_dt": pd.to_datetime("2099-01-01"),
        "is_complete_window": True,
    }
    cutoff_dt = obs_meta["t_obs_dt"]

    # Breadth-first traversal up to max_hops using point-in-time relationships
    visited_accounts = {clean_id}
    queue = [(clean_id, 0)]
    all_evidence: list[RelationshipEvidence] = []
    edges = set()

    while queue:
        curr_acc, depth = queue.pop(0)
        if depth >= max_hops:
            continue

        rel_list = extract_account_relationships(
            curr_acc, df_accounts, df_transactions, df_gt=df_gt, mode="predictive", custom_cutoff_dt=cutoff_dt
        )

        for ev in rel_list:
            edge_key = tuple(sorted([ev.source_account, ev.target_account])) + (ev.evidence_type, ev.shared_entity_id)
            if edge_key not in edges:
                edges.add(edge_key)
                all_evidence.append(ev)

            peer = ev.target_account
            if peer not in visited_accounts and depth + 1 <= max_hops:
                visited_accounts.add(peer)
                queue.append((peer, depth + 1))

    # Compile community summary
    return {
        "focal_account": clean_id,
        "observation_cutoff": obs_meta["t_obs"],
        "community_scope": "POINT_IN_TIME_OBSERVATION_WINDOW",
        "total_members": len(visited_accounts),
        "member_accounts": sorted(list(visited_accounts)),
        "relationships_count": len(all_evidence),
        "relationships": [asdict(ev) for ev in all_evidence],
        "is_complete_outcome_window": obs_meta.get("is_complete_window", True),
    }


def extract_cluster_relationships(
    cluster_id: str,
    df_graph_clusters: pd.DataFrame,
    df_accounts: pd.DataFrame,
    df_transactions: pd.DataFrame,
    df_gt: Optional[pd.DataFrame] = None,
    mode: str = "retrospective",
) -> list[RelationshipEvidence]:
    """
    Extracts relationship evidence across all member accounts of a cluster.
    Note: Global Louvain clusters were constructed from 30-day data, so cluster-level
    inspections default to 'retrospective' mode with explicit provenance tagging.
    """
    clean_c_id = str(cluster_id).strip()
    match = df_graph_clusters[df_graph_clusters["cluster_id"] == clean_c_id]
    if match.empty:
        return []

    accounts_str = str(match.iloc[0]["accounts_list"])
    member_accs = [str(a).strip() for a in accounts_str.split("|")]

    all_evidence = []
    seen = set()

    for acc in member_accs[:20]:  # Limit to top 20 members for responsive extraction
        ev_list = extract_account_relationships(
            acc, df_accounts, df_transactions, df_gt=df_gt, mode=mode
        )
        for ev in ev_list:
            if ev.target_account in member_accs:
                pair_key = tuple(sorted([ev.source_account, ev.target_account])) + (ev.evidence_type, ev.shared_entity_id)
                if pair_key not in seen:
                    seen.add(pair_key)
                    all_evidence.append(ev)

    return all_evidence
