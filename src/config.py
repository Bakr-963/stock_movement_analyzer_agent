"""Load runtime settings and build external clients."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

from dotenv import load_dotenv
from tavily import TavilyClient

LLMProvider = Literal["ollama", "lmstudio"]


def _env(key: str, default: str | None = None, *, fallback: str | None = None) -> str | None:
    """Read an environment variable with an optional fallback key."""
    value = os.getenv(key)
    if value not in (None, ""):
        return value
    if fallback is not None:
        fallback_value = os.getenv(fallback)
        if fallback_value not in (None, ""):
            return fallback_value
    return default


def _env_int(key: str, default: int, *, fallback: str | None = None) -> int:
    """Read an integer environment variable safely."""
    value = _env(key, fallback=fallback)
    if value in (None, ""):
        return default
    return int(value)


def _env_float(key: str, default: float) -> float:
    """Read a float environment variable safely."""
    value = _env(key)
    if value in (None, ""):
        return default
    return float(value)


@dataclass(frozen=True)
class Settings:
    """Store application settings for the analyzer."""

    local_llm: str = "gemma4:e4b-it-q8_0"
    llm_provider: LLMProvider = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    tavily_api_key: str | None = None
    max_research_loops: int = 3
    confidence_threshold: int = 80
    search_max_results: int = 5
    max_tokens_per_source: int = 1000
    model_temperature: float = 0.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from environment variables."""
        load_dotenv()
        llm_provider = (_env("LLM_PROVIDER", "ollama") or "ollama").strip().lower()
        if llm_provider not in ("ollama", "lmstudio"):
            raise ValueError(
                "LLM_PROVIDER must be either 'ollama' or 'lmstudio', "
                f"got {llm_provider!r}."
            )

        return cls(
            local_llm=_env("LOCAL_LLM", "gemma4:e4b-it-q8_0") or "gemma4:e4b-it-q8_0",
            llm_provider=llm_provider,
            ollama_base_url=_env("OLLAMA_BASE_URL", "http://localhost:11434")
            or "http://localhost:11434",
            lmstudio_base_url=_env("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
            or "http://localhost:1234/v1",
            tavily_api_key=_env("TAVILY_API_KEY"),
            max_research_loops=_env_int(
                "MAX_RESEARCH_LOOPS",
                3,
                fallback="MAX_WEB_RESEARCH_LOOPS",
            ),
            confidence_threshold=_env_int("CONFIDENCE_THRESHOLD", 80),
            search_max_results=_env_int("SEARCH_MAX_RESULTS", 5),
            max_tokens_per_source=_env_int("MAX_TOKENS_PER_SOURCE", 1000),
            model_temperature=_env_float("MODEL_TEMPERATURE", 0.0),
            log_level=(_env("LOG_LEVEL", "INFO") or "INFO").upper(),
        )


@dataclass(frozen=True)
class RuntimeDependencies:
    """Bundle runtime dependencies for the graph."""

    settings: Settings
    llm: Any
    json_llm: Any
    tavily_client: TavilyClient | None


def build_chat_models(settings: Settings) -> tuple[Any, Any]:
    """Create standard and JSON-oriented chat models."""
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        return (
            ChatOllama(
                model=settings.local_llm,
                temperature=settings.model_temperature,
                base_url=settings.ollama_base_url,
            ),
            ChatOllama(
                model=settings.local_llm,
                temperature=settings.model_temperature,
                base_url=settings.ollama_base_url,
                format="json",
            ),
        )

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.local_llm,
        temperature=settings.model_temperature,
        base_url=settings.lmstudio_base_url,
        api_key=_env("LMSTUDIO_API_KEY", "lmstudio"),
    )
    return llm, llm


def build_dependencies(settings: Settings | None = None) -> RuntimeDependencies:
    """Construct all runtime dependencies from settings."""
    resolved_settings = settings or Settings.from_env()
    llm, json_llm = build_chat_models(resolved_settings)
    tavily_client = (
        TavilyClient(api_key=resolved_settings.tavily_api_key)
        if resolved_settings.tavily_api_key
        else None
    )
    return RuntimeDependencies(
        settings=resolved_settings,
        llm=llm,
        json_llm=json_llm,
        tavily_client=tavily_client,
    )
