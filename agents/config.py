"""Read settings from the agent's own environment file or process environment."""

import os
from ipaddress import ip_address
from math import isfinite
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    mongodb_uri: str
    mongodb_db_name: str
    model: str
    mongodb_dns_servers: tuple[str, ...] = ()
    model_timeout_seconds: float = 20
    model_max_tokens: int = 2048
    langfuse_public_key: str = field(default="", repr=False)
    langfuse_secret_key: str = field(default="", repr=False)
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_tracing_enabled: bool = True
    langfuse_environment: str = "development"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(__file__).with_name(".env"))
        mongodb_uri = os.environ.get("MONGODB_URI", "").strip()
        model = os.environ.get("AGENT_MODEL", "").strip()
        if not mongodb_uri or not model:
            raise ValueError("Set MONGODB_URI and AGENT_MODEL in agents/.env.")
        # Groq's display name is capitalized, but its API model ID is lowercase.
        if model.lower() in ("groq:qwen/qwen3.8-27b", "qwen/qwen3.8-27b"):
            model = "groq:qwen/qwen3.8-27b"
        if model.startswith("groq:") and not os.environ.get("GROQ_API_KEY", "").strip():
            raise ValueError("Set GROQ_API_KEY in agents/.env to use Groq.")
        database_name = os.environ.get("MONGODB_DB_NAME", "paperdesk").strip()
        if not database_name:
            raise ValueError("MONGODB_DB_NAME must not be empty.")
        dns_servers = tuple(
            server.strip()
            for server in os.environ.get("MONGODB_DNS_SERVERS", "").split(",")
            if server.strip()
        )
        for server in dns_servers:
            ip_address(server)
        timeout = float(os.environ.get("AGENT_MODEL_TIMEOUT_SECONDS", "20"))
        max_tokens = int(os.environ.get("AGENT_MODEL_MAX_TOKENS", "2048"))
        if not isfinite(timeout) or timeout <= 0 or max_tokens <= 0:
            raise ValueError("Model timeout and token limit must be positive.")
        return cls(
            mongodb_uri=mongodb_uri,
            mongodb_db_name=database_name,
            model=model,
            mongodb_dns_servers=dns_servers,
            model_timeout_seconds=timeout,
            model_max_tokens=max_tokens,
            langfuse_public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip(),
            langfuse_secret_key=os.environ.get("LANGFUSE_SECRET_KEY", "").strip(),
            langfuse_base_url=os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").strip().rstrip("/"),
            langfuse_tracing_enabled=os.environ.get("LANGFUSE_TRACING_ENABLED", "true").strip().lower() == "true",
            langfuse_environment=os.environ.get("LANGFUSE_TRACING_ENVIRONMENT", "development").strip(),
        )
