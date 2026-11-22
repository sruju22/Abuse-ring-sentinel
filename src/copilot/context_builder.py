"""
Abuse-Ring Sentinel - AI Investigation Copilot
Module: Account-Aware Context Builder & Evidence Assembler

Extracts and validates actual point-in-time and retrospective telemetry
from existing backend investigation services without modifying or duplicating them.
"""

from dataclasses import asdict
import re
from typing import Any, Optional
import numpy as np

from src.investigation.cluster_summarizer import (
    HIGH_RISK_THRESHOLD,
    InvestigationModelCache,
    get_account_ml_prediction,
)
from src.investigation.evidence_engine import (
    extract_account_relationships,
    get_account_observation_metadata,
)
from src.investigation.timeline_engine import (
    build_account_timeline,
)


ACCOUNT_ID_PATTERN = re.compile(r"^ACC_\d{6}$")


class CopilotContextBuilder:
    """
    Constructs bounded, structured, verified context payloads for the LLM.
    Guarantees strict point-in-time isolation in predictive mode.
    """

    @classmethod
    def validate_account_id(cls, account_id: str) -> str:
        """Validates that the account ID matches expected format and prevents injection."""
        clean_id = str(account_id).strip()
        if not clean_id or not ACCOUNT_ID_PATTERN.match(clean_id):
            raise ValueError(
                f"Invalid account ID '{clean_id}'. Expected format 'ACC_XXXXXX' (e.g. ACC_009754)."
            )
        return clean_id

    @classmethod
    def build_context(
        cls,
        account_id: str,
        mode: str = "predictive",
    ) -> dict[str, Any]:
        """
        Gathers authorized, grounded facts for the specified account.
        Raises KeyError if account is not found in the dataset.
        """
        clean_id = cls.validate_account_id(account_id)
        cache = InvestigationModelCache.get_instance()
        df_acc = cache.df_accounts
        if df_acc.empty:
            cache.load_data()
            df_acc = cache.df_accounts

        match = df_acc[df_acc["account_id"] == clean_id]
        if match.empty:
            raise KeyError(f"Account '{clean_id}' not found in the platform dataset.")

        # 1. Observation Window Metadata
        obs_meta = get_account_observation_metadata(clean_id, cache.df_gt, df_acc)

        # 2. Authoritative CatBoost ML Prediction & Platt Calibration
        ml_prediction = get_account_ml_prediction(clean_id)

        # 3. Verified Relationship Evidence Records
        rel_evidence = extract_account_relationships(
            clean_id,
            df_acc,
            cache.df_tx,
            df_gt=cache.df_gt,
            mode=mode,
        )

        # 4. Account Timeline & Behavioral Shifts
        timeline = build_account_timeline(clean_id, mode=mode)
        timeline_dict = asdict(timeline)

        # 5. Extract Observable Behavioral Features
        features_dict = {}
        if not cache.df_features.empty:
            feat_match = cache.df_features[cache.df_features["account_id"] == clean_id]
            if not feat_match.empty:
                features_dict = feat_match.iloc[0].to_dict()

        # 6. Cluster context
        cluster_id = None
        if not cache.df_clusters.empty:
            for _, c_row in cache.df_clusters.iterrows():
                members = [str(a).strip() for a in str(c_row["accounts_list"]).split("|")]
                if clean_id in members:
                    cluster_id = str(c_row["cluster_id"]).strip()
                    break

        # Group relationships by type for concise summaries
        rel_by_type = {}
        top_relationships = []
        for r in rel_evidence:
            r_dict = asdict(r)
            etype = r_dict["evidence_type"]
            rel_by_type[etype] = rel_by_type.get(etype, 0) + 1
            if len(top_relationships) < 8:
                top_relationships.append({
                    "target_account": r_dict["target_account"],
                    "evidence_type": etype,
                    "shared_entity_id": r_dict["shared_entity_id"],
                    "evidence_strength": r_dict["evidence_strength"],
                    "support_count": r_dict["support_count"],
                    "is_mitigating": r_dict["is_mitigating"],
                    "explanation": r_dict["explanation"],
                })

        # Summary of key features that influence baseline risk
        key_features = {
            "transaction_count": features_dict.get("transaction_count", 0),
            "total_transaction_amount": round(float(features_dict.get("total_transaction_amount", 0.0) or 0.0), 2),
            "night_transaction_ratio": round(float(features_dict.get("night_transaction_ratio", 0.0) or 0.0), 3),
            "p2p_transaction_ratio": round(float(features_dict.get("p2p_transaction_ratio", 0.0) or 0.0), 3),
            "transfer_transaction_ratio": round(float(features_dict.get("transfer_transaction_ratio", 0.0) or 0.0), 3),
            "accounts_sharing_device": int(features_dict.get("accounts_sharing_device", 0) or 0),
            "accounts_sharing_ip": int(features_dict.get("accounts_sharing_ip", 0) or 0),
            "accounts_with_similar_timing": int(features_dict.get("number_of_accounts_with_similar_transaction_timing", 0) or 0),
            "timing_similarity": round(float(features_dict.get("average_transaction_timing_similarity", 0.0) or 0.0), 3),
            "accounts_with_shared_destinations": int(features_dict.get("number_of_accounts_with_shared_destinations", 0) or 0),
        }

        # Extract infrastructure details
        acc_row = match.iloc[0]
        device_id = str(acc_row.get("device_id", ""))
        ip_id = str(acc_row.get("ip_id", ""))

        # Assemble structured context dictionary
        context_data = {
            "account_id": clean_id,
            "investigation_mode": mode,
            "observation_window": {
                "created_at": obs_meta["created_at"],
                "cutoff_t_obs": obs_meta["t_obs"],
                "outcome_window_end": obs_meta["t_outcome_end"],
                "outcome_window_status": obs_meta["outcome_window_status"],
                "is_complete_window": obs_meta["is_complete_window"],
            },
            "ml_risk_assessment": {
                "model_name": "Untuned CatBoost Baseline (Platt Calibrated)",
                "calibrated_probability": ml_prediction.get("calibrated_probability"),
                "risk_tier": ml_prediction.get("risk_tier", "UNRATED"),
                "is_high_risk": ml_prediction.get("is_high_risk", False),
                "decision_threshold": HIGH_RISK_THRESHOLD,
                "status": ml_prediction.get("status"),
                "explanation": ml_prediction.get("explanation"),
            },
            "infrastructure": {
                "device_id": device_id if device_id != "nan" else "UNSPECIFIED",
                "ip_id": ip_id if ip_id != "nan" else "UNSPECIFIED",
                "shared_device_peers_count": key_features["accounts_sharing_device"],
                "shared_ip_peers_count": key_features["accounts_sharing_ip"],
            },
            "behavioral_profile": key_features,
            "graph_evidence": {
                "total_verified_relationships": len(rel_evidence),
                "relationship_type_breakdown": rel_by_type,
                "top_relationships": top_relationships,
                "macro_cluster_id": cluster_id,
            },
            "timeline_telemetry": {
                "summary": timeline_dict.get("summary_statistics", {}),
                "behavioral_alerts": timeline_dict.get("behavioral_alerts", []),
                "events_count": len(timeline_dict.get("events", [])),
            },
        }

        # Build citations list for UI linking
        citations = []
        if ml_prediction.get("calibrated_probability") is not None:
            citations.append({
                "type": "MODEL",
                "id": "CATBOOST_SCORE",
                "label": f"CatBoost P(abuse) = {ml_prediction['calibrated_probability']:.4f} ({ml_prediction.get('risk_tier')})",
                "target_tab": "evidence",
            })
        if cluster_id:
            citations.append({
                "type": "CLUSTER",
                "id": cluster_id,
                "label": f"Louvain Cluster {cluster_id}",
                "target_tab": "evidence",
            })
        for r in top_relationships[:3]:
            citations.append({
                "type": "EVIDENCE",
                "id": r["shared_entity_id"],
                "label": f"{r['evidence_type']}: {r['shared_entity_id']} ({r['target_account']})",
                "target_tab": "evidence",
            })
        for alert in timeline_dict.get("behavioral_alerts", [])[:2]:
            citations.append({
                "type": "TIMELINE",
                "id": alert.get("alert_type", "ALERT"),
                "label": f"{alert.get('alert_type')}: {alert.get('timestamp')}",
                "target_tab": "timeline",
            })

        context_data["citations"] = citations
        return context_data

    @classmethod
    def format_prompt_context(cls, context_dict: dict[str, Any]) -> str:
        """
        Serializes context into an unambiguous XML-delimited prompt payload.
        Encapsulation guards against prompt injection from user or database fields.
        """
        acc = context_dict["account_id"]
        mode = context_dict["investigation_mode"]
        obs = context_dict["observation_window"]
        ml = context_dict["ml_risk_assessment"]
        infra = context_dict["infrastructure"]
        feat = context_dict["behavioral_profile"]
        graph = context_dict["graph_evidence"]
        time_s = context_dict["timeline_telemetry"]["summary"]
        alerts = context_dict["timeline_telemetry"]["behavioral_alerts"]

        lines = [
            "<investigation_context>",
            f'  <account id="{acc}" mode="{mode}" status="{obs["outcome_window_status"]}">'
            f'    <temporal_window created_at="{obs["created_at"]}" observation_cutoff="{obs["cutoff_t_obs"]}" is_complete="{obs["is_complete_window"]}" />',
            "    <ml_prediction>",
            f'      <model name="{ml["model_name"]}" />',
            f'      <calibrated_probability>{ml["calibrated_probability"]}</calibrated_probability>',
            f'      <risk_tier>{ml["risk_tier"]}</risk_tier>',
            f'      <decision_threshold>{ml["decision_threshold"]}</decision_threshold>',
            f'      <is_high_risk>{ml["is_high_risk"]}</is_high_risk>',
            "    </ml_prediction>",
            "    <infrastructure>",
            f'      <device id="{infra["device_id"]}" shared_peers="{infra["shared_device_peers_count"]}" />',
            f'      <ip id="{infra["ip_id"]}" shared_peers="{infra["shared_ip_peers_count"]}" />',
            "    </infrastructure>",
            "    <observable_behavior>",
            f'      <transactions count="{feat["transaction_count"]}" total_amount="{feat["total_transaction_amount"]}" />',
            f'      <timing_synchrony peer_accounts="{feat["accounts_with_similar_timing"]}" similarity_score="{feat["timing_similarity"]}" />',
            f'      <destination_funneling shared_destination_peers="{feat["accounts_with_shared_destinations"]}" />',
            f'      <night_ratio>{feat["night_transaction_ratio"]}</night_ratio>',
            f'      <p2p_ratio>{feat["p2p_transaction_ratio"]}</p2p_ratio>',
            f'      <transfer_ratio>{feat["transfer_transaction_ratio"]}</transfer_ratio>',
            "    </observable_behavior>",
            f'    <graph_relationships total="{graph["total_verified_relationships"]}" macro_cluster="{graph["macro_cluster_id"]}">',
        ]

        for r in graph["top_relationships"]:
            lines.append(
                f'      <relationship target="{r["target_account"]}" type="{r["evidence_type"]}" '
                f'entity="{r["shared_entity_id"]}" strength="{r["evidence_strength"]}" '
                f'support_count="{r["support_count"]}" is_mitigating="{r["is_mitigating"]}" />'
            )

        lines.extend([
            "    </graph_relationships>",
            "    <timeline_summary>",
            f'      <transactions total="{time_s.get("total_transactions", 0)}" volume="{time_s.get("total_volume", 0)}" fail_rate="{time_s.get("failed_rate", 0)}" />',
            f'      <behavioral_alerts count="{len(alerts)}">',
        ])

        for a in alerts[:4]:
            lines.append(
                f'        <alert type="{a.get("alert_type")}" timestamp="{a.get("timestamp")}" severity="{a.get("severity", "WARNING")}" description="{a.get("description", "")}" />'
            )

        lines.extend([
            "      </behavioral_alerts>",
            "    </timeline_summary>",
            "  </account>",
            "</investigation_context>",
        ])

        return "\n".join(lines)

    @classmethod
    def get_suggested_questions(cls, context_dict: dict[str, Any]) -> list[str]:
        """Returns contextually relevant inquiry chips based on the account's actual data."""
        questions = []
        ml = context_dict.get("ml_risk_assessment", {})
        tier = ml.get("risk_tier", "LOW")
        infra = context_dict.get("infrastructure", {})
        graph = context_dict.get("graph_evidence", {})
        alerts = context_dict.get("timeline_telemetry", {}).get("behavioral_alerts", [])

        # 1. Tier-specific explanation
        if tier in ("CRITICAL", "HIGH"):
            questions.append(f"Why was this account flagged as {tier.lower()}?")
        elif tier == "UNRATED":
            questions.append("Why is this account unrated and excluded?")
        else:
            questions.append("Explain this account's low risk score.")

        # 2. Infrastructure & Connected accounts
        if infra.get("shared_device_peers_count", 0) > 0 or infra.get("shared_ip_peers_count", 0) > 0:
            questions.append("Explain the shared hardware device and IP connections.")
        elif graph.get("total_verified_relationships", 0) > 0:
            questions.append("Which accounts and entities are connected to this account?")
        else:
            questions.append("What corroborated evidence is available?")

        # 3. Timeline / Behavioral anomalies
        if len(alerts) > 0:
            questions.append("What behavioral timeline anomalies were detected?")
        else:
            questions.append("Summarize the account's transaction timeline.")

        # 4. Actionable next steps
        questions.append("What should an investigator examine next?")

        return questions[:4]
