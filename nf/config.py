"""프로젝트별 AI 설정 관리 — ai_config.json 로드/저장/프로바이더 생성."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .providers.base import AIProvider

# Phase names used as keys in phase_overrides
PHASE_KEYS = [
    "phase1_planning",
    "phase2_development",
    "phase3_writing",
    "phase4_revision",
]

# Map state machine phase values to config phase keys
PHASE_MAP = {
    "phase1": "phase1_planning",
    "phase2": "phase2_development",
    "phase3": "phase3_writing",
    "phase4": "phase4_revision",
}

DEFAULT_CONFIG = {
    "default_provider": {
        "type": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "phase_overrides": {
        "phase1_planning": None,
        "phase2_development": None,
        "phase3_writing": None,
        "phase4_revision": None,
    },
    "cost_tracking": False,
}


def load_ai_config(project_root: Path) -> dict:
    """Load ai_config.json from project root. Returns default if not found."""
    config_path = project_root / "ai_config.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        # Ensure all keys exist (forward-compat)
        for key, default_val in DEFAULT_CONFIG.items():
            config.setdefault(key, default_val)
        if "phase_overrides" in config:
            for pk in PHASE_KEYS:
                config["phase_overrides"].setdefault(pk, None)
        return config
    return json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy


def save_ai_config(project_root: Path, config: dict) -> Path:
    """Save ai_config.json to project root."""
    config_path = project_root / "ai_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return config_path


def get_provider_config(config: dict, phase: str) -> dict:
    """Get the effective provider config for a given phase.

    If the phase has an override, use it. Otherwise fall back to default_provider.
    """
    phase_key = PHASE_MAP.get(phase, phase)
    override = config.get("phase_overrides", {}).get(phase_key)
    if override is not None:
        return override
    return config.get("default_provider", DEFAULT_CONFIG["default_provider"])


def create_provider(provider_config: dict) -> AIProvider:
    """Instantiate an AIProvider from a config dict.

    Config dict format:
        {"type": "anthropic", "model": "claude-sonnet-4-20250514", "api_key_env": "ANTHROPIC_API_KEY", ...}
    """
    provider_type = provider_config.get("type", "anthropic")
    model = provider_config.get("model", "")
    api_key_env = provider_config.get("api_key_env", "")
    api_key = provider_config.get("api_key")  # Direct key (not recommended)

    if provider_type == "anthropic":
        from .providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            model=model or "claude-sonnet-4-20250514",
            api_key=api_key,
            api_key_env=api_key_env or "ANTHROPIC_API_KEY",
        )

    if provider_type == "openai":
        from .providers.openai_provider import OpenAIProvider
        return OpenAIProvider(
            model=model or "gpt-4o",
            api_key=api_key,
            api_key_env=api_key_env or "OPENAI_API_KEY",
            base_url=provider_config.get("base_url"),
        )

    if provider_type == "google":
        from .providers.google_provider import GoogleProvider
        return GoogleProvider(
            model=model or "gemini-2.0-flash",
            api_key=api_key,
            api_key_env=api_key_env or "GOOGLE_API_KEY",
        )

    if provider_type == "openrouter":
        from .providers.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(
            model=model or "anthropic/claude-sonnet-4",
            api_key=api_key,
            api_key_env=api_key_env or "OPENROUTER_API_KEY",
        )

    if provider_type == "ollama":
        from .providers.ollama_provider import OllamaProvider
        return OllamaProvider(
            model=model or "llama3.1",
            base_url=provider_config.get("base_url", "http://localhost:11434/v1"),
        )

    if provider_type == "custom":
        # OpenAI-compatible custom endpoint
        from .providers.openai_provider import OpenAIProvider
        return OpenAIProvider(
            model=model,
            api_key=api_key,
            api_key_env=api_key_env,
            base_url=provider_config.get("base_url", ""),
        )

    # v2.2: CLI 기반 프로바이더 (외부 에이전트 CLI를 subprocess로 호출)
    timeout = provider_config.get("timeout")
    if provider_type in ("gemini-cli", "gemini_cli"):
        from .providers.gemini_cli_provider import GeminiCLIProvider
        return GeminiCLIProvider(model=model, timeout=timeout)

    if provider_type in ("codex-cli", "codex_cli"):
        from .providers.codex_cli_provider import CodexCLIProvider
        return CodexCLIProvider(model=model, timeout=timeout)

    if provider_type in ("claude-cli", "claude_cli"):
        from .providers.claude_cli_provider import ClaudeCLIProvider
        return ClaudeCLIProvider(model=model, timeout=timeout)

    raise ValueError(
        f"Unknown provider type: {provider_type}. "
        "Supported: anthropic, openai, google, openrouter, ollama, custom, "
        "gemini-cli, codex-cli, claude-cli"
    )


def get_provider_for_phase(project_root: Path, phase: str) -> AIProvider:
    """Convenience: load config + create provider for a phase in one call."""
    config = load_ai_config(project_root)
    pc = get_provider_config(config, phase)
    return create_provider(pc)


def format_config_summary(config: dict) -> str:
    """Human-readable summary of AI configuration."""
    lines = []
    default = config.get("default_provider", {})
    default_name = f"{default.get('type', '?')}/{default.get('model', '?')}"
    lines.append(f"Default: {default_name}")

    phase_labels = {
        "phase1_planning": "Phase 1 (기획)",
        "phase2_development": "Phase 2 (전개)",
        "phase3_writing": "Phase 3 (집필)",
        "phase4_revision": "Phase 4 (퇴고)",
    }
    overrides = config.get("phase_overrides", {})
    for key in PHASE_KEYS:
        label = phase_labels.get(key, key)
        override = overrides.get(key)
        if override:
            name = f"{override.get('type', '?')}/{override.get('model', '?')}"
            lines.append(f"  {label}: {name}")
        else:
            lines.append(f"  {label}: (default)")

    if config.get("cost_tracking"):
        lines.append("Cost tracking: ON")

    return "\n".join(lines)
