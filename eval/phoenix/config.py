"""Explicit gateway configuration; imports and dry-runs never require secrets."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

load_dotenv()
# Phoenix prints Unicode progress markers; Windows redirected consoles may
# otherwise default to cp1252 and abort an otherwise valid experiment.
if os.name == "nt":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
ROOT = Path(__file__).resolve().parents[2]
MODULE = Path(__file__).resolve().parent
os.environ.setdefault("PHOENIX_WORKING_DIR", str(ROOT / ".phoenix"))


def api_url(base: str, path: str = "/api/v1") -> str:
    """Accept a gateway origin or a complete API base; never append v1 twice."""
    parsed = urlsplit(base.rstrip("/"))
    if (
        parsed.scheme not in ("https", "http")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Gateway URL must be an HTTP(S) API base without "
            "credentials, query, or fragment."
        )
    if parsed.scheme == "http" and parsed.hostname not in (
        "localhost",
        "127.0.0.1",
        "::1",
    ):
        raise ValueError("Use HTTPS for a remote model gateway.")
    if not path.startswith("/") or "?" in path or "#" in path or "://" in path:
        raise ValueError("USAI_API_PATH must be a relative API path such as /api/v1.")
    current = parsed.path.rstrip("/")
    if current.endswith(("/chat/completions", "/responses", "/models")):
        raise ValueError(
            "Provide the API base, not a specific inference/models endpoint."
        )
    if not current.endswith("/v1") and not current.endswith(path.rstrip("/")):
        current += path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, current, "", ""))


@dataclass(frozen=True)
class Gateway:
    base_url: str
    model: str
    api_key: str = field(repr=False)
    timeout: float = 90
    provider: str = "openai"
    deployment: str | None = None

    def public_config(self) -> dict:
        # URLs can identify private infrastructure; only the model is traced.
        return {
            "model": self.model,
            "provider": self.provider,
            "api_protocol": "openai_chat_completions",
        }


def gateway(role: str) -> Gateway:
    if role not in ("agent", "judge"):
        raise ValueError("Gateway role must be agent or judge")
    provider = os.getenv("MODEL_PROVIDER", "openai").strip()
    if provider == "digital_gateway":
        from eval.phoenix.digital_gateway import configuration

        return configuration(role)
    if provider != "openai":
        raise ValueError("MODEL_PROVIDER must be openai or digital_gateway")
    base = os.getenv("USAI_BASE_URL", "").strip()
    key = os.getenv("USAI_API_KEY", "").strip()
    model = os.getenv("AGENT_MODEL" if role == "agent" else "JUDGE_MODEL", "").strip()
    if role == "judge":
        base = os.getenv("JUDGE_BASE_URL", base).strip()
        key = os.getenv("JUDGE_API_KEY", key).strip()
    if not base or not key or not model:
        raise ValueError(
            f"Configure USAI_BASE_URL, USAI_API_KEY, and {role.upper()}_MODEL "
            "in the ignored repository-root .env. Judge overrides are optional."
        )
    if model.startswith(("your-", "replace-")) or key.startswith("replace-"):
        raise ValueError("Replace gateway/model placeholders before a live experiment.")
    return Gateway(
        api_url(base, os.getenv("USAI_API_PATH", "/api/v1")),
        model,
        key,
        float(os.getenv("MODEL_TIMEOUT_SECONDS", "90")),
    )


def validate_models() -> dict:
    agent, judge = gateway("agent"), gateway("judge")
    return {
        "agent": agent.public_config(),
        "judge": judge.public_config(),
        "same_model": (
            agent.provider == judge.provider
            and agent.base_url == judge.base_url
            and (agent.deployment or agent.model) == (judge.deployment or judge.model)
        ),
    }


def phoenix_endpoint() -> str:
    return os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006").rstrip("/")
