"""
Abuse-Ring Sentinel - AI Investigation Copilot
Module: Configuration and Environment Settings
"""

import os
from pathlib import Path
from typing import Optional


def load_env_file(filepath: Optional[str] = None) -> None:
    """
    Lightweight, dependency-free .env file parser and loader.
    Populates os.environ without overwriting existing environment variables.
    """
    if filepath is None:
        # Search project root
        root_dir = Path(__file__).resolve().parent.parent.parent
        env_path = root_dir / ".env"
    else:
        env_path = Path(filepath)

    if not env_path.exists() or not env_path.is_file():
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not load .env file: {e}")


# Load .env file at module import time
load_env_file()


class CopilotConfig:
    """Configuration options for the AI Investigation Copilot."""

    @classmethod
    def get_provider(cls) -> str:
        """
        Detects provider from COPILOT_PROVIDER or autodetects from API keys.
        Options: 'local' (default built-in forensic engine), 'gemini', 'openai', 'anthropic', 'ollama', 'mock'.
        """
        explicit = os.environ.get("COPILOT_PROVIDER", "").lower().strip()
        if explicit:
            return explicit

        # Autodetect based on available keys
        if os.environ.get("GEMINI_API_KEY"):
            return "gemini"
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"

        # Default to unconfigured if no explicit provider or key is present
        return "unconfigured"

    @classmethod
    def get_api_key(cls, provider: Optional[str] = None) -> Optional[str]:
        p = provider or cls.get_provider()
        if p == "gemini":
            return os.environ.get("GEMINI_API_KEY")
        elif p == "openai":
            return os.environ.get("OPENAI_API_KEY")
        elif p == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY")
        return None

    @classmethod
    def get_model(cls, provider: Optional[str] = None) -> str:
        p = provider or cls.get_provider()
        env_model = os.environ.get("COPILOT_MODEL")
        if env_model:
            return env_model

        if p in ("local", "mock"):
            return "Built-in Forensic Engine"
        elif p == "gemini":
            return "gemini-1.5-flash"
        elif p == "openai":
            return "gpt-4o-mini"
        elif p == "anthropic":
            return "claude-3-5-haiku-latest"
        elif p == "ollama":
            return "llama3.2"
        return "Built-in Forensic Engine"

    @classmethod
    def get_ollama_base_url(cls) -> str:
        return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    @classmethod
    def get_timeout_seconds(cls) -> float:
        try:
            return float(os.environ.get("COPILOT_TIMEOUT_SECONDS", "25.0"))
        except ValueError:
            return 25.0

    @classmethod
    def get_temperature(cls) -> float:
        try:
            return float(os.environ.get("COPILOT_TEMPERATURE", "0.1"))
        except ValueError:
            return 0.1

    @classmethod
    def is_configured(cls) -> tuple[bool, str]:
        """
        Checks if the LLM provider is properly configured with credentials.
        Returns (is_ready, status_message).
        """
        provider = cls.get_provider()
        if provider in ("local", "mock"):
            return True, "Built-in Forensic Intelligence Engine active (Instant local analysis, zero API keys required)."

        if provider == "gemini":
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                return False, "GEMINI_API_KEY is not set. Configure GEMINI_API_KEY in your environment or .env file."
            return True, f"Google Gemini ready ({cls.get_model('gemini')})."

        elif provider == "openai":
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                return False, "OPENAI_API_KEY is not set. Configure OPENAI_API_KEY in your environment or .env file."
            return True, f"OpenAI ready ({cls.get_model('openai')})."

        elif provider == "anthropic":
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                return False, "ANTHROPIC_API_KEY is not set. Configure ANTHROPIC_API_KEY in your environment or .env file."
            return True, f"Anthropic ready ({cls.get_model('anthropic')})."

        elif provider == "ollama":
            return True, f"Ollama local model ready ({cls.get_model('ollama')} at {cls.get_ollama_base_url()})."

        return False, (
            "No LLM provider configured. Set COPILOT_PROVIDER and corresponding API key "
            "(e.g. GEMINI_API_KEY or OPENAI_API_KEY) in .env to activate live AI responses."
        )
