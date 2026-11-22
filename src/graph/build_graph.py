"""
Abuse-Ring Sentinel - Graph Intelligence Pipeline.

Builds a heterogeneous entity graph and an account-to-account projection graph
using sparse candidate generation, behavioral similarity, and shared infrastructure.
Performs community detection to identify candidate coordinated abuse rings.
"""

import os
from typing import Optional, Tuple
import numpy as np
import pandas as pd
from scipy import sparse
import networkx as nx
from networkx.algorithms.community import louvain_communities


def build_heterogeneous_graph(df_accounts: pd.DataFrame, df_transactions: pd.DataFrame) -> nx.Graph:
    """
    Constructs a base heterogeneous graph representing raw observable entity relationships.
    Nodes: account, device, ip, merchant, destination.
    Edges represent usage or transaction flow.
    Strictly excludes ground-truth labels.
    """
    G = nx.Graph()

    # Add Account Nodes and Account -> Device, Account -> IP edges
    cols_acc = [c for c in ["account_id", "device_id", "ip_id"] if c in df_accounts.columns]
    for row in df_accounts[cols_acc].itertuples(index=False):
        acc = str(row[0]).strip()
        G.add_node(acc, type="account")

        if len(row) > 1:
            dev = row[1]
            if pd.notna(dev) and str(dev).strip():
                dev_str = str(dev).strip()
                if not G.has_node(dev_str):
                    G.add_node(dev_str, type="device")
                G.add_edge(acc, dev_str, type="uses_device")

        if len(row) > 2:
            ip = row[2]
            if pd.notna(ip) and str(ip).strip():
                ip_str = str(ip).strip()
                if not G.has_node(ip_str):
                    G.add_node(ip_str, type="ip")
                G.add_edge(acc, ip_str, type="uses_ip")

    # Add Counterparty Edges from Transactions (Account -> Merchant, Account -> Destination)
    cols_tx = [c for c in ["account_id", "merchant_id", "destination_id"] if c in df_transactions.columns]
    for row in df_transactions[cols_tx].itertuples(index=False):
        acc = str(row[0]).strip()
        if not G.has_node(acc):
            G.add_node(acc, type="account")

        if len(row) > 1:
            merch = row[1]
            if pd.notna(merch) and str(merch).strip():
                merch_str = str(merch).strip()
                if not G.has_node(merch_str):
                    G.add_node(merch_str, type="merchant")
                G.add_edge(acc, merch_str, type="pays_merchant")

        if len(row) > 2:
            dest = row[2]
            if pd.notna(dest) and str(dest).strip():
                dest_str = str(dest).strip()
                if not G.has_node(dest_str):
                    G.add_node(dest_str, type="destination")
                G.add_edge(acc, dest_str, type="transfers_to")

    return G


