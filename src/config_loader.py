"""
Centralised configuration loader.

Reads config/config.yaml, expands ${VAR:-default} style environment
placeholders, and exposes a single CONFIG dict plus helpers. Importing this
module from anywhere in src/ guarantees every stage uses the same parameters.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()  # pull DB_*, SEC_USER_AGENT, etc. from .env if present

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _expand_env(value):
    """Replace ${VAR} or ${VAR:-default} inside strings, recursively."""
    if isinstance(value, str):
        def repl(match):
            var, default = match.group(1), match.group(2)
            return os.environ.get(var, default if default is not None else "")
        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return _expand_env(raw)


CONFIG = load_config()


def path(key: str) -> Path:
    """Resolve a path defined under config.paths to an absolute Path."""
    rel = CONFIG["paths"][key]
    p = PROJECT_ROOT / rel
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_url() -> str:
    """
    SQLAlchemy connection URL.

    Managed hosts (Supabase, Neon, Railway, ...) hand you a single connection
    string. If DATABASE_URL is set in the environment (.env or a CI secret) we
    use it verbatim, only normalising the scheme so SQLAlchemy routes it
    through psycopg2. Otherwise we assemble one from config.database.

    For Supabase, copy the "Connection string" (URI) from
    Project Settings -> Database. Append ?sslmode=require if it is not already
    present, since Supabase requires TLS.
    """
    raw = os.environ.get("DATABASE_URL", "").strip()
    if raw:
        if raw.startswith("postgresql://"):
            raw = raw.replace("postgresql://", "postgresql+psycopg2://", 1)
        elif raw.startswith("postgres://"):
            raw = raw.replace("postgres://", "postgresql+psycopg2://", 1)
        if "sslmode=" not in raw:
            raw += ("&" if "?" in raw else "?") + "sslmode=require"
        return raw

    d = CONFIG["database"]
    return (
        f"postgresql+psycopg2://{d['user']}:{d['password']}"
        f"@{d['host']}:{d['port']}/{d['dbname']}"
    )
