"""
Abuse-Ring Sentinel - AI Investigation Copilot
Module: Copilot Service Orchestration Layer
"""

import logging
from typing import Any, Optional

from src.copilot.config import CopilotConfig
from src.copilot.context_builder import CopilotContextBuilder
from src.copilot.prompts import SYSTEM_PROMPT
from src.copilot.provider import LLMProviderError, get_llm_provider

logger = logging.getLogger(__name__)


class CopilotService:
    """Orchestrates account-aware context building and grounded AI response generation."""

    @classmethod
    def get_status(cls) -> dict[str, Any]:
        """Returns the readiness state and active provider metadata."""
        is_ready, message = CopilotConfig.is_configured()
        provider = CopilotConfig.get_provider()
        model = CopilotConfig.get_model() if is_ready else None

        return {
            "is_ready": is_ready,
            "provider": provider,
            "model": model,
            "status_message": message,
            "supported_providers": ["gemini", "openai", "anthropic", "ollama", "mock"],
        }

    @classmethod
    def get_suggested_questions(cls, account_id: str, mode: str = "predictive") -> list[str]:
        """Generates dynamic suggested question chips for the active account."""
        # Strictly validate account_id format first
        clean_id = CopilotContextBuilder.validate_account_id(account_id)
        try:
            context = CopilotContextBuilder.build_context(clean_id, mode=mode)
            return CopilotContextBuilder.get_suggested_questions(context)
        except (ValueError, KeyError):
            raise
        except Exception as e:
            logger.warning(f"Failed to generate suggested questions for {account_id}: {e}")
            return [
                "Why was this account flagged?",
                "What entities are shared with peer accounts?",
                "Summarize the transaction timeline.",
                "What should an investigator examine next?",
            ]

    @classmethod
    async def generate_account_brief(
        cls,
        account_id: str,
        mode: str = "predictive",
    ) -> dict[str, Any]:
        """
        Generates the initial automated briefing when an investigator opens
        the Copilot panel for an account.
        """
        context = CopilotContextBuilder.build_context(account_id, mode=mode)
        prompt = (
            f"Provide an initial, concise forensic investigation summary for account {account_id}. "
            "Highlight its calibrated CatBoost risk tier, primary observable indicators, and recommended next steps."
        )

        return await cls.chat(
            account_id=account_id,
            mode=mode,
            message=prompt,
            history=[],
        )

    @classmethod
    async def chat(
        cls,
        account_id: str,
        mode: str = "predictive",
        message: str = "",
        history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        """
        Executes an account-grounded investigation Q&A interaction.
        """
        clean_msg = message.strip()
        if not clean_msg:
            raise ValueError("Inquiry message cannot be empty.")
        if len(clean_msg) > 1000:
            raise ValueError("Inquiry message exceeds maximum allowed length of 1000 characters.")

        # 1. Build verified account context
        context = CopilotContextBuilder.build_context(account_id, mode=mode)
        context_xml = CopilotContextBuilder.format_prompt_context(context)

        # 2. Check provider readiness
        is_ready, status_msg = CopilotConfig.is_configured()
        if not is_ready:
            return {
                "account_id": account_id,
                "mode": mode,
                "response": (
                    f"### Copilot Configuration Required\n\n"
                    f"{status_msg}\n\n"
                    f"**Quick Setup Instructions:**\n"
                    f"1. Create a `.env` file in the project root: `touch .env`\n"
                    f"2. Add your Google Gemini or OpenAI API key:\n"
                    f"   ```bash\n"
                    f"   GEMINI_API_KEY=your_gemini_api_key_here\n"
                    f"   # or\n"
                    f"   OPENAI_API_KEY=your_openai_api_key_here\n"
                    f"   ```\n"
                    f"3. Restart the dashboard (`python3 dashboard/run_dashboard.py`).\n\n"
                    f"> *For hermetic offline evaluation or testing, you can also run with `COPILOT_PROVIDER=mock`.*"
                ),
                "is_configuration_error": True,
                "provider": CopilotConfig.get_provider(),
                "model": None,
                "citations": context.get("citations", []),
                "suggested_questions": CopilotContextBuilder.get_suggested_questions(context),
            }

        # 3. Invoke configured LLM Provider
        provider = get_llm_provider()
        safe_history = history or []

        try:
            ai_text = await provider.generate_response(
                system_prompt=SYSTEM_PROMPT,
                context_str=context_xml,
                history=safe_history,
                user_prompt=clean_msg,
            )
        except LLMProviderError as e:
            logger.error(f"Copilot LLM execution error for {account_id}: {e}")
            return {
                "account_id": account_id,
                "mode": mode,
                "response": (
                    f"### AI Provider Notice\n\n"
                    f"The configured AI provider was unable to complete the analysis ({str(e)}).\n\n"
                    f"**Grounded Telemetry Available:**\n"
                    f"- CatBoost Platt-calibrated score: **{context['ml_risk_assessment']['calibrated_probability']}** ({context['ml_risk_assessment']['risk_tier']})\n"
                    f"- Verified relationship links: **{context['graph_evidence']['total_verified_relationships']}**\n\n"
                    f"Please verify provider connectivity or retry your inquiry."
                ),
                "is_error": True,
                "provider": CopilotConfig.get_provider(),
                "model": CopilotConfig.get_model(),
                "citations": context.get("citations", []),
                "suggested_questions": CopilotContextBuilder.get_suggested_questions(context),
            }

        return {
            "account_id": account_id,
            "mode": mode,
            "response": ai_text,
            "is_error": False,
            "provider": CopilotConfig.get_provider(),
            "model": CopilotConfig.get_model(),
            "citations": context.get("citations", []),
            "suggested_questions": CopilotContextBuilder.get_suggested_questions(context),
        }
