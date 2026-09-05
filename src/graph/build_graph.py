"""
Abuse-Ring Sentinel - Graph Intelligence Pipeline.

Builds a heterogeneous entity graph and an account-to-account projection graph
using behavioral similarity and shared infrastructure. Performs community
detection to identify candidate coordinated abuse rings.
"""

import os
import numpy as np
import pandas as pd
import networkx as nx
from networkx.algorithms.community import louvain_communities
import itertools


def build_heterogeneous_graph(df_accounts: pd.DataFrame, df_transactions: pd.DataFrame) -> nx.Graph:
    """
    Constructs a base heterogeneous graph representing raw observable entity relationships.
    Nodes: account, device, ip, merchant, destination.
    Edges represent usage or transaction flow.
    """
    G = nx.Graph()

    # Add Account Nodes
    for _, row in df_accounts.iterrows():
        acc = row["account_id"]
        G.add_node(acc, type="account")

        # Account -> Device edge
        dev = row.get("device_id")
        if pd.notna(dev) and str(dev).strip():
            if not G.has_node(dev):
                G.add_node(dev, type="device")
            G.add_edge(acc, dev, type="uses_device")

        # Account -> IP edge
        ip = row.get("ip_id")
        if pd.notna(ip) and str(ip).strip():
            if not G.has_node(ip):
                G.add_node(ip, type="ip")
            G.add_edge(acc, ip, type="uses_ip")

    # Add Counterparty Edges from Transactions
    for _, row in df_transactions.iterrows():
        acc = row["account_id"]
        
        # Account -> Merchant edge
        merch = row.get("merchant_id")
        if pd.notna(merch) and str(merch).strip():
            if not G.has_node(merch):
                G.add_node(merch, type="merchant")
            G.add_edge(acc, merch, type="pays_merchant")

        # Account -> Destination edge
        dest = row.get("destination_id")
        if pd.notna(dest) and str(dest).strip():
            if not G.has_node(dest):
                G.add_node(dest, type="destination")
            G.add_edge(acc, dest, type="transfers_to")

    return G


