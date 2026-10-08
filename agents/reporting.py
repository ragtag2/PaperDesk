"""Per-analysis JSON reports and model usage, including failed requests."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler


logger = logging.getLogger(__name__)
ANALYSES_DIRECTORY = Path(__file__).resolve().parent / "runs" / "analyses"


def redact_secrets(data):
    """Remove configured credentials from report errors and tracing payloads."""
    if isinstance(data, str):
        for name in ("GROQ_API_KEY", "OPENAI_API_KEY", "MONGODB_URI", "LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY"):
            value = os.environ.get(name)
            if value:
                data = data.replace(value, "[redacted]")
    elif isinstance(data, dict):
        return {key: redact_secrets(value) for key, value in data.items()}
    elif isinstance(data, (list, tuple)):
        return type(data)(redact_secrets(value) for value in data)
    return data


def safe_error(error: BaseException) -> str:
    return f"{type(error).__name__}: {redact_secrets(str(error))}"


class AnalysisMetrics(BaseCallbackHandler):
    """One callback instance per request; never record credentials or prompts."""

    def __init__(self):
        self._lock = Lock()
        self._starts = {}
        self._calls = {}
        self._database_tools = []

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        with self._lock:
            self._starts[run_id] = perf_counter()
            self._calls[run_id] = {
                "status": "running", "inputTokens": 0, "outputTokens": 0,
                "cachedInputTokens": 0, "toolCalls": [],
            }

    def on_llm_end(self, response, *, run_id, **kwargs):
        with self._lock:
            call = self._calls[run_id]
            call["status"] = "passed"
            call["elapsedSeconds"] = round(perf_counter() - self._starts[run_id], 3)
            for generations in response.generations:
                for generation in generations:
                    message = generation.message
                    usage = message.usage_metadata or {}
                    call["inputTokens"] += usage.get("input_tokens", 0)
                    call["outputTokens"] += usage.get("output_tokens", 0)
                    call["cachedInputTokens"] += (usage.get("input_token_details") or {}).get("cache_read", 0) or 0
                    call["toolCalls"].extend(tool["name"] for tool in message.tool_calls)

    def on_llm_error(self, error, *, run_id, **kwargs):
        with self._lock:
            self._calls[run_id].update({
                "status": "failed", "errorType": type(error).__name__,
                "elapsedSeconds": round(perf_counter() - self._starts[run_id], 3),
            })

    def on_tool_start(self, serialized, input_str, **kwargs):
        with self._lock:
            self._database_tools.append(serialized["name"])

    def snapshot(self, ticket_id: str, elapsed: float, result=None) -> dict:
        with self._lock:
            calls = list(self._calls.values())
            return {
                "ticketId": ticket_id,
                "elapsedSeconds": round(elapsed, 3),
                "modelCalls": len(calls),
                "toolCalls": [name for call in calls for name in call["toolCalls"]],
                "databaseToolCalls": list(self._database_tools),
                **{key: sum(call[key] for call in calls) for key in (
                    "inputTokens", "outputTokens", "cachedInputTokens",
                )},
                "modelRequests": calls,
                "relevantTeams": len(result.relevantTeams) if result else 0,
                "stakeholders": len(result.stakeholderUserIds) if result else 0,
            }


class AnalysisReport:
    def __init__(self, ticket_id: str, model: str):
        # Only validated ObjectIds are allowed to become directory names.
        if len(ticket_id) != 24 or any(c not in "0123456789abcdef" for c in ticket_id):
            raise ValueError("Invalid ticket ID for analysis report.")
        now = datetime.now(timezone.utc)
        analysis_id = now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
        self.path = ANALYSES_DIRECTORY / ticket_id / f"{analysis_id}.json"
        self.data = {
            "analysisId": analysis_id, "startedAt": now.isoformat(),
            "status": "running", "model": model, "ticketId": ticket_id,
            "ticketTitle": None, "teamCount": None, "httpStatus": None,
            "result": None, "checks": {}, "metrics": {},
        }

    def save(self):
        """Atomically replace the running report when the request finishes."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            # A logging failure must not discard a valid coordination result.
            logger.exception("Could not save analysis report %s.", self.path)
