"""Configuration shared by every source: environment parsing, cache location, User-Agent.

Each source has its own ``Settings`` dataclass (``dismal.bls.config.Settings``,
...) with its own environment-variable prefix (``BLS_``, ``BEA_``, ``FRED_``),
default endpoint and extras. They all extend :class:`BaseSettings` and build
themselves with :func:`settings_kwargs_from_env`, so the rules for reading the
environment are written once.

The API key is **only** read from the environment; it is never accepted on the
command line so it cannot leak into shell history or process listings (see
``docs/adr/0003-api-key-from-environment.md``).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_URL = "https://github.com/rtrimble13/dismal"
DEFAULT_MAX_RETRIES = 3
ENV_NO_COLOR = "NO_COLOR"


@dataclass(frozen=True)
class EnvNames:
    """The environment variables one source reads, derived from its prefix."""

    prefix: str

    @property
    def api_key(self) -> str:
        return f"{self.prefix}_API_KEY"

    @property
    def base_url(self) -> str:
        return f"{self.prefix}_API_BASE_URL"

    @property
    def timeout(self) -> str:
        return f"{self.prefix}_TIMEOUT"

    @property
    def max_retries(self) -> str:
        return f"{self.prefix}_MAX_RETRIES"

    @property
    def cache_dir(self) -> str:
        return f"{self.prefix}_CACHE_DIR"

    @property
    def user_agent(self) -> str:
        return f"{self.prefix}_USER_AGENT"

    @property
    def format(self) -> str:
        return f"{self.prefix}_FORMAT"

    def all(self) -> list[str]:
        """The variables in the order ``config`` lists them."""
        return [
            self.api_key,
            self.base_url,
            self.timeout,
            self.max_retries,
            self.cache_dir,
            self.user_agent,
            self.format,
        ]


def default_cache_dir(source: str, env: Mapping[str, str] | None = None) -> Path:
    """Return the XDG-style cache directory for ``source``: ``~/.cache/dismal/<source>``."""
    env = os.environ if env is None else env
    xdg = env.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "dismal" / source


def default_user_agent() -> str:
    from dismal import __version__

    return f"dismal/{__version__} (+{REPO_URL})"


def env_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def env_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def settings_kwargs_from_env(
    env: Mapping[str, str],
    *,
    names: EnvNames,
    source: str,
    default_base_url: str,
    default_timeout: float,
    default_max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    """Read the common settings for ``source`` from ``env`` (keyword arguments for ``Settings``)."""
    api_key = (env.get(names.api_key) or "").strip() or None
    cache_dir_raw = env.get(names.cache_dir)
    return {
        "api_key": api_key,
        "base_url": (env.get(names.base_url) or default_base_url).rstrip("/"),
        "timeout": env_float(env, names.timeout, default_timeout),
        "max_retries": env_int(env, names.max_retries, default_max_retries),
        "cache_dir": Path(cache_dir_raw).expanduser()
        if cache_dir_raw
        else default_cache_dir(source, env),
        "user_agent": env.get(names.user_agent) or default_user_agent(),
        "default_format": (env.get(names.format) or "").strip().lower() or None,
        "no_color": bool(env.get(ENV_NO_COLOR)),
    }


@dataclass(frozen=True)
class BaseSettings:
    """Effective configuration for one CLI invocation or client instance.

    Sources subclass this to set their own defaults (endpoint, timeout, cache
    directory) and add source-specific fields.
    """

    api_key: str | None = None
    base_url: str = ""
    timeout: float = 30.0
    max_retries: int = DEFAULT_MAX_RETRIES
    cache_dir: Path = field(default_factory=lambda: default_cache_dir("dismal"))
    user_agent: str = field(default_factory=default_user_agent)
    default_format: str | None = None
    no_color: bool = False

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def masked_api_key(self) -> str:
        """Return the key with all but the last four characters hidden."""
        if not self.api_key:
            return "(not set)"
        if len(self.api_key) <= 4:
            return "*" * len(self.api_key)
        return "*" * (len(self.api_key) - 4) + self.api_key[-4:]
