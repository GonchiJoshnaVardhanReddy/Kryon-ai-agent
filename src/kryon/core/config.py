"""Kryon configuration system.

Loads from ``~/.kryon/config.yaml`` with environment variable override
using the ``KRYON__SECTION__KEY=value`` convention (double underscore
for nesting, e.g. ``KRYON__LLM__PROVIDER=ollama``).

**Single-mode**: the agent is one configurable tool, not three products.
The user customizes the agent for their context by setting the LLM
provider, model, cost budgets, and tool configuration. There are no
profile presets — ``KryonConfig()`` returns Pydantic defaults, and the
user customizes with ``kryon config set <key> <value>`` or by editing
``~/.kryon/config.yaml`` directly.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, SecretStr

from kryon.core.exceptions import ConfigError
from kryon.core.paths import kryon_config_file

# ============================================================================
# Sub-configs
# ============================================================================


class LLMConfig(BaseModel):
    """LLM provider configuration.

    ``provider`` is one of: anthropic, openai, azure, bedrock, ollama, custom.
    For Ollama, set ``base_url`` (e.g. ``http://localhost:11434``).
    For custom endpoints, set ``provider=custom`` and ``base_url``.

    For API keys, prefer the secrets manager (``kryon secrets set
    anthropic_api_key``) and let the LLM gateway resolve them. The
    ``api_key`` field here is a convenience for one-off runs; in
    production it should be left None.
    """

    provider: Literal["anthropic", "openai", "azure", "bedrock", "ollama", "custom"] = "anthropic"
    model: str = "claude-sonnet-4-5"
    api_key: SecretStr | None = None
    fallback_provider: str | None = None
    fallback_model: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    base_url: str | None = None  # for Ollama or custom endpoints
    timeout_seconds: int = 120
    max_retries: int = 3


class CostConfig(BaseModel):
    """Cost control configuration.

    ``default_per_target_usd`` is the per-engagement budget.
    ``hard_cap_usd`` is the global cap across all targets.
    ``warn_at_percent`` is when to start warning the user (% of either).
    """

    default_per_target_usd: float = 50.0
    warn_at_percent: int = Field(default=80, ge=0, le=100)
    hard_cap_usd: float = 500.0


class ScopeConfig(BaseModel):
    """Scope handling configuration."""

    default_path: Path | None = None
    allow_wildcards: bool = True
    dns_rebinding_check: bool = True
    require_explicit_authorization: bool = True


class OAuthConfig(BaseModel):
    """OAuth 2.1 configuration for an MCP server."""

    client_id: str
    client_secret: SecretStr
    scopes: list[str] = Field(default_factory=list)
    auth_url: str | None = None
    token_url: str | None = None


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server.

    Either ``command`` (for stdio) or ``url`` (for http/sse) must be set,
    matching the ``transport`` field.
    """

    name: str
    transport: Literal["stdio", "http", "sse"] = "stdio"
    command: list[str] | None = None  # for stdio
    url: str | None = None  # for http/sse
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    include_tools: list[str] | None = None  # None = all
    exclude_tools: list[str] = Field(default_factory=list)
    oauth: OAuthConfig | None = None
    timeout_seconds: int = 60


class MCPConfig(BaseModel):
    """MCP integration configuration."""

    servers: list[MCPServerConfig] = Field(default_factory=list)
    default_filter_mode: Literal["allowlist", "denylist"] = "allowlist"
    catalog_path: Path | None = None


class SandboxConfig(BaseModel):
    """Docker sandbox configuration for running tools.

    Defaults follow the principle of least privilege: read-only rootfs,
    all capabilities dropped, no new privileges, low PID/memory limits.
    """

    image: str = "kalilinux/kali-rolling:latest"
    read_only_root: bool = True
    drop_all_capabilities: bool = True
    no_new_privileges: bool = True
    pids_limit: int = 256
    mem_limit: str = "512m"
    cpu_quota: int = 50000
    timeout_seconds: int = 300
    network_mode: str = "bridge"


class ChannelConfig(BaseModel):
    """A single notification channel."""

    type: Literal["telegram", "discord", "slack", "email", "local"] = "local"
    enabled: bool = True
    # Telegram fields
    bot_token: SecretStr | None = None
    chat_id: str | None = None
    # Webhook fields (discord, slack)
    webhook_url: SecretStr | None = None
    # Email fields
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    from_address: str | None = None
    to_addresses: list[str] = Field(default_factory=list)
    # Local-file channel
    file_path: Path | None = None


class NotificationConfig(BaseModel):
    """Notification configuration."""

    channels: list[ChannelConfig] = Field(default_factory=list)
    min_severity: Literal["info", "warning", "critical"] = "info"


class AuditConfig(BaseModel):
    """Audit log configuration."""

    path: Path | None = None  # default: per-target audit.db
    retention_days: int = 90
    redact_secrets: bool = True
    enable_live_view: bool = True


class SubagentDefaults(BaseModel):
    """Default limits for subagents.

    ``max_iterations`` and ``max_cost_usd`` are safety bounds. Each
    subagent run is terminated if either is exceeded.
    """

    max_iterations: int = 30
    max_cost_usd: float = 0.50
    timeout_seconds: int = 300


# ============================================================================
# Root config (single mode, no profiles)
# ============================================================================


class KryonConfig(BaseModel):
    """Root configuration for Kryon.

    Single agent, configurable for any deployment context. No profile
    presets. The user customizes by setting individual values with
    ``kryon config set`` or by editing ``~/.kryon/config.yaml`` directly.

    Example: to use Ollama locally with a $5 budget, run::

        kryon config set llm.provider ollama
        kryon config set llm.model llama3.1:8b
        kryon config set cost.default_per_target_usd 5
    """

    llm: LLMConfig = Field(default_factory=LLMConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    scope: ScopeConfig = Field(default_factory=ScopeConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    subagent_defaults: SubagentDefaults = Field(default_factory=SubagentDefaults)


# ============================================================================
# Loaders / savers
# ============================================================================


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Apply ``KRYON__SECTION__KEY=value`` env var overrides to the config dict.

    Example: ``KRYON__LLM__PROVIDER=ollama`` → ``data['llm']['provider'] = 'ollama'``

    Missing intermediate sections are created on the fly so the user
    can set ``KRYON__LLM__BASE_URL=...`` without first writing the
    full LLM section to disk.
    """
    prefix = "KRYON__"
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        path = env_key[len(prefix) :].lower().split("__")
        if not path or path == [""]:
            continue
        # Navigate into the nested dict, creating missing sections.
        current = data
        for key in path[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[path[-1]] = _coerce_env_value(env_value)
    return data


def _coerce_env_value(value: str) -> Any:
    """Coerce an env var string to int/float/bool/str.

    Used by both the env-override pass and ``set_config_value`` so the
    user can type ``kryon config set cost.default_per_target_usd 5``
    and get an int / float, not a string.
    """
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def load_config(path: Path | None = None) -> KryonConfig:
    """Load configuration from a YAML file with env var override.

    If the file does not exist, returns ``KryonConfig()`` with Pydantic
    defaults — but env-var overrides (``KRYON__...``) are still applied.
    This lets a user override defaults at the shell without writing a
    config file (e.g. for one-off runs in CI).

    Does NOT write the file — that is ``kryon config init``'s job.

    Args:
        path: Path to the YAML config. Defaults to
            ``kryon_config_file()`` (``~/.kryon/config.yaml``).

    Returns:
        The validated ``KryonConfig``.

    Raises:
        ConfigError: On YAML parse failure or Pydantic validation failure.
    """
    if path is None:
        path = kryon_config_file()
    if not path.exists():
        data: dict[str, Any] = {}
    else:
        try:
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(
                f"Failed to parse config YAML at {path}",
                details={"path": str(path), "error": str(e)},
            ) from e
        if not isinstance(data, dict):
            raise ConfigError(
                f"Config file must be a YAML mapping, got {type(data).__name__}",
                details={"path": str(path)},
            )
    # Env vars are applied whether or not the file exists, so a
    # user can override defaults without first running `kryon config init`.
    data = _apply_env_overrides(data)
    try:
        return KryonConfig.model_validate(data)
    except Exception as e:
        raise ConfigError(
            f"Failed to validate config from {path}",
            details={"path": str(path), "error": str(e)},
        ) from e


def save_config(config: KryonConfig, path: Path | None = None) -> None:
    """Save configuration to a YAML file.

    SecretStr fields are serialized to ``"**********"`` (Pydantic's
    default for ``model_dump(mode="json")``). To set a real secret,
    use the secrets manager — not the config file.

    On POSIX, the file is written with 0600 permissions. On Windows
    the chmod is a no-op (NTFS ACLs differ).

    Args:
        config: The config to serialize.
        path: Where to write. Defaults to ``kryon_config_file()``.
    """
    if path is None:
        path = kryon_config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    data = _strip_none(data)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    # Best-effort 0600 on POSIX; Windows uses NTFS ACLs instead.
    with contextlib.suppress(OSError, AttributeError):
        path.chmod(0o600)


def _strip_none(data: Any) -> Any:
    """Recursively remove None values from a dict/list structure.

    Keeps the YAML output clean — only fields the user has actually
    set (or that have non-None defaults) appear in the file.
    """
    if isinstance(data, dict):
        return {k: _strip_none(v) for k, v in data.items() if v is not None}
    if isinstance(data, list):
        return [_strip_none(item) for item in data]
    return data


# ============================================================================
# Dot-notation getter/setter
# ============================================================================


def get_config_value(config: KryonConfig, dotted_key: str) -> Any:
    """Get a value from the config using dot notation (e.g., ``llm.provider``).

    SecretStr values are returned as ``"***REDACTED***"``.

    Args:
        config: The config to read from.
        dotted_key: Dot-notation path (e.g., ``llm.max_tokens``).

    Returns:
        The value at the path.

    Raises:
        ConfigError: If the key does not exist.
    """
    parts = dotted_key.split(".")
    current: Any = config
    for part in parts:
        if not hasattr(current, part):
            raise ConfigError(
                f"Unknown config key: {dotted_key}",
                details={"key": dotted_key},
            )
        current = getattr(current, part)
    if isinstance(current, SecretStr):
        return "***REDACTED***"
    return current


def set_config_value(
    config: KryonConfig,
    dotted_key: str,
    value: str,
) -> KryonConfig:
    """Set a value on the config using dot notation. Returns a new config.

    The input config is not mutated (the new config is re-validated
    via Pydantic from the modified dict).

    Note: this function does not handle SecretStr fields gracefully —
    setting ``llm.api_key`` via this path will round-trip through the
    redacted placeholder. Use ``kryon secrets set`` for credentials.

    Args:
        config: The current config.
        dotted_key: Dot-notation path (e.g., ``llm.provider``).
        value: The new value (string; will be coerced to int/float/bool).

    Returns:
        A new ``KryonConfig`` with the value set.

    Raises:
        ConfigError: If the key does not exist.
    """
    data = config.model_dump(mode="json")
    parts = dotted_key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            raise ConfigError(
                f"Unknown config section: {part!r}",
                details={"key": dotted_key, "missing_section": part},
            )
        current = current[part]
    if parts[-1] not in current:
        raise ConfigError(
            f"Unknown config key: {dotted_key}",
            details={
                "key": dotted_key,
                "section": parts[-2] if len(parts) > 1 else None,
            },
        )
    current[parts[-1]] = _coerce_env_value(value)
    try:
        return KryonConfig.model_validate(data)
    except Exception as e:
        raise ConfigError(
            f"Failed to validate config after setting {dotted_key}",
            details={"key": dotted_key, "value": value, "error": str(e)},
        ) from e


__all__ = [
    "AuditConfig",
    "ChannelConfig",
    "CostConfig",
    # Root
    "KryonConfig",
    # Sub-configs
    "LLMConfig",
    "MCPConfig",
    "MCPServerConfig",
    "NotificationConfig",
    "OAuthConfig",
    "SandboxConfig",
    "ScopeConfig",
    "SubagentDefaults",
    # Helpers
    "get_config_value",
    # Loaders / savers
    "load_config",
    "save_config",
    "set_config_value",
]
