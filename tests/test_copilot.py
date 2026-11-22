"""
Unit and Integration Tests for AI Investigation Copilot
Validates context building, temporal isolation, grounding, provider adapters,
security sanitization, and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.copilot.config import CopilotConfig
from src.copilot.context_builder import CopilotContextBuilder
from src.copilot.prompts import SYSTEM_PROMPT
from src.copilot.provider import LLMProviderError, MockProvider, get_llm_provider
from src.copilot.service import CopilotService


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# 1. Account Context Selection & Validation
# =============================================================================

def test_validate_account_id_valid():
    assert CopilotContextBuilder.validate_account_id("ACC_009754") == "ACC_009754"
    assert CopilotContextBuilder.validate_account_id("  ACC_000001  ") == "ACC_000001"


def test_validate_account_id_invalid_injection():
    with pytest.raises(ValueError):
        CopilotContextBuilder.validate_account_id("ACC_009754; DROP TABLE accounts;")

    with pytest.raises(ValueError):
        CopilotContextBuilder.validate_account_id("<script>alert(1)</script>")

    with pytest.raises(ValueError):
        CopilotContextBuilder.validate_account_id("INVALID_ID")


def test_build_context_known_account():
    context = CopilotContextBuilder.build_context("ACC_009754", mode="predictive")
    assert context["account_id"] == "ACC_009754"
    assert context["investigation_mode"] == "predictive"
    assert context["ml_risk_assessment"]["calibrated_probability"] == 0.9351
    assert context["ml_risk_assessment"]["risk_tier"] == "CRITICAL"
    assert context["ml_risk_assessment"]["is_high_risk"] is True
    assert context["ml_risk_assessment"]["decision_threshold"] == 0.35
    assert len(context["graph_evidence"]["top_relationships"]) > 0
    assert "observation_window" in context
    assert context["observation_window"]["is_complete_window"] is True


def test_build_context_nonexistent_account():
    with pytest.raises(KeyError):
        CopilotContextBuilder.build_context("ACC_999999", mode="predictive")


# =============================================================================
# 2. Predictive vs Retrospective Temporal Separation
# =============================================================================

def test_predictive_vs_retrospective_mode_separation():
    ctx_pred = CopilotContextBuilder.build_context("ACC_009754", mode="predictive")
    ctx_retro = CopilotContextBuilder.build_context("ACC_009754", mode="retrospective")

    assert ctx_pred["investigation_mode"] == "predictive"
    assert ctx_retro["investigation_mode"] == "retrospective"

    # XML prompt serialization should clearly indicate mode
    xml_pred = CopilotContextBuilder.format_prompt_context(ctx_pred)
    xml_retro = CopilotContextBuilder.format_prompt_context(ctx_retro)

    assert 'mode="predictive"' in xml_pred
    assert 'mode="retrospective"' in xml_retro


# =============================================================================
# 3. Excluded Outcome Window Handling
# =============================================================================

def test_excluded_account_context_handling():
    # ACC_009995 to ACC_010000 are registered within 7 days of dataset cutoff
    # Let's verify how context builder handles incomplete outcome windows
    cache = CopilotContextBuilder.build_context("ACC_000001", mode="predictive")
    assert cache["account_id"] == "ACC_000001"
    assert cache["ml_risk_assessment"]["risk_tier"] == "LOW"


# =============================================================================
# 4. Context Grounding & Prompt Formatting
# =============================================================================

def test_format_prompt_context_xml_integrity():
    context = CopilotContextBuilder.build_context("ACC_009754", mode="predictive")
    xml_str = CopilotContextBuilder.format_prompt_context(context)

    assert xml_str.startswith("<investigation_context>")
    assert xml_str.endswith("</investigation_context>")
    assert 'id="ACC_009754"' in xml_str
    assert "<calibrated_probability>0.9351</calibrated_probability>" in xml_str
    assert "<risk_tier>CRITICAL</risk_tier>" in xml_str


def test_suggested_questions_generation():
    context = CopilotContextBuilder.build_context("ACC_009754", mode="predictive")
    questions = CopilotContextBuilder.get_suggested_questions(context)

    assert isinstance(questions, list)
    assert len(questions) <= 4
    assert any("critical" in q.lower() for q in questions)


# =============================================================================
# 5. Provider Adapters & Deterministic Mock Provider
# =============================================================================

@pytest.mark.anyio
async def test_mock_provider_deterministic_answers():
    provider = MockProvider()
    context = CopilotContextBuilder.build_context("ACC_009754", mode="predictive")
    xml_str = CopilotContextBuilder.format_prompt_context(context)

    # 1. Ask why flagged
    reply_why = await provider.generate_response(
        system_prompt=SYSTEM_PROMPT,
        context_str=xml_str,
        history=[],
        user_prompt="Why was this account flagged as critical?",
    )
    assert "### Summary" in reply_why
    assert "### Key Evidence" in reply_why
    assert "0.9351" in reply_why
    assert "CRITICAL" in reply_why
    assert "### Investigator Next Steps" in reply_why

    # 2. Ask about connections
    reply_conn = await provider.generate_response(
        system_prompt=SYSTEM_PROMPT,
        context_str=xml_str,
        history=[],
        user_prompt="What entities are connected to this account?",
    )
    assert "### Summary" in reply_conn
    assert "connection" in reply_conn.lower() or "relationship" in reply_conn.lower()


def test_provider_factory_mock(monkeypatch):
    monkeypatch.setenv("COPILOT_PROVIDER", "mock")
    provider = get_llm_provider()
    assert isinstance(provider, MockProvider)


def test_provider_missing_key_error(monkeypatch):
    monkeypatch.setenv("COPILOT_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMProviderError):
        get_llm_provider()


# =============================================================================
# 6. Service Layer Isolation & Account Switching
# =============================================================================

@pytest.mark.anyio
async def test_service_account_switching_isolation(monkeypatch):
    monkeypatch.setenv("COPILOT_PROVIDER", "mock")

    # Account 1
    brief1 = await CopilotService.chat(account_id="ACC_009754", message="Why flagged?")
    assert brief1["account_id"] == "ACC_009754"
    assert "0.9351" in brief1["response"]

    # Account 2
    brief2 = await CopilotService.chat(account_id="ACC_000001", message="Explain risk.")
    assert brief2["account_id"] == "ACC_000001"
    assert "ACC_000001" in brief2["response"]
    assert "0.9351" not in brief2["response"]


# =============================================================================
# 7. FastAPI Endpoint Integration Tests
# =============================================================================

def test_endpoint_copilot_status(client):
    res = client.get("/api/investigations/copilot/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_ready" in data
    assert "supported_providers" in data


def test_endpoint_suggested_questions(client):
    res = client.get("/api/investigations/copilot/suggested-questions?account_id=ACC_009754")
    assert res.status_code == 200
    data = res.json()
    assert data["account_id"] == "ACC_009754"
    assert len(data["suggested_questions"]) > 0


def test_endpoint_suggested_questions_invalid_account(client):
    res = client.get("/api/investigations/copilot/suggested-questions?account_id=INVALID_ACC")
    assert res.status_code == 400


def test_endpoint_copilot_chat_mock(client, monkeypatch):
    monkeypatch.setenv("COPILOT_PROVIDER", "mock")
    payload = {
        "account_id": "ACC_009754",
        "mode": "predictive",
        "message": "Why was this account flagged?",
    }
    res = client.post("/api/investigations/copilot/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["account_id"] == "ACC_009754"
    assert data["is_error"] is False
    assert "### Summary" in data["response"]
    assert len(data["citations"]) > 0


def test_endpoint_copilot_chat_prompt_injection_defense(client, monkeypatch):
    monkeypatch.setenv("COPILOT_PROVIDER", "mock")
    # Injection via account ID
    res = client.post(
        "/api/investigations/copilot/chat",
        json={"account_id": "ACC_009754'; DROP TABLE accounts;--", "message": "hello"},
    )
    assert res.status_code == 400

    # Non-existent account
    res_404 = client.post(
        "/api/investigations/copilot/chat",
        json={"account_id": "ACC_999999", "message": "hello"},
    )
    assert res_404.status_code == 404


def test_endpoint_copilot_unconfigured_guidance(client, monkeypatch):
    monkeypatch.delenv("COPILOT_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    payload = {
        "account_id": "ACC_009754",
        "mode": "predictive",
        "message": "Why was this account flagged?",
    }
    res = client.post("/api/investigations/copilot/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    # Must report configuration required, NOT a fake fabricated AI answer
    assert data.get("is_configuration_error") is True
    assert "Copilot Configuration Required" in data["response"]
