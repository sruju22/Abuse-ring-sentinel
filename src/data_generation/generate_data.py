"""
Abuse-Ring Sentinel - Scalable Realistic Synthetic Payment Data Generator.

Generates synthetic payment datasets of configurable scale (from 100-account prototypes
to 10,000+ account enterprise populations) with realistic behavioral coordination,
natural infrastructure overlap, and noise for defensive abuse ring detection.

Strictly preserves label isolation: all scenario information resides purely in metadata
(ring_id, account_type) for evaluation, without leaking into observable transaction fields.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import os
import random
from typing import Any, Optional
import numpy as np
import pandas as pd


@dataclass
class DataGenConfig:
    """Configuration container for synthetic dataset generation."""
    name: str = "scale_10k"
    num_accounts: int = 10000
    duration_days: int = 30
    abuse_ratio: float = 0.045        # ~4.5% abuse accounts (~450 accounts)
    legit_shared_ratio: float = 0.125  # ~12.5% legit shared accounts (~1,250 accounts)
    # Remaining (~83.0%) are independent normal accounts (~8,300 accounts)
    random_seed: int = 42
    start_date: datetime = datetime(2026, 7, 1, 0, 0, 0)


# Standard Preset Configurations
PRESETS = {
    "prototype_100": DataGenConfig(
        name="prototype_100",
        num_accounts=100,
        abuse_ratio=0.12,
        legit_shared_ratio=0.13,
        random_seed=42,
    ),
    "scale_10k": DataGenConfig(
        name="scale_10k",
        num_accounts=10000,
        abuse_ratio=0.045,
        legit_shared_ratio=0.125,
        random_seed=42,
    ),
}


def set_seed(seed: int = 42) -> None:
    """Set random seeds across standard library and NumPy."""
    random.seed(seed)
    np.random.seed(seed)


def sample_diurnal_hour() -> int:
    """Sample an hour of day following a natural human diurnal distribution."""
    hour_weights = [
        0.010, 0.007, 0.005, 0.005, 0.008, 0.015,  # 00:00 - 05:59 (Night)
        0.030, 0.055, 0.075, 0.080, 0.075, 0.070,  # 06:00 - 11:59 (Morning)
        0.085, 0.080, 0.075, 0.070, 0.065, 0.065,  # 12:00 - 17:59 (Afternoon)
        0.070, 0.065, 0.055, 0.040, 0.025, 0.015,  # 18:00 - 23:59 (Evening)
    ]
    prob = np.array(hour_weights, dtype=np.float64)
    prob /= prob.sum()
    return int(np.random.choice(24, p=prob))


def generate_synthetic_data(
    config: Optional[DataGenConfig] = None,
    output_dir: str = "data/raw",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate synthetic payment dataset of configurable scale.
    """
    if config is None:
        config = PRESETS["scale_10k"]

    set_seed(config.random_seed)
    abuse_noise_rng = random.Random(config.random_seed + 12345)

    accounts: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []
    attack_events: list[dict[str, Any]] = []

    start_date = config.start_date
    duration_days = config.duration_days
    end_date = start_date + timedelta(days=duration_days)

    total_accounts = config.num_accounts
    num_abuse = int(total_accounts * config.abuse_ratio)
    num_legit_shared = int(total_accounts * config.legit_shared_ratio)
    num_normal = total_accounts - num_abuse - num_legit_shared

    # Scale pool sizes dynamically with account population
    num_merchants = max(40, int(total_accounts * 0.05))
    num_destinations = max(50, int(total_accounts * 0.08))
    all_merchants = [f"MERCH_{i:04d}" for i in range(1, num_merchants + 1)]
    all_destinations = [f"DEST_{i:04d}" for i in range(1, num_destinations + 1)]
    all_countries = ["US", "GB", "IN", "CA", "DE", "SG", "AU", "FR", "NL", "BR"]

    account_idx = 1
    tx_idx = 1

    # -------------------------------------------------------------------------
    # 1. NORMAL INDEPENDENT ACCOUNTS (~83-85% of population)
    # -------------------------------------------------------------------------
    # Large independent device and IP space with 5-10% natural ISP/public collision
    max_normal_dev = int(num_normal * 0.90)
    max_normal_ip = int(num_normal * 0.85)

    for _ in range(num_normal):
        acc_id = f"ACC_{account_idx:06d}"
        account_idx += 1

        created_offset = random.uniform(0.1, duration_days * 0.6)
        created_at = start_date + timedelta(days=created_offset)

        dev_num = random.randint(1, max_normal_dev)
        ip_num = random.randint(1, max_normal_ip)
        device_id = f"DEV_N_{dev_num:05d}"
        ip_id = f"IP_N_{ip_num:05d}"
        country = random.choice(all_countries)

        accounts.append({
            "account_id": acc_id,
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": device_id,
            "ip_id": ip_id,
            "country": country,
            "ring_id": "",
            "account_type": "normal",
        })

        # Generate 7 to 25 organic transactions per normal account (mean ~14)
        num_tx = random.randint(7, 25)
        for _ in range(num_tx):
            tx_day = random.uniform(created_offset + 0.05, duration_days - 0.05)
            h = sample_diurnal_hour()
            m = random.randint(0, 59)
            s = random.randint(0, 59)
            tx_time = start_date + timedelta(days=int(tx_day), hours=h, minutes=m, seconds=s)
            if tx_time > end_date:
                tx_time = end_date - timedelta(minutes=random.randint(1, 120))

            # Organic amount: gamma distribution ($5 to $400, median ~$50)
            amt = float(np.clip(np.random.gamma(shape=2.5, scale=22.0), 5.0, 450.0))

            tx_type = random.choices(
                ["payment", "p2p", "transfer", "cashout", "refund"],
                weights=[0.62, 0.20, 0.12, 0.04, 0.02],
            )[0]

            merch_id = random.choice(all_merchants) if tx_type in ["payment", "refund"] else ""
            dest_id = random.choice(all_destinations) if tx_type in ["p2p", "transfer"] else ""
            status = "FAILED" if random.random() < 0.045 else "SUCCESS"

            transactions.append({
                "transaction_id": f"TX_{tx_idx:08d}",
                "account_id": acc_id,
                "timestamp": tx_time.strftime("%Y-%m-%d %H:%M:%S"),
                "amount": round(amt, 2),
                "merchant_id": merch_id,
                "destination_id": dest_id,
                "transaction_type": tx_type,
                "status": status,
            })
            tx_idx += 1

    # -------------------------------------------------------------------------
    # 2. LEGITIMATE SHARED GROUPS (~12-13% of population)
    # -------------------------------------------------------------------------
    # Structured into:
    #  - Family Households (2-4 accounts, shared home IP, 1-2 devices)
    #  - Corporate Offices / Businesses (5-15 accounts, shared office IP, shared workstation pool)
    #  - University Campuses / Coworking Hubs (10-30 accounts, shared public IP, individual devices)
    # -------------------------------------------------------------------------
    legit_shared_allocated = 0
    group_counter = 1

    while legit_shared_allocated < num_legit_shared:
        group_type = random.choices(["household", "office", "campus"], weights=[0.55, 0.30, 0.15])[0]

        if group_type == "household":
            group_size = min(random.randint(2, 4), num_legit_shared - legit_shared_allocated)
            g_ip = f"IP_HOME_{group_counter:04d}"
            g_devs = [f"DEV_HOME_{group_counter:04d}_{d}" for d in range(1, max(2, group_size - 1))]
        elif group_type == "office":
            group_size = min(random.randint(5, 15), num_legit_shared - legit_shared_allocated)
            g_ip = f"IP_OFFICE_{group_counter:04d}"
            g_devs = [f"DEV_OFFICE_{group_counter:04d}_{d}" for d in range(1, max(3, group_size // 2))]
        else:  # campus / coworking
            group_size = min(random.randint(10, 30), num_legit_shared - legit_shared_allocated)
            g_ip = f"IP_CAMPUS_{group_counter:04d}"
            g_devs = [f"DEV_CAMPUS_{group_counter:04d}_{d}" for d in range(1, group_size + 1)]

        group_country = random.choice(all_countries)
        base_created_offset = random.uniform(0.1, duration_days * 0.5)

        for member_i in range(group_size):
            acc_id = f"ACC_{account_idx:06d}"
            account_idx += 1
            legit_shared_allocated += 1

            member_created = start_date + timedelta(days=base_created_offset + random.uniform(0.0, 5.0))
            member_dev = random.choice(g_devs)

            accounts.append({
                "account_id": acc_id,
                "created_at": member_created.strftime("%Y-%m-%d %H:%M:%S"),
                "device_id": member_dev,
                "ip_id": g_ip,
                "country": group_country,
                "ring_id": "",
                "account_type": "legitimate_shared",
            })

            # Organic independent transactions (normal shopping behavior despite shared network)
            num_tx = random.randint(8, 26)
            for _ in range(num_tx):
                tx_day = random.uniform(base_created_offset + 0.1, duration_days - 0.05)
                h = sample_diurnal_hour()
                m = random.randint(0, 59)
                s = random.randint(0, 59)
                tx_time = start_date + timedelta(days=int(tx_day), hours=h, minutes=m, seconds=s)
                if tx_time > end_date:
                    tx_time = end_date - timedelta(minutes=random.randint(1, 120))

                amt = float(np.clip(np.random.gamma(shape=2.4, scale=23.0), 5.0, 420.0))
                tx_type = random.choices(
                    ["payment", "p2p", "transfer", "cashout", "refund"],
                    weights=[0.65, 0.18, 0.12, 0.03, 0.02],
                )[0]

                merch_id = random.choice(all_merchants) if tx_type in ["payment", "refund"] else ""
                dest_id = random.choice(all_destinations) if tx_type in ["p2p", "transfer"] else ""
                status = "FAILED" if random.random() < 0.04 else "SUCCESS"

                transactions.append({
                    "transaction_id": f"TX_{tx_idx:08d}",
                    "account_id": acc_id,
                    "timestamp": tx_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "amount": round(amt, 2),
                    "merchant_id": merch_id,
                    "destination_id": dest_id,
                    "transaction_type": tx_type,
                    "status": status,
                })
                tx_idx += 1

        group_counter += 1

    # -------------------------------------------------------------------------
    # 3. ABUSE RINGS (~3.5-5% of population across varied sizes & archetypes)
    # -------------------------------------------------------------------------
    # Sizes: Small (4-8), Medium (9-20), Large (21-50)
    # Archetypes:
    #   1. INFRASTRUCTURE_LINKED: Shared device/IP with automated micro-cashouts
    #   2. DISTRIBUTED_FUNNEL: 100% unique IPs/devices funneling to tight destination accounts
    #   3. SYNCHRONIZED_BURST: Disparate entities executing in tight multi-minute temporal bursts
    #   4. TASK_JOB_SCAM: Coordinated tiered deposits with rapid settlement transfers
    #   5. COVER_TRAFFIC_HYBRID: Organic payments mixed with scripted cashout batches
    #   6. MIXED_PARTIAL: Partial infrastructure reuse and staggered operational activation
    # -------------------------------------------------------------------------
    abuse_allocated = 0
    ring_idx = 1
    archetypes = [
        "INFRASTRUCTURE_LINKED",
        "DISTRIBUTED_FUNNEL",
        "SYNCHRONIZED_BURST",
        "TASK_JOB_SCAM",
        "COVER_TRAFFIC_HYBRID",
        "MIXED_PARTIAL",
    ]

    while abuse_allocated < num_abuse:
        remaining_abuse = num_abuse - abuse_allocated
        # Pick ring size distribution: ~60% small, 30% medium, 10% large
        size_tier = random.choices(["small", "medium", "large"], weights=[0.58, 0.32, 0.10])[0]

        if size_tier == "small":
            ring_size = min(random.randint(4, 8), remaining_abuse)
        elif size_tier == "medium":
            ring_size = min(random.randint(9, 20), remaining_abuse)
        else:
            ring_size = min(random.randint(21, 50), remaining_abuse)

        if ring_size < 3:
            ring_size = remaining_abuse

        ring_id = f"RING_{ring_idx:03d}"
        archetype = archetypes[(ring_idx - 1) % len(archetypes)]
        ring_idx += 1

        # Common attributes for ring
        ring_country = random.choice(all_countries)
        base_creation_day = random.uniform(2.0, duration_days * 0.4)
        activation_day = base_creation_day + random.uniform(3.0, 8.0)

        # Dedicated destination accounts for funneling / scam settling
        ring_destinations = random.sample(all_destinations, k=min(len(all_destinations), max(2, ring_size // 4)))
        ring_merchants = random.sample(all_merchants, k=min(len(all_merchants), max(2, ring_size // 3)))

        # Infrastructure settings based on archetype
        if archetype == "INFRASTRUCTURE_LINKED":
            r_ips = [f"IP_RING_{ring_idx}_{i}" for i in range(1, max(2, ring_size // 3))]
            r_devs = [f"DEV_RING_{ring_idx}_{i}" for i in range(1, max(2, ring_size // 3))]
        elif archetype == "DISTRIBUTED_FUNNEL":
            # 100% unique IPs and devices (evades IP/device linking completely)
            r_ips = [f"IP_DIS_{ring_idx}_{i}" for i in range(1, ring_size + 1)]
            r_devs = [f"DEV_DIS_{ring_idx}_{i}" for i in range(1, ring_size + 1)]
        elif archetype == "MIXED_PARTIAL":
            # 50% shared, 50% unique
            r_ips = [f"IP_MIX_{ring_idx}_{1}"] * (ring_size // 2) + [f"IP_MIX_{ring_idx}_{i}" for i in range(2, ring_size - (ring_size // 2) + 2)]
            r_devs = [f"DEV_MIX_{ring_idx}_{1}"] * (ring_size // 2) + [f"DEV_MIX_{ring_idx}_{i}" for i in range(2, ring_size - (ring_size // 2) + 2)]
        else:
            # Diverse/cloud proxies
            r_ips = [f"IP_R_{ring_idx}_{i}" for i in range(1, ring_size + 1)]
            r_devs = [f"DEV_R_{ring_idx}_{i}" for i in range(1, ring_size + 1)]

        ring_accounts = []
        ring_acc_fail_rates = {}
        for i in range(ring_size):
            acc_id = f"ACC_{account_idx:06d}"
            account_idx += 1
            abuse_allocated += 1

            # Registration timestamps
            if archetype in ["SYNCHRONIZED_BURST", "INFRASTRUCTURE_LINKED"]:
                acc_created = start_date + timedelta(days=base_creation_day, minutes=random.randint(1, 45))
            else:
                acc_created = start_date + timedelta(days=base_creation_day + random.uniform(0.0, 4.0))

            dev_id = r_devs[i % len(r_devs)]
            ip_id = r_ips[i % len(r_ips)]

            accounts.append({
                "account_id": acc_id,
                "created_at": acc_created.strftime("%Y-%m-%d %H:%M:%S"),
                "device_id": dev_id,
                "ip_id": ip_id,
                "country": ring_country,
                "ring_id": ring_id,
                "account_type": "abuse_ring",
            })
            ring_accounts.append((acc_id, acc_created))
            ring_acc_fail_rates[acc_id] = abuse_noise_rng.uniform(0.025, 0.075)

        # ---------------------------------------------------------------------
        # Generate Ring Transaction Activity by Archetype
        # ---------------------------------------------------------------------
        if archetype == "INFRASTRUCTURE_LINKED":
            # Cover retail payments followed by clustered micro-cashouts
            for acc_id, acc_created in ring_accounts:
                f_rate = ring_acc_fail_rates.get(acc_id, 0.05)
                # 3-6 cover retail payments
                for _ in range(random.randint(3, 6)):
                    t_time = acc_created + timedelta(days=random.uniform(0.5, 3.0), hours=sample_diurnal_hour(), minutes=random.randint(0, 59))
                    amt = float(np.clip(np.random.gamma(shape=2.0, scale=20.0), 10.0, 150.0))
                    m_choice = random.choice(ring_merchants)
                    noise_p = abuse_noise_rng.random()
                    if noise_p < 0.04:
                        tx_t = "refund"
                        m_id = m_choice
                        d_id = ""
                    elif noise_p < 0.12:
                        tx_t = "transfer"
                        m_id = ""
                        d_id = abuse_noise_rng.choice(ring_destinations)
                    else:
                        tx_t = "payment"
                        m_id = m_choice
                        d_id = ""
                    status = "FAILED" if abuse_noise_rng.random() < f_rate else "SUCCESS"
                    transactions.append({
                        "transaction_id": f"TX_{tx_idx:08d}",
                        "account_id": acc_id,
                        "timestamp": t_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "amount": round(amt, 2),
                        "merchant_id": m_id,
                        "destination_id": d_id,
                        "transaction_type": tx_t,
                        "status": status,
                    })
                    tx_idx += 1

                # Clustered rapid micro-cashouts on shared infrastructure
                for _ in range(random.randint(4, 9)):
                    cashout_time = start_date + timedelta(days=activation_day, hours=14, minutes=random.randint(0, 50))
                    c_amt = round(random.uniform(18.0, 32.0), 2)
                    m_choice = random.choice(ring_merchants)
                    status = "FAILED" if abuse_noise_rng.random() < f_rate else "SUCCESS"
                    tx_id_str = f"TX_{tx_idx:08d}"
                    transactions.append({
                        "transaction_id": tx_id_str,
                        "account_id": acc_id,
                        "timestamp": cashout_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "amount": c_amt,
                        "merchant_id": m_choice,
                        "destination_id": "",
                        "transaction_type": "cashout",
                        "status": status,
                    })
                    attack_events.append({
                        "event_id": f"EV_{len(attack_events)+1:08d}",
                        "transaction_id": tx_id_str,
                        "account_id": acc_id,
                        "timestamp": cashout_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "attack_type": "micro_cashout_burst",
                        "ring_id": ring_id,
                    })
                    tx_idx += 1

        elif archetype == "DISTRIBUTED_FUNNEL":
            # Unique IPs/devices, all funneling structured funds into narrow destinations
            for acc_id, acc_created in ring_accounts:
                f_rate = ring_acc_fail_rates.get(acc_id, 0.05)
                num_tx = random.randint(8, 16)
                for tx_step in range(num_tx):
                    t_time = start_date + timedelta(days=activation_day + (tx_step * 0.8), hours=sample_diurnal_hour(), minutes=random.randint(0, 59))
                    if t_time > end_date:
                        t_time = end_date - timedelta(hours=random.randint(1, 24))

                    amt = round(random.uniform(38.0, 85.0), 2)
                    dest = random.choice(ring_destinations)
                    orig_type = "p2p" if random.random() < 0.65 else "transfer"
                    noise_p = abuse_noise_rng.random()
                    if noise_p < 0.20:
                        tx_t = "payment"
                        m_id = abuse_noise_rng.choice(all_merchants)
                        d_id = ""
                    elif noise_p < 0.23:
                        tx_t = "refund"
                        m_id = abuse_noise_rng.choice(all_merchants)
                        d_id = ""
                    else:
                        tx_t = orig_type
                        m_id = ""
                        d_id = dest
                    status = "FAILED" if abuse_noise_rng.random() < f_rate else "SUCCESS"
                    tx_id_str = f"TX_{tx_idx:08d}"
                    transactions.append({
                        "transaction_id": tx_id_str,
                        "account_id": acc_id,
                        "timestamp": t_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "amount": amt,
                        "merchant_id": m_id,
                        "destination_id": d_id,
                        "transaction_type": tx_t,
                        "status": status,
                    })
                    if tx_t == orig_type:
                        attack_events.append({
                            "event_id": f"EV_{len(attack_events)+1:08d}",
                            "transaction_id": tx_id_str,
                            "account_id": acc_id,
                            "timestamp": t_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "attack_type": "destination_funnel",
                            "ring_id": ring_id,
                        })
                    tx_idx += 1

        elif archetype == "SYNCHRONIZED_BURST":
            # Coordinated execution waves: identical timestamp bursts
            num_waves = random.randint(3, 6)
            for w in range(num_waves):
                wave_time = start_date + timedelta(days=activation_day + (w * 2.5), hours=random.choice([10, 14, 18, 22]), minutes=random.randint(10, 40))
                for acc_id, _ in ring_accounts:
                    f_rate = ring_acc_fail_rates.get(acc_id, 0.05)
                    burst_time = wave_time + timedelta(seconds=random.randint(5, 90))
                    amt = round(random.uniform(75.0, 120.0), 2)
                    dest_c = random.choice(ring_destinations)
                    noise_p = abuse_noise_rng.random()
                    if noise_p < 0.15:
                        tx_t = "payment"
                        m_id = abuse_noise_rng.choice(all_merchants)
                        d_id = ""
                    elif noise_p < 0.18:
                        tx_t = "refund"
                        m_id = abuse_noise_rng.choice(all_merchants)
                        d_id = ""
                    else:
                        tx_t = "transfer"
                        m_id = ""
                        d_id = dest_c
                    status = "FAILED" if abuse_noise_rng.random() < f_rate else "SUCCESS"
                    tx_id_str = f"TX_{tx_idx:08d}"
                    transactions.append({
                        "transaction_id": tx_id_str,
                        "account_id": acc_id,
                        "timestamp": burst_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "amount": amt,
                        "merchant_id": m_id,
                        "destination_id": d_id,
                        "transaction_type": tx_t,
                        "status": status,
                    })
                    if tx_t == "transfer":
                        attack_events.append({
                            "event_id": f"EV_{len(attack_events)+1:08d}",
                            "transaction_id": tx_id_str,
                            "account_id": acc_id,
                            "timestamp": burst_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "attack_type": "synchronized_wave",
                            "ring_id": ring_id,
                        })
                    tx_idx += 1

        elif archetype == "TASK_JOB_SCAM":
            # Multi-tier deposit tasks ($115-$135, $310-$345) followed by settlement transfer
            for wave_step in range(3):
                wave_day = activation_day + (wave_step * 3.0)
                if wave_day >= duration_days - 1:
                    break

                # Tier 1 Task Deposits
                for acc_id, _ in ring_accounts:
                    f_rate = ring_acc_fail_rates.get(acc_id, 0.05)
                    t1_time = start_date + timedelta(days=wave_day, hours=11, minutes=random.randint(10, 45))
                    t1_amt = round(random.uniform(118.0, 138.0), 2)
                    dest_c = random.choice(ring_destinations)
                    noise_p = abuse_noise_rng.random()
                    if noise_p < 0.12:
                        tx_t = "payment"
                        m_id = abuse_noise_rng.choice(all_merchants)
                        d_id = ""
                    else:
                        tx_t = "p2p"
                        m_id = ""
                        d_id = dest_c
                    status = "FAILED" if abuse_noise_rng.random() < f_rate else "SUCCESS"
                    tx_id_str = f"TX_{tx_idx:08d}"
                    transactions.append({
                        "transaction_id": tx_id_str,
                        "account_id": acc_id,
                        "timestamp": t1_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "amount": t1_amt,
                        "merchant_id": m_id,
                        "destination_id": d_id,
                        "transaction_type": tx_t,
                        "status": status,
                    })
                    if tx_t == "p2p":
                        attack_events.append({
                            "event_id": f"EV_{len(attack_events)+1:08d}",
                            "transaction_id": tx_id_str,
                            "account_id": acc_id,
                            "timestamp": t1_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "attack_type": "task_deposit_scam",
                            "ring_id": ring_id,
                        })
                    tx_idx += 1

                # Tier 2 Task Deposits (30 mins later)
                for acc_id, _ in ring_accounts:
                    f_rate = ring_acc_fail_rates.get(acc_id, 0.05)
                    t2_time = start_date + timedelta(days=wave_day, hours=11, minutes=random.randint(50, 59), seconds=random.randint(0, 59))
                    t2_amt = round(random.uniform(310.0, 345.0), 2)
                    dest_c = random.choice(ring_destinations)
                    noise_p = abuse_noise_rng.random()
                    if noise_p < 0.08:
                        tx_t = "payment"
                        m_id = abuse_noise_rng.choice(all_merchants)
                        d_id = ""
                    else:
                        tx_t = "p2p"
                        m_id = ""
                        d_id = dest_c
                    status = "FAILED" if abuse_noise_rng.random() < f_rate else "SUCCESS"
                    tx_id_str = f"TX_{tx_idx:08d}"
                    transactions.append({
                        "transaction_id": tx_id_str,
                        "account_id": acc_id,
                        "timestamp": t2_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "amount": t2_amt,
                        "merchant_id": m_id,
                        "destination_id": d_id,
                        "transaction_type": tx_t,
                        "status": status,
                    })
                    if tx_t == "p2p":
                        attack_events.append({
                            "event_id": f"EV_{len(attack_events)+1:08d}",
                            "transaction_id": tx_id_str,
                            "account_id": acc_id,
                            "timestamp": t2_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "attack_type": "task_deposit_scam",
                            "ring_id": ring_id,
                        })
                    tx_idx += 1

                # Rapid Settlement Transfer (1 hour later)
                for acc_id, _ in ring_accounts:
                    f_rate = ring_acc_fail_rates.get(acc_id, 0.05)
                    settle_time = start_date + timedelta(days=wave_day, hours=12, minutes=random.randint(20, 55))
                    settle_amt = round(random.uniform(420.0, 470.0), 2)
                    dest_c = random.choice(ring_destinations)
                    noise_p = abuse_noise_rng.random()
                    if noise_p < 0.04:
                        tx_t = "refund"
                        m_id = abuse_noise_rng.choice(all_merchants)
                        d_id = ""
                    else:
                        tx_t = "transfer"
                        m_id = ""
                        d_id = dest_c
                    status = "FAILED" if abuse_noise_rng.random() < f_rate else "SUCCESS"
                    tx_id_str = f"TX_{tx_idx:08d}"
                    transactions.append({
                        "transaction_id": tx_id_str,
                        "account_id": acc_id,
                        "timestamp": settle_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "amount": settle_amt,
                        "merchant_id": m_id,
                        "destination_id": d_id,
                        "transaction_type": tx_t,
                        "status": status,
                    })
                    if tx_t == "transfer":
                        attack_events.append({
                            "event_id": f"EV_{len(attack_events)+1:08d}",
                            "transaction_id": tx_id_str,
                            "account_id": acc_id,
                            "timestamp": settle_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "attack_type": "task_scam_settlement",
                            "ring_id": ring_id,
                        })
                    tx_idx += 1

        else:
            # COVER_TRAFFIC_HYBRID & MIXED_PARTIAL
            for acc_id, acc_created in ring_accounts:
                f_rate = ring_acc_fail_rates.get(acc_id, 0.05)
                num_tx = random.randint(10, 20)
                for step in range(num_tx):
                    t_time = acc_created + timedelta(days=random.uniform(1.0, duration_days - 5.0), hours=sample_diurnal_hour(), minutes=random.randint(0, 59))
                    if t_time > end_date:
                        t_time = end_date - timedelta(hours=random.randint(1, 12))

                    is_scripted_attack = False
                    if random.random() < 0.40:
                        # Scripted cashout/transfer
                        amt = round(random.uniform(45.0, 95.0), 2)
                        tx_type = random.choice(["cashout", "transfer"])
                        merch = random.choice(ring_merchants) if tx_type == "cashout" else ""
                        dest = random.choice(ring_destinations) if tx_type == "transfer" else ""
                        tx_type_eff = tx_type
                        is_scripted_attack = True
                    else:
                        # Background cover payment
                        amt = float(np.clip(np.random.gamma(shape=2.0, scale=20.0), 10.0, 120.0))
                        merch_choice = random.choice(all_merchants)
                        noise_p = abuse_noise_rng.random()
                        if noise_p < 0.04:
                            tx_type_eff = "refund"
                            merch = merch_choice
                            dest = ""
                        elif noise_p < 0.12:
                            tx_type_eff = "p2p"
                            merch = ""
                            dest = abuse_noise_rng.choice(ring_destinations)
                        else:
                            tx_type_eff = "payment"
                            merch = merch_choice
                            dest = ""

                    status = "FAILED" if abuse_noise_rng.random() < f_rate else "SUCCESS"
                    tx_id_str = f"TX_{tx_idx:08d}"
                    transactions.append({
                        "transaction_id": tx_id_str,
                        "account_id": acc_id,
                        "timestamp": t_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "amount": round(amt, 2),
                        "merchant_id": merch,
                        "destination_id": dest,
                        "transaction_type": tx_type_eff,
                        "status": status,
                    })
                    if is_scripted_attack:
                        attack_events.append({
                            "event_id": f"EV_{len(attack_events)+1:08d}",
                            "transaction_id": tx_id_str,
                            "account_id": acc_id,
                            "timestamp": t_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "attack_type": "scripted_cashout_transfer",
                            "ring_id": ring_id,
                        })
                    tx_idx += 1

    # -------------------------------------------------------------------------
    # Final assembly and sorting
    # -------------------------------------------------------------------------
    df_accounts = pd.DataFrame(accounts)
    df_transactions = pd.DataFrame(transactions)
    df_attack_events = pd.DataFrame(attack_events)

    # Sort transactions chronologically
    df_transactions["timestamp_dt"] = pd.to_datetime(df_transactions["timestamp"])
    df_transactions = df_transactions.sort_values("timestamp_dt").reset_index(drop=True)
    df_transactions = df_transactions.drop(columns=["timestamp_dt"])

    if not df_attack_events.empty:
        df_attack_events["timestamp_dt"] = pd.to_datetime(df_attack_events["timestamp"])
        df_attack_events = df_attack_events.sort_values("timestamp_dt").reset_index(drop=True)
        df_attack_events = df_attack_events.drop(columns=["timestamp_dt"])

    # Persist to disk
    os.makedirs(output_dir, exist_ok=True)
    accounts_file = os.path.join(output_dir, "accounts.csv")
    transactions_file = os.path.join(output_dir, "transactions.csv")
    attack_events_file = os.path.join(output_dir, "attack_events.csv")

    df_accounts.to_csv(accounts_file, index=False)
    df_transactions.to_csv(transactions_file, index=False)
    df_attack_events.to_csv(attack_events_file, index=False)

    return df_accounts, df_transactions


def print_dataset_quality_report(df_accounts: pd.DataFrame, df_transactions: pd.DataFrame) -> None:
    """Print structured metrics and validation report for generated dataset."""
    total_acc = len(df_accounts)
    total_tx = len(df_transactions)

    type_counts = df_accounts["account_type"].value_counts()
    ring_accounts = df_accounts[df_accounts["account_type"] == "abuse_ring"]
    rings = ring_accounts.groupby("ring_id")["account_id"].count()

    small_rings = rings[rings.between(4, 8)]
    med_rings = rings[rings.between(9, 20)]
    large_rings = rings[rings.between(21, 50)]
    other_rings = rings[(rings < 4) | (rings > 50)]

    # Shared infrastructure statistics
    dev_counts = df_accounts.groupby("device_id")["account_id"].nunique()
    shared_devs = dev_counts[dev_counts > 1]
    ip_counts = df_accounts.groupby("ip_id")["account_id"].nunique()
    shared_ips = ip_counts[ip_counts > 1]

    # Abuse accounts with unique IP/device
    ring_dev_counts = df_accounts.set_index("account_id")["device_id"].map(dev_counts)
    ring_ip_counts = df_accounts.set_index("account_id")["ip_id"].map(ip_counts)

    abuse_acc_ids = set(ring_accounts["account_id"])
    abuse_no_shared_infra = sum(
        1 for acc in abuse_acc_ids
        if ring_dev_counts.get(acc, 1) == 1 and ring_ip_counts.get(acc, 1) == 1
    )

    # Legitimate accounts sharing infrastructure
    legit_accs = df_accounts[df_accounts["account_type"] != "abuse_ring"]
    legit_sharing_dev = sum(1 for _, row in legit_accs.iterrows() if dev_counts.get(row["device_id"], 1) > 1)
    legit_sharing_ip = sum(1 for _, row in legit_accs.iterrows() if ip_counts.get(row["ip_id"], 1) > 1)

    # Destination concentration
    valid_tx = df_transactions[df_transactions["destination_id"].fillna("").str.strip() != ""]
    dest_counts = valid_tx.groupby("destination_id")["account_id"].nunique()

    print("\n" + "=" * 75)
    print("      ABUSE-RING SENTINEL - SCALED DATASET QUALITY REPORT")
    print("=" * 75)
    print(f"1. POPULATION TOTALS:")
    print(f"   • Total Accounts     : {total_acc:,}")
    print(f"   • Total Transactions : {total_tx:,} (Avg {total_tx/total_acc:.1f} tx/account)")
    print(f"   • Date Span          : {df_transactions['timestamp'].min()} -> {df_transactions['timestamp'].max()}")

    print("\n2. ACCOUNT-TYPE DISTRIBUTION:")
    for t_name, count in type_counts.items():
        pct = (count / total_acc) * 100.0
        print(f"   • {t_name:<20s}: {count:>6,d} accounts ({pct:5.2f}%)")

    print("\n3. ABUSE RING METRICS:")
    print(f"   • Total Abuse Rings   : {len(rings)}")
    print(f"   • Total Ring Accounts : {len(ring_accounts):,} ({len(ring_accounts)/total_acc*100:.2f}%)")
    print(f"   • Small Rings (4-8)   : {len(small_rings)} rings ({small_rings.sum():,} accounts)")
    print(f"   • Medium Rings (9-20) : {len(med_rings)} rings ({med_rings.sum():,} accounts)")
    print(f"   • Large Rings (21-50) : {len(large_rings)} rings ({large_rings.sum():,} accounts)")
    if len(other_rings) > 0:
        print(f"   • Other Rings         : {len(other_rings)} rings ({other_rings.sum():,} accounts)")

    print("\n4. INFRASTRUCTURE & REUSE SIGNALS:")
    print(f"   • Unique Devices Used : {df_accounts['device_id'].nunique():,}")
    print(f"   • Devices Shared >1   : {len(shared_devs):,} devices (max {shared_devs.max()} accounts on one device)")
    print(f"   • Unique IPs Used     : {df_accounts['ip_id'].nunique():,}")
    print(f"   • IPs Shared >1       : {len(shared_ips):,} IPs (max {shared_ips.max()} accounts on one IP)")
    print(f"   • Abuse Accounts with ZERO shared IP & Device: {abuse_no_shared_infra:,} / {len(ring_accounts):,} ({abuse_no_shared_infra/len(ring_accounts)*100:.1f}%)")
    print(f"   • Legitimate Accounts Sharing IP             : {legit_sharing_ip:,} / {len(legit_accs):,} ({legit_sharing_ip/len(legit_accs)*100:.1f}%)")
    print(f"   • Legitimate Accounts Sharing Device         : {legit_sharing_dev:,} / {len(legit_accs):,} ({legit_sharing_dev/len(legit_accs)*100:.1f}%)")

    print("\n5. TRANSACTION BEHAVIOR & COUNTERPARTIES:")
    print("   • Transaction Type Breakdown:")
    type_tx = df_transactions["transaction_type"].value_counts()
    for t_type, count in type_tx.items():
        print(f"     - {t_type:<10s}: {count:>7,d} ({count/total_tx*100:5.2f}%)")
    print("   • Amount Statistics:")
    amt_stats = df_transactions["amount"].describe()
    print(f"     - Mean: ₹{amt_stats['mean'] * 83:.2f}, Median: ₹{amt_stats['50%'] * 83:.2f}, Std: ₹{amt_stats['std'] * 83:.2f}, Min: ₹{amt_stats['min'] * 83:.2f}, Max: ₹{amt_stats['max'] * 83:.2f}")
    print(f"   • Unique Destinations : {df_transactions['destination_id'].nunique():,} (Max {dest_counts.max()} accounts per dest)")
    print(f"   • Unique Merchants    : {df_transactions['merchant_id'].nunique():,}")
    print(f"   • Success Rate        : {(df_transactions['status'] == 'SUCCESS').mean()*100:.2f}%")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    df_acc, df_tx = generate_synthetic_data(PRESETS["scale_10k"])
    print_dataset_quality_report(df_acc, df_tx)
