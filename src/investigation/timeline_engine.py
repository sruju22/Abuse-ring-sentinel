"""
Abuse-Ring Sentinel - Evidence-Backed Graph Investigation Engine.
Module: Account Investigation Timeline Engine.

Constructs an interactive, chronological event timeline for focal accounts.
Supports:
  1. Predictive Investigation Mode (default):
     - Strictly restricted to events on or before T_obs.
     - Never accesses post-cutoff transactions or outcome labels.
  2. Retrospective Investigation Mode:
     - Includes all 30-day historical transactions.
     - Strictly tags post-cutoff events with is_retrospective=True and
       event_phase="RETROSPECTIVE_OUTCOME".
     - Inserts explicit visual milestone marker at T_obs.

Detects verifiable behavioral shifts:
  - Velocity surges (>= 3 txs in 1 hour)
  - Amount spikes (> 3x median amount or > $2500)
  - Rapid cashout bursts
  - Concentrated transaction failures
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
import numpy as np
import pandas as pd

from src.investigation.cluster_summarizer import InvestigationModelCache, get_account_ml_prediction
from src.investigation.evidence_engine import get_account_observation_metadata


@dataclass
class TimelineEvent:
    """Individual chronological event on the account timeline."""
    event_id: str
    timestamp: str
    event_type: str        # ACCOUNT_CREATED | TRANSACTION | BEHAVIORAL_ALERT | OBSERVATION_CUTOFF
    event_phase: str       # PREDICTIVE_OBSERVATION | RETROSPECTIVE_OUTCOME | MILESTONE
    is_retrospective: bool # False if <= T_obs, True if > T_obs
    title: str
    details: dict[str, Any]
    severity: str          # NORMAL | INFO | WARNING | CRITICAL


@dataclass
class AccountTimeline:
    """Comprehensive chronological timeline for fraud investigation."""
    account_id: str
    investigation_mode: str  # predictive | retrospective
    created_at: str
    observation_cutoff: str
    outcome_window_end: str
    outcome_window_status: str
    ml_prediction: dict[str, Any]
    summary_statistics: dict[str, Any]
    events: list[dict[str, Any]]
    behavioral_alerts: list[dict[str, Any]]
    mode_banner: Optional[str] = None


def detect_behavioral_shifts(
    df_tx_acc: pd.DataFrame,
    cutoff_dt: pd.Timestamp,
    mode: str,
) -> list[dict[str, Any]]:
    """
    Detects behavioral anomalies across transactions:
      - Velocity surge (burst >= 3 transactions in 60 minutes)
      - Amount spike (> 3x prior median or > $2500)
      - Rapid cashout burst (cashout following deposits/p2p)
      - Repeated transaction failures (>= 2 consecutive failures)
    """
    alerts = []
    if df_tx_acc.empty:
        return alerts

    sorted_tx = df_tx_acc.sort_values("timestamp_dt").reset_index(drop=True)
    amounts = sorted_tx["amount"].values
    timestamps = sorted_tx["timestamp_dt"].values
    types = sorted_tx["transaction_type"].values
    statuses = sorted_tx["status"].values
    tx_ids = sorted_tx["transaction_id"].values

    median_amount = float(np.median(amounts)) if len(amounts) > 0 else 0.0

    # 1. Velocity Surge Detection (rolling 1-hour window)
    for i in range(len(timestamps)):
        t_curr = timestamps[i]
        # Count transactions in [t_curr - 1 hour, t_curr]
        one_hr_ago = t_curr - np.timedelta64(1, "h")
        in_window_idx = np.where((timestamps >= one_hr_ago) & (timestamps <= t_curr))[0]
        if len(in_window_idx) >= 3 and i == in_window_idx[-1]:
            is_retro = bool(pd.to_datetime(t_curr) > cutoff_dt)
            if mode == "predictive" and is_retro:
                continue
            window_vol = float(np.sum(amounts[in_window_idx]))
            alerts.append({
                "alert_type": "VELOCITY_SURGE",
                "timestamp": str(pd.to_datetime(t_curr)),
                "transaction_id": str(tx_ids[i]),
                "severity": "WARNING" if len(in_window_idx) < 5 else "CRITICAL",
                "is_retrospective": is_retro,
                "description": (
                    f"Velocity burst: {len(in_window_idx)} transactions executed within 60 minutes "
                    f"(window volume: ${window_vol:,.2f})."
                ),
            })

    # 2. Amount Spike Detection
    for i in range(len(amounts)):
        amt = float(amounts[i])
        is_retro = bool(pd.to_datetime(timestamps[i]) > cutoff_dt)
        if mode == "predictive" and is_retro:
            continue

        if (median_amount > 0 and amt >= 3.0 * median_amount and amt > 500.0) or (amt >= 2500.0):
            alerts.append({
                "alert_type": "AMOUNT_SPIKE",
                "timestamp": str(pd.to_datetime(timestamps[i])),
                "transaction_id": str(tx_ids[i]),
                "severity": "CRITICAL" if amt >= 2500.0 else "WARNING",
                "is_retrospective": is_retro,
                "description": (
                    f"Transaction amount of ${amt:,.2f} is significantly elevated "
                    f"({amt / max(1.0, median_amount):.1f}x account median of ${median_amount:,.2f})."
                ),
            })

    # 3. Rapid Cashout Detection
    for i in range(len(types)):
        if str(types[i]).lower() == "cashout":
            is_retro = bool(pd.to_datetime(timestamps[i]) > cutoff_dt)
            if mode == "predictive" and is_retro:
                continue
            # Look at previous 3 transactions
            prior_start = max(0, i - 3)
            prior_types = [str(t).lower() for t in types[prior_start:i]]
            if any(t in ("payment", "p2p", "transfer") for t in prior_types):
                alerts.append({
                    "alert_type": "RAPID_CASHOUT_BURST",
                    "timestamp": str(pd.to_datetime(timestamps[i])),
                    "transaction_id": str(tx_ids[i]),
                    "severity": "HIGH",
                    "is_retrospective": is_retro,
                    "description": (
                        f"Cashout transaction of ${float(amounts[i]):,.2f} initiated immediately following "
                        f"incoming funding transactions ({', '.join(prior_types)})."
                    ),
                })

    # 4. Concentrated Transaction Failures
    consecutive_fails = 0
    for i in range(len(statuses)):
        is_retro = bool(pd.to_datetime(timestamps[i]) > cutoff_dt)
        if str(statuses[i]).upper() == "FAILED":
            consecutive_fails += 1
            if consecutive_fails >= 2:
                if mode == "predictive" and is_retro:
                    continue
                alerts.append({
                    "alert_type": "FAILURE_CONCENTRATION",
                    "timestamp": str(pd.to_datetime(timestamps[i])),
                    "transaction_id": str(tx_ids[i]),
                    "severity": "WARNING",
                    "is_retrospective": is_retro,
                    "description": f"Consecutive transaction failure ({consecutive_fails} failed transactions in sequence).",
                })
        else:
            consecutive_fails = 0

    return alerts


def build_account_timeline(
    account_id: str,
    mode: str = "predictive",
) -> AccountTimeline:
    """
    Constructs the end-to-end investigation timeline for an account.

    In predictive mode (default):
      - Strictly includes events with timestamp <= T_obs.
      - Never surfaces future transactions.

    In retrospective mode:
      - Includes full 30-day timeline.
      - Explicitly tags post-cutoff events with is_retrospective=True.
      - Inserts observation cutoff milestone marker.
    """
    clean_id = str(account_id).strip()
    cache = InvestigationModelCache.get_instance()
    df_accounts = cache.df_accounts
    df_gt = cache.df_gt
    df_tx = cache.df_tx

    acc_match = df_accounts[df_accounts["account_id"] == clean_id]
    if acc_match.empty:
        raise KeyError(f"Account '{clean_id}' not found in dataset.")

    # 1. Observation Metadata & Cutoff
    obs_meta = get_account_observation_metadata(clean_id, df_gt, df_accounts)
    created_dt = obs_meta["created_dt"]
    cutoff_dt = obs_meta["t_obs_dt"]
    cutoff_str = obs_meta["t_obs"]
    outcome_end_str = obs_meta["t_outcome_end"]
    outcome_status = obs_meta["outcome_window_status"]

    # 2. Calibrated ML Prediction
    ml_pred = get_account_ml_prediction(clean_id)

    # 3. Retrieve Transactions
    all_acc_tx = df_tx[df_tx["account_id"] == clean_id].copy()
    if not all_acc_tx.empty and "timestamp_dt" not in all_acc_tx.columns:
        all_acc_tx["timestamp_dt"] = pd.to_datetime(all_acc_tx["timestamp"])

    # Enforce predictive filtering
    if mode == "predictive":
        valid_tx = all_acc_tx[all_acc_tx["timestamp_dt"] <= cutoff_dt] if not all_acc_tx.empty else pd.DataFrame()
    else:
        valid_tx = all_acc_tx

    # 4. Behavioral Shifts
    behavioral_alerts = detect_behavioral_shifts(valid_tx, cutoff_dt, mode)
    alerts_by_tx = {}
    for alert in behavioral_alerts:
        tx_id = alert.get("transaction_id")
        if tx_id:
            alerts_by_tx.setdefault(tx_id, []).append(alert)

    # 5. Assemble Timeline Events
    timeline_events: list[TimelineEvent] = []

    # Milestone: Account Creation
    timeline_events.append(TimelineEvent(
        event_id=f"CREATION_{clean_id}",
        timestamp=obs_meta["created_at"],
        event_type="ACCOUNT_CREATED",
        event_phase="PREDICTIVE_OBSERVATION",
        is_retrospective=False,
        title="Account Registered",
        details={
            "account_id": clean_id,
            "device_id": str(acc_match.iloc[0].get("device_id", "N/A")),
            "ip_id": str(acc_match.iloc[0].get("ip_id", "N/A")),
            "country": str(acc_match.iloc[0].get("country", "N/A")),
        },
        severity="INFO",
    ))

    # Transactions
    if not valid_tx.empty:
        sorted_tx = valid_tx.sort_values("timestamp_dt")
        for _, tx_row in sorted_tx.iterrows():
            tx_dt = tx_row["timestamp_dt"]
            is_retro = bool(tx_dt > cutoff_dt)
            phase = "RETROSPECTIVE_OUTCOME" if is_retro else "PREDICTIVE_OBSERVATION"
            t_id = str(tx_row["transaction_id"])
            amt = float(tx_row["amount"])
            tx_type = str(tx_row["transaction_type"])
            status = str(tx_row["status"])

            related_alerts = alerts_by_tx.get(t_id, [])
            severity = "CRITICAL" if any(a["severity"] == "CRITICAL" for a in related_alerts) else (
                "WARNING" if (status == "FAILED" or len(related_alerts) > 0) else "NORMAL"
            )

            title = f"{tx_type.upper()} - ${amt:,.2f} ({status})"
            timeline_events.append(TimelineEvent(
                event_id=t_id,
                timestamp=str(tx_row["timestamp"]),
                event_type="TRANSACTION",
                event_phase=phase,
                is_retrospective=is_retro,
                title=title,
                details={
                    "transaction_id": t_id,
                    "amount": amt,
                    "transaction_type": tx_type,
                    "status": status,
                    "destination_id": str(tx_row.get("destination_id", "")),
                    "merchant_id": str(tx_row.get("merchant_id", "")),
                    "associated_alerts": [a["description"] for a in related_alerts],
                },
                severity=severity,
            ))

    # Milestone: Observation Cutoff Marker (T_obs)
    timeline_events.append(TimelineEvent(
        event_id=f"CUTOFF_{clean_id}",
        timestamp=cutoff_str,
        event_type="OBSERVATION_CUTOFF",
        event_phase="MILESTONE",
        is_retrospective=False,
        title="Point-in-Time Observation Cutoff (T_obs)",
        details={
            "description": (
                "Prediction decision point (7 days after account creation). "
                "All features and predictive model scores are evaluated using data up to this exact moment. "
                "Any subsequent activity occurs strictly in the outcome evaluation window."
            ),
            "cutoff_timestamp": cutoff_str,
            "outcome_window_end": outcome_end_str,
        },
        severity="INFO",
    ))

    # Sort all events chronologically
    timeline_events.sort(key=lambda e: (pd.to_datetime(e.timestamp), 0 if e.event_type != "OBSERVATION_CUTOFF" else 1))

    # 6. Compute Summary Statistics
    total_tx_count = len(valid_tx)
    total_vol = float(valid_tx["amount"].sum()) if not valid_tx.empty else 0.0
    failed_count = int((valid_tx["status"] == "FAILED").sum()) if not valid_tx.empty else 0

    pred_tx = valid_tx[valid_tx["timestamp_dt"] <= cutoff_dt] if not valid_tx.empty else pd.DataFrame()
    retro_tx = valid_tx[valid_tx["timestamp_dt"] > cutoff_dt] if not valid_tx.empty else pd.DataFrame()

    type_counts = valid_tx["transaction_type"].value_counts().to_dict() if not valid_tx.empty else {}

    summary_stats = {
        "total_transactions": total_tx_count,
        "total_volume": round(total_vol, 2),
        "failed_transactions_count": failed_count,
        "failed_rate": round(failed_count / max(1, total_tx_count), 4),
        "predictive_transactions_count": len(pred_tx),
        "predictive_volume": round(float(pred_tx["amount"].sum()), 2) if not pred_tx.empty else 0.0,
        "retrospective_transactions_count": len(retro_tx),
        "retrospective_volume": round(float(retro_tx["amount"].sum()), 2) if not retro_tx.empty else 0.0,
        "transaction_types": type_counts,
        "behavioral_alerts_count": len(behavioral_alerts),
    }

    mode_banner = None
    if mode == "retrospective":
        mode_banner = (
            "RETROSPECTIVE_INVESTIGATION_ACTIVE: You are viewing full 30-day historical data. "
            "Events occurring after T_obs (" + cutoff_str + ") represent outcome-window activity "
            "and were NOT visible to the ML model at prediction time."
        )

    return AccountTimeline(
        account_id=clean_id,
        investigation_mode=mode,
        created_at=obs_meta["created_at"],
        observation_cutoff=cutoff_str,
        outcome_window_end=outcome_end_str,
        outcome_window_status=outcome_status,
        ml_prediction=ml_pred,
        summary_statistics=summary_stats,
        events=[asdict(e) for e in timeline_events],
        behavioral_alerts=behavioral_alerts,
        mode_banner=mode_banner,
    )