def compute_behavioral_vectors(
    df_accounts: pd.DataFrame,
    df_transactions: pd.DataFrame,
    num_bins_time: int = 720
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """
    Computes normalized temporal activity vectors and amount distribution vectors
    for all accounts in O(T) time and O(N * bins) memory.
    
    Returns:
        norm_time: (N, 720) float32 normalized smoothed temporal activity vectors
        norm_amt: (N, 6) float32 normalized amount distribution vectors
        acc_to_idx: dictionary mapping account_id to matrix row index
    """
    account_ids = df_accounts["account_id"].astype(str).tolist()
    n_accounts = len(account_ids)
    acc_to_idx = {acc: i for i, acc in enumerate(account_ids)}

    df_tx = df_transactions.copy()
    df_tx["timestamp_dt"] = pd.to_datetime(df_tx["timestamp"])

    min_time = df_tx["timestamp_dt"].min()
    max_time = df_tx["timestamp_dt"].max()
    total_seconds = max(1.0, (max_time - min_time).total_seconds())

    # Map transaction accounts to row indices
    acc_indices = df_tx["account_id"].astype(str).map(acc_to_idx).values
    valid_mask = ~np.isnan(acc_indices)
    valid_acc_idx = acc_indices[valid_mask].astype(int)

    # 1. Temporal activity matrix (binned into 720 intervals)
    time_matrix = np.zeros((n_accounts, num_bins_time), dtype=np.float32)
    t_secs = (df_tx.loc[valid_mask, "timestamp_dt"] - min_time).dt.total_seconds().values
    bin_indices = np.clip((t_secs / total_seconds * num_bins_time).astype(int), 0, num_bins_time - 1)
    np.add.at(time_matrix, (valid_acc_idx, bin_indices), 1.0)

    # Smooth temporal bursts (1D moving average [0.25, 0.5, 0.25])
    smoothed = np.empty_like(time_matrix)
    smoothed[:, 1:-1] = 0.25 * time_matrix[:, :-2] + 0.5 * time_matrix[:, 1:-1] + 0.25 * time_matrix[:, 2:]
    smoothed[:, 0] = 0.5 * time_matrix[:, 0] + 0.25 * time_matrix[:, 1]
    smoothed[:, -1] = 0.5 * time_matrix[:, -1] + 0.25 * time_matrix[:, -2]

    time_norms = np.linalg.norm(smoothed, axis=1, keepdims=True)
    time_norms[time_norms == 0] = 1.0
    norm_time = smoothed / time_norms

    # 2. Amount Distribution Matrix (6 bins)
    amt_edges = [0, 15, 35, 75, 150, 450, 2000]
    n_amt_bins = len(amt_edges) - 1
    amt_matrix = np.zeros((n_accounts, n_amt_bins), dtype=np.float32)

    raw_amts = df_tx.loc[valid_mask, "amount"].values
    amt_bins = np.digitize(raw_amts, amt_edges) - 1
    amt_bins = np.clip(amt_bins, 0, n_amt_bins - 1)
    np.add.at(amt_matrix, (valid_acc_idx, amt_bins), 1.0)

    tx_counts = np.bincount(valid_acc_idx, minlength=n_accounts).astype(np.float32)[:, None]
    tx_counts[tx_counts == 0] = 1.0
    amt_matrix = amt_matrix / tx_counts

    amt_norms = np.linalg.norm(amt_matrix, axis=1, keepdims=True)
    amt_norms[amt_norms == 0] = 1.0
    norm_amt = amt_matrix / amt_norms

    return norm_time, norm_amt, acc_to_idx


def compute_pairwise_behavioral_signals(
    df_accounts: pd.DataFrame,
    df_transactions: pd.DataFrame
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """
    Computes pairwise similarities for timing and amounts.
    Retained for testing and small-subset evaluation.
    """
    norm_time, norm_amt, acc_to_idx = compute_behavioral_vectors(df_accounts, df_transactions)
    timing_sim_matrix = norm_time @ norm_time.T
    np.fill_diagonal(timing_sim_matrix, 0.0)
    amt_sim_matrix = norm_amt @ norm_amt.T
    np.fill_diagonal(amt_sim_matrix, 0.0)
    return timing_sim_matrix, amt_sim_matrix, acc_to_idx


def build_a2a_projection_graph(
    G_base: nx.Graph,
    df_accounts: pd.DataFrame,
    df_transactions: pd.DataFrame,
    min_edge_threshold: float = 0.5
) -> nx.Graph:
    """
    Constructs an Account-to-Account weighted projection graph using sparse candidate generation
    with destination frequency-aware weighting (IDF) and support damping.

    Candidate pairs are generated from shared entities:
      - Shared Device (A_dev @ A_dev.T > 0)
      - Shared IP (A_ip @ A_ip.T > 0)
      - Coordinated Destination Funneling (shared_count >= 2 and IDF-Jaccard >= 0.20)
      - Single Concentrated Drop Destination (shared_count == 1 and IDF-Jaccard >= 0.50)

    Edge weights are formed via combination of:
      - Shared Device (+1.0)
      - Shared IP (+0.5)
      - Destination Relationship: IDF-weighted Jaccard * support_factor
          * support_factor = 1.0 if shared_destinations >= 2 (multi-target funneling)
          * support_factor = 0.35 if shared_destinations == 1 (damped collision safeguard;
            cannot exceed 0.35 alone, preventing false links unless corroborated by timing,
            amount similarity, or infrastructure)
      - High Timing Synchrony (+0.5 if >= 0.35)
      - High Amount Similarity (+0.5 if >= 0.90)
    """
    account_ids = df_accounts["account_id"].astype(str).tolist()
    n_accounts = len(account_ids)
    acc_to_idx = {acc: i for i, acc in enumerate(account_ids)}

    # Compute normalized behavioral vectors
    norm_time, norm_amt, _ = compute_behavioral_vectors(df_accounts, df_transactions)

    # -------------------------------------------------------------------------
    # Sparse Candidate Generation via Entity Projections
    # -------------------------------------------------------------------------
    # 1. Device Sharing Projection
    dev_mask = df_accounts["device_id"].notna() & (df_accounts["device_id"].astype(str).str.strip() != "")
    if dev_mask.any():
        dev_accs = df_accounts.loc[dev_mask, "account_id"].astype(str).map(acc_to_idx).values
        unique_devs = df_accounts.loc[dev_mask, "device_id"].astype(str).unique().tolist()
        dev_to_idx = {d: i for i, d in enumerate(unique_devs)}
        dev_indices = df_accounts.loc[dev_mask, "device_id"].astype(str).map(dev_to_idx).values

        A_dev = sparse.csr_matrix(
            (np.ones(len(dev_accs), dtype=np.int8), (dev_accs, dev_indices)),
            shape=(n_accounts, max(1, len(unique_devs)))
        )
        dev_shared = (A_dev @ A_dev.T).tocoo()
        dev_shared.setdiag(0)
        dev_shared.eliminate_zeros()
    else:
        dev_shared = sparse.coo_matrix((n_accounts, n_accounts), dtype=np.int8)

    # 2. IP Sharing Projection
    ip_mask = df_accounts["ip_id"].notna() & (df_accounts["ip_id"].astype(str).str.strip() != "")
    if ip_mask.any():
        ip_accs = df_accounts.loc[ip_mask, "account_id"].astype(str).map(acc_to_idx).values
        unique_ips = df_accounts.loc[ip_mask, "ip_id"].astype(str).unique().tolist()
        ip_to_idx = {ip: i for i, ip in enumerate(unique_ips)}
        ip_indices = df_accounts.loc[ip_mask, "ip_id"].astype(str).map(ip_to_idx).values

        A_ip = sparse.csr_matrix(
            (np.ones(len(ip_accs), dtype=np.int8), (ip_accs, ip_indices)),
            shape=(n_accounts, max(1, len(unique_ips)))
        )
        ip_shared = (A_ip @ A_ip.T).tocoo()
        ip_shared.setdiag(0)
        ip_shared.eliminate_zeros()
    else:
        ip_shared = sparse.coo_matrix((n_accounts, n_accounts), dtype=np.int8)

    # 3. Frequency-Aware Destination Projection (IDF-weighted Jaccard + Support Damping)
    tx_dest = df_transactions[
        df_transactions["destination_id"].notna() &
        (df_transactions["destination_id"].astype(str).str.strip() != "")
    ]
    acc_dest_pairs = tx_dest[["account_id", "destination_id"]].astype(str).drop_duplicates()
    unique_dests = acc_dest_pairs["destination_id"].unique().tolist()

    dest_candidates_found = False
    if unique_dests:
        dest_to_idx = {d: i for i, d in enumerate(unique_dests)}
        valid_dest_pairs = acc_dest_pairs[acc_dest_pairs["account_id"].isin(acc_to_idx)]

        if not valid_dest_pairs.empty:
            dest_acc_idx = valid_dest_pairs["account_id"].map(acc_to_idx).values
            dest_col_idx = valid_dest_pairs["destination_id"].map(dest_to_idx).values

            # Destination account frequency and Inverse Destination Frequency (IDF)
            # High-fanout destination accounts (frequent) get lower IDF; narrow funnel targets get higher IDF
            dest_counts = np.bincount(dest_col_idx, minlength=len(unique_dests))
            # Standard smoothed Inverse Destination Frequency (IDF): log((N+1)/(df+1)) + 1.0
            dest_idf = (np.log((n_accounts + 1.0) / (dest_counts + 1.0)) + 1.0).astype(np.float32)

            A_dest_unweighted = sparse.csr_matrix(
                (np.ones(len(dest_acc_idx), dtype=np.float32), (dest_acc_idx, dest_col_idx)),
                shape=(n_accounts, len(unique_dests))
            )
            A_dest_idf = sparse.csr_matrix(
                (dest_idf[dest_col_idx], (dest_acc_idx, dest_col_idx)),
                shape=(n_accounts, len(unique_dests))
            )

            # Intersection counts
            shared_counts = (A_dest_unweighted @ A_dest_unweighted.T).tocoo()
            shared_counts.setdiag(0)
            shared_counts.eliminate_zeros()
            upper_cnt = shared_counts.row < shared_counts.col
            r_cnt = shared_counts.row[upper_cnt]
            c_cnt = shared_counts.col[upper_cnt]
            data_cnt = shared_counts.data[upper_cnt]

            # Weighted intersection sum
            shared_idf_sum = (A_dest_idf @ A_dest_unweighted.T).tocoo()
            upper_idf = shared_idf_sum.row < shared_idf_sum.col
            data_idf = shared_idf_sum.data[upper_idf]

            acc_idf_sum = np.array(A_dest_idf.sum(axis=1)).flatten()
            idf_union = acc_idf_sum[r_cnt] + acc_idf_sum[c_cnt] - data_idf
            jacc_idf = data_idf / np.maximum(idf_union, 1e-6)

            # Candidates from destination sharing:
            # 1. Coordinated funneling: >= 2 shared destinations with IDF-Jaccard >= 0.20
            # 2. Concentrated singleton drop: == 1 shared destination with IDF-Jaccard >= 0.50
            mask_dest = ((data_cnt >= 2) & (jacc_idf >= 0.20)) | ((data_cnt == 1) & (jacc_idf >= 0.50))
            r_dest = r_cnt[mask_dest]
            c_dest = c_cnt[mask_dest]
            jacc_dest = jacc_idf[mask_dest]
            cnt_dest = data_cnt[mask_dest]
            dest_candidates_found = len(r_dest) > 0

    # Upper triangle filtering for device and IP
    upper_dev = dev_shared.row < dev_shared.col
    r_dev = dev_shared.row[upper_dev]
    c_dev = dev_shared.col[upper_dev]

    upper_ip = ip_shared.row < ip_shared.col
    r_ip = ip_shared.row[upper_ip]
    c_ip = ip_shared.col[upper_ip]

    # Combine into candidate pair dictionary: (r, c) -> [dev_score, ip_score, dest_weight]
    pair_signals: dict[tuple[int, int], list[float]] = {}
    for r, c in zip(r_dev, c_dev):
        pair_signals[(int(r), int(c))] = [1.0, 0.0, 0.0]

    for r, c in zip(r_ip, c_ip):
        k = (int(r), int(c))
        if k not in pair_signals:
            pair_signals[k] = [0.0, 0.5, 0.0]
        else:
            pair_signals[k][1] = 0.5

    if dest_candidates_found:
        for r, c, j, cnt in zip(r_dest, c_dest, jacc_dest, cnt_dest):
            k = (int(r), int(c))
            # Support damping:
            # Multi-destination sharing (cnt >= 2) gets full support (1.0).
            # Single-destination collision (cnt == 1) is damped to 0.35, ensuring a single
            # common destination ALONE can never exceed min_edge_threshold (0.50) without corroboration.
            supp = 1.0 if cnt >= 2 else 0.35
            w_dest = float(j) * supp
            if k not in pair_signals:
                pair_signals[k] = [0.0, 0.0, w_dest]
            else:
                pair_signals[k][2] = max(pair_signals[k][2], w_dest)

    A2A = nx.Graph()
    for acc in account_ids:
        A2A.add_node(acc, type="account")

    if not pair_signals:
        return A2A

    cand_list = list(pair_signals.keys())
    cand_rows = np.array([p[0] for p in cand_list], dtype=int)
    cand_cols = np.array([p[1] for p in cand_list], dtype=int)

    # Vectorized behavioral dot products for candidate pairs
    t_sims = np.sum(norm_time[cand_rows] * norm_time[cand_cols], axis=1)
    a_sims = np.sum(norm_amt[cand_rows] * norm_amt[cand_cols], axis=1)

    for idx, (r, c) in enumerate(cand_list):
        dev_score, ip_score, dest_weight = pair_signals[(r, c)]
        score = dev_score + ip_score + dest_weight

        if t_sims[idx] >= 0.35:
            score += 0.5
        if a_sims[idx] >= 0.90:
            score += 0.5

        if score >= min_edge_threshold:
            A2A.add_edge(account_ids[r], account_ids[c], weight=round(float(score), 4))

    return A2A


def extract_candidate_clusters(A2A: nx.Graph, resolution: float = 1.0) -> list[dict]:
    """
    Run Louvain community detection on the A2A graph and compute cluster statistics.
    Filters out trivial communities (size < 2).
    Deterministic sorting by cluster size descending and member account IDs.
    """
    communities = louvain_communities(A2A, weight="weight", resolution=resolution, seed=42)
    filtered = [comm for comm in communities if len(comm) >= 2]
    filtered.sort(key=lambda comm: (-len(comm), sorted(list(comm))))

    candidate_clusters = []
    for c_idx, comm in enumerate(filtered, 1):
        subgraph = A2A.subgraph(comm)

        edge_weights = [d.get("weight", 1.0) for u, v, d in subgraph.edges(data=True)]
        avg_weight = np.mean(edge_weights) if edge_weights else 0.0

        n_nodes = subgraph.number_of_nodes()
        n_edges = subgraph.number_of_edges()
        max_possible_edges = n_nodes * (n_nodes - 1) / 2
        density = n_edges / max_possible_edges if max_possible_edges > 0 else 0.0

        candidate_clusters.append({
            "cluster_id": f"CLUSTER_{c_idx:03d}",
            "num_accounts": n_nodes,
            "average_edge_strength": round(float(avg_weight), 4),
            "graph_density": round(float(density), 4),
            "accounts_list": "|".join(sorted(list(comm)))
        })

    return candidate_clusters


def build_graph_pipeline(
    raw_dir: str = "data/raw",
    processed_dir: str = "data/processed",
) -> None:
    """
    Main execution pipeline for graph intelligence.
    """
    accounts_path = os.path.join(raw_dir, "accounts.csv")
    transactions_path = os.path.join(raw_dir, "transactions.csv")
    df_accounts = pd.read_csv(accounts_path)
    df_transactions = pd.read_csv(transactions_path)

    # 1. Base Heterogeneous Graph
    G_base = build_heterogeneous_graph(df_accounts, df_transactions)
    
    node_types = {}
    for node, data in G_base.nodes(data=True):
        ntype = data.get("type", "unknown")
        node_types[ntype] = node_types.get(ntype, 0) + 1
        
    print("\n" + "=" * 70)
    print("      ABUSE-RING SENTINEL - GRAPH INTELLIGENCE SUMMARY")
    print("=" * 70)
    print("1. BASE HETEROGENEOUS GRAPH")
    print(f"Total Nodes: {G_base.number_of_nodes()}")
    print(f"Total Edges: {G_base.number_of_edges()}")
    print("Node Types:")
    for nt, count in sorted(node_types.items()):
        print(f"  - {nt}: {count}")
        
    # 2. Account-to-Account Projection Graph
    A2A = build_a2a_projection_graph(G_base, df_accounts, df_transactions, min_edge_threshold=0.5)
    print("-" * 70)
    print("2. ACCOUNT-TO-ACCOUNT PROJECTION GRAPH")
    print(f"Total Nodes (Accounts): {A2A.number_of_nodes()}")
    print(f"Total Edges (A2A Links): {A2A.number_of_edges()}")
    
    # 3. Candidate Clusters
    clusters = extract_candidate_clusters(A2A)
    df_clusters = pd.DataFrame(clusters)
    
    print("-" * 70)
    print("3. COMMUNITY DETECTION")
    print(f"Detected {len(clusters)} candidate clusters (size >= 2).")
    
    if not df_clusters.empty:
        print("\nTop Candidate Clusters:")
        print(df_clusters[["cluster_id", "num_accounts", "average_edge_strength", "graph_density"]].head(10).to_string())
        
        # Save to disk
        os.makedirs(processed_dir, exist_ok=True)
        clusters_out_path = os.path.join(processed_dir, "graph_clusters.csv")
        df_clusters.to_csv(clusters_out_path, index=False)
        print(f"\nSaved clusters to {clusters_out_path}")
    else:
        print("\nNo clusters found.")
        
    print("=" * 70)
    
    # Debugging evaluation against ground truth
    evaluate_clusters_against_ground_truth(df_clusters, df_accounts)


def evaluate_clusters_against_ground_truth(df_clusters: pd.DataFrame, df_accounts: pd.DataFrame) -> None:
    """
    For offline evaluation only: Maps detected clusters back to raw ground-truth ring_ids.
    Strictly isolated from operational inference.
    """
    if df_clusters.empty:
        return
        
    print("\n[DEBUG] CANDIDATE CLUSTER ALIGNMENT WITH GROUND TRUTH:")
    acc_to_ring = df_accounts.set_index("account_id")["ring_id"].to_dict()
    acc_to_type = df_accounts.set_index("account_id")["account_type"].to_dict()
    
    for _, row in df_clusters.head(10).iterrows():
        accounts = row["accounts_list"].split("|")
        ring_counts = {}
        type_counts = {}
        for acc in accounts:
            r = acc_to_ring.get(acc)
            if pd.notna(r) and r != "":
                ring_counts[r] = ring_counts.get(r, 0) + 1
                
            t = acc_to_type.get(acc)
            type_counts[t] = type_counts.get(t, 0) + 1
            
        print(f"  {row['cluster_id']} (size {row['num_accounts']}) -> Types: {type_counts}, Rings: {ring_counts}")


if __name__ == "__main__":
    build_graph_pipeline()
