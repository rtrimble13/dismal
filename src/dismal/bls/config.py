"""Runtime configuration for the BLS source, sourced from ``BLS_*`` environment variables.

The API key is **only** read from the environment (``BLS_API_KEY``); it is never
accepted on the command line so it cannot leak into shell history or process
listings (see ``docs/adr/0003-api-key-from-environment.md``).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dismal.core.config import (
    DEFAULT_MAX_RETRIES,
    ENV_NO_COLOR,
    BaseSettings,
    EnvNames,
    default_user_agent,
    settings_kwargs_from_env,
)

SOURCE = "bls"
DEFAULT_BASE_URL = "https://api.bls.gov/publicAPI/v2"
DEFAULT_FLATFILE_BASE_URL = "https://download.bls.gov/pub/time.series"
DEFAULT_TIMEOUT = 30.0

ENV = EnvNames("BLS")
ENV_API_KEY = ENV.api_key
ENV_BASE_URL = ENV.base_url
ENV_FLATFILE_BASE_URL = "BLS_FLATFILE_BASE_URL"
ENV_TIMEOUT = ENV.timeout
ENV_MAX_RETRIES = ENV.max_retries
ENV_CACHE_DIR = ENV.cache_dir
ENV_USER_AGENT = ENV.user_agent
ENV_FORMAT = ENV.format

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_FLATFILE_BASE_URL",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT",
    "ENV",
    "ENV_API_KEY",
    "ENV_BASE_URL",
    "ENV_CACHE_DIR",
    "ENV_FLATFILE_BASE_URL",
    "ENV_FORMAT",
    "ENV_MAX_RETRIES",
    "ENV_NO_COLOR",
    "ENV_TIMEOUT",
    "ENV_USER_AGENT",
    "SOURCE",
    "Settings",
    "default_cache_dir",
    "default_user_agent",
]


def default_cache_dir(env: Mapping[str, str] | None = None) -> Path:
    """Return the cache directory for BLS metadata: ``~/.cache/dismal/bls``."""
    from dismal.core.config import default_cache_dir as _default

    return _default(SOURCE, env)


@dataclass(frozen=True)
class Settings(BaseSettings):
    """Effective configuration for one CLI invocation or client instance."""

    base_url: str = DEFAULT_BASE_URL
    flatfile_base_url: str = DEFAULT_FLATFILE_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    cache_dir: Path = field(default_factory=default_cache_dir)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        common = settings_kwargs_from_env(
            env,
            names=ENV,
            source=SOURCE,
            default_base_url=DEFAULT_BASE_URL,
            default_timeout=DEFAULT_TIMEOUT,
        )
        return cls(
            flatfile_base_url=(env.get(ENV_FLATFILE_BASE_URL) or DEFAULT_FLATFILE_BASE_URL).rstrip(
                "/"
            ),
            **common,
        )