def compute_pairwise_behavioral_signals(df_accounts: pd.DataFrame, df_transactions: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Compute dense pairwise similarities for timing and amounts.
    Returns:
        timing_sim_matrix: (N, N) cosine similarity of temporal burst vectors
        amt_sim_matrix: (N, N) cosine similarity of amount distribution vectors
        acc_to_idx: dictionary mapping account_id to matrix index
    """
    df_tx = df_transactions.copy()
    df_tx["timestamp_dt"] = pd.to_datetime(df_tx["timestamp"])
    
    account_ids = df_accounts["account_id"].tolist()
    n_accounts = len(account_ids)
    acc_to_idx = {acc: i for i, acc in enumerate(account_ids)}
    
    # 1. Temporal Synchrony
    num_bins_time = 720
    min_time = df_tx["timestamp_dt"].min()
    max_time = df_tx["timestamp_dt"].max()
    total_seconds = max(1.0, (max_time - min_time).total_seconds())

    time_matrix = np.zeros((n_accounts, num_bins_time), dtype=np.float64)
    for _, row in df_tx.iterrows():
        acc = row["account_id"]
        if acc in acc_to_idx:
            idx = acc_to_idx[acc]
            t_sec = (row["timestamp_dt"] - min_time).total_seconds()
            bin_idx = min(num_bins_time - 1, int((t_sec / total_seconds) * num_bins_time))
            time_matrix[idx, bin_idx] += 1.0

    # Smooth temporal bursts (1D moving average)
    kernel = np.array([0.25, 0.5, 0.25])
    smoothed_time_matrix = np.apply_along_axis(lambda m: np.convolve(m, kernel, mode="same"), axis=1, arr=time_matrix)
    time_norms = np.linalg.norm(smoothed_time_matrix, axis=1, keepdims=True)
    time_norms[time_norms == 0] = 1.0
    timing_sim_matrix = np.dot(smoothed_time_matrix / time_norms, (smoothed_time_matrix / time_norms).T)
    np.fill_diagonal(timing_sim_matrix, 0.0)

    # 2. Amount Distribution Similarity
    amt_edges = [0, 15, 35, 75, 150, 450, 2000]
    amt_matrix = np.zeros((n_accounts, len(amt_edges) - 1), dtype=np.float64)
    tx_by_acc = df_tx.groupby("account_id")
    
    for acc, idx in acc_to_idx.items():
        if acc in tx_by_acc.groups:
            sub = tx_by_acc.get_group(acc)
            hist, _ = np.histogram(sub["amount"], bins=amt_edges)
            amt_matrix[idx] = hist / len(sub)
            
    amt_norms = np.linalg.norm(amt_matrix, axis=1, keepdims=True)
    amt_norms[amt_norms == 0] = 1.0
    amt_sim_matrix = np.dot(amt_matrix / amt_norms, (amt_matrix / amt_norms).T)
    np.fill_diagonal(amt_sim_matrix, 0.0)

    return timing_sim_matrix, amt_sim_matrix, acc_to_idx


def build_a2a_projection_graph(
    G_base: nx.Graph,
    df_accounts: pd.DataFrame,
    df_transactions: pd.DataFrame,
    min_edge_threshold: float = 0.5
) -> nx.Graph:
    """
    Constructs an Account-to-Account weighted projection graph.
    Edges are formed via combination of:
    - Shared Device (+1.0)
    - Shared IP (+0.5)
    - Meaningful Shared Destination (+ Jaccard * 1.0)
    - High Timing Synchrony (+0.5 if >= 0.35)
    - High Amount Similarity (+0.5 if >= 0.90)
    """
    timing_sim, amt_sim, acc_to_idx = compute_pairwise_behavioral_signals(df_accounts, df_transactions)
    
    # Destination Sets for Jaccard
    acc_dests = {}
    for node, data in G_base.nodes(data=True):
        if data.get("type") == "account":
            neighbors = [n for n in G_base.neighbors(node) if G_base.nodes[n].get("type") == "destination"]
            acc_dests[node] = set(neighbors)
            
    # IP and Device sets
    acc_ips = {}
    acc_devs = {}
    for node, data in G_base.nodes(data=True):
        if data.get("type") == "account":
            acc_ips[node] = {n for n in G_base.neighbors(node) if G_base.nodes[n].get("type") == "ip"}
            acc_devs[node] = {n for n in G_base.neighbors(node) if G_base.nodes[n].get("type") == "device"}

    A2A = nx.Graph()
    account_ids = df_accounts["account_id"].tolist()
    
    for acc in account_ids:
        A2A.add_node(acc, type="account")

    # Construct weighted edges
    for i, acc_u in enumerate(account_ids):
        for j in range(i + 1, len(account_ids)):
            acc_v = account_ids[j]
            score = 0.0
            
            # 1. Device and IP sharing
            if len(acc_devs[acc_u].intersection(acc_devs[acc_v])) > 0:
                score += 1.0
            if len(acc_ips[acc_u].intersection(acc_ips[acc_v])) > 0:
                score += 0.5
                
            # 2. Destination Jaccard
            d_u = acc_dests[acc_u]
            d_v = acc_dests[acc_v]
            if len(d_u) > 0 and len(d_v) > 0:
                intersection = d_u.intersection(d_v)
                union = d_u.union(d_v)
                jacc = len(intersection) / len(union)
                if jacc >= 0.20:
                    score += (jacc * 1.0)
                    
            # 3. Behavioral Signals
            u_idx = acc_to_idx[acc_u]
            v_idx = acc_to_idx[acc_v]
            
            t_sim = timing_sim[u_idx, v_idx]
            if t_sim >= 0.35:
                score += 0.5
                
            a_sim = amt_sim[u_idx, v_idx]
            if a_sim >= 0.90:
                score += 0.5
                
            if score >= min_edge_threshold:
                A2A.add_edge(acc_u, acc_v, weight=score)
                
    return A2A


def extract_candidate_clusters(A2A: nx.Graph, resolution: float = 1.0) -> list[dict]:
    """
    Run Louvain community detection on the A2A graph and compute cluster statistics.
    Filters out trivial communities (size 1).
    """
    # Detect communities
    communities = louvain_communities(A2A, weight="weight", resolution=resolution, seed=42)
    
    candidate_clusters = []
    for c_idx, comm in enumerate(communities, 1):
        if len(comm) < 2:
            continue
            
        subgraph = A2A.subgraph(comm)
        
        # Calculate cluster metrics
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
        
    # Sort by size descending
    candidate_clusters.sort(key=lambda x: x["num_accounts"], reverse=True)
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
    print(f"3. COMMUNITY DETECTION")
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
    For debugging only: Maps detected clusters back to raw ground-truth ring_ids to verify scenario success.
    """
    if df_clusters.empty:
        return
        
    print("\n[DEBUG] CANDIDATE CLUSTER ALIGNMENT WITH GROUND TRUTH:")
    acc_to_ring = df_accounts.set_index("account_id")["ring_id"].to_dict()
    acc_to_type = df_accounts.set_index("account_id")["account_type"].to_dict()
    
    for _, row in df_clusters.iterrows():
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
