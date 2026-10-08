"""Manually isolate endpoint, token-parameter and initial tool-call failures.

Makes at most six model requests (three with --tools-only), stopping at the first
failure. No MongoDB, Langfuse, seed, experiment or actual database tool calls occur. Credentials are
read from agents/.env; light.py is neither imported nor executed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI
from langchain.agents.structured_output import OutputToolBinding, ToolStrategy
from langchain_core.messages import ToolMessage

from agents.agent import SYSTEM_PROMPT
from agents.config import Settings
from agents.model import create_model
from agents.reporting import redact_secrets, safe_error
from agents.schemas import TeamAssessment
from agents.tools import create_database_tools


class NoDatabase:
    """Tool schemas can be bound, but a probe must never execute these tools."""

    def get_ticket(self, ticket_id):
        raise RuntimeError("Model probes must not read the database.")

    def list_teams(self):
        raise RuntimeError("Model probes must not read the database.")

    def get_team_members(self, team_id):
        raise RuntimeError("Model probes must not read the database.")


def probe(name: str, request: Callable, *, require_tools: bool = False, captured: list | None = None) -> bool:
    try:
        result = request()
        if hasattr(result, "choices"):
            choice = result.choices[0]
            details = {"finish_reason": choice.finish_reason,
                       "content_present": bool(choice.message.content)}
        else:
            details = {"content_present": bool(result.content),
                       "tool_calls": [call["name"] for call in result.tool_calls],
                       "reasoning_content_present": "reasoning_content" in result.additional_kwargs}
            if require_tools and not result.tool_calls:
                raise ValueError("The agent requires tool calls, but the probe returned none.")
            if not result.tool_calls and not result.content:
                raise ValueError(f"Empty model response; finish_reason={result.response_metadata.get('finish_reason')!r}.")
        if captured is not None:
            captured.append(result)
        print(json.dumps({"stage": name, "ok": True, **details}))
        return True
    except Exception as error:
        details = {"stage": name, "ok": False, "error": safe_error(error),
                   "status_code": getattr(error, "status_code", None)}
        body = getattr(error, "body", None)
        if body is not None:
            details["body"] = redact_secrets(body)
        print(json.dumps(details, default=str))
        print("Stopped here. Resolve this stage before running the ten-ticket experiment.")
        return False


def check_tools(settings: Settings) -> bool:
    model = create_model(settings)
    echo = {"type": "function", "function": {
        "name": "echo", "description": "Return the supplied text.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
                       "required": ["text"], "additionalProperties": False},
    }}
    bound_echo = model.bind_tools([echo], tool_choice="auto")
    messages = [{"role": "user", "content": "Use echo once with text hello, then report its returned text."}]
    captured = []
    if not probe("single_tool_auto", lambda: bound_echo.invoke(messages),
                 require_tools=True, captured=captured):
        return False

    def continue_tool_exchange():
        assistant = captured[0]
        replies = []
        for call in assistant.tool_calls:
            if call["name"] != "echo" or not isinstance(call["args"].get("text"), str):
                raise ValueError("The probe returned an invalid echo tool call.")
            # Supply an artificial response directly; do not invoke any tool.
            replies.append(ToolMessage(content=call["args"]["text"], tool_call_id=call["id"]))
        return bound_echo.invoke([*messages, assistant, *replies])

    if not probe("tool_reply_roundtrip", continue_tool_exchange):
        return False

    # Use the actual database-tool schemas and the agent's ToolStrategy schema.
    # This only requests the initial model response; returned tools are not run.
    tools = create_database_tools(NoDatabase())
    tools.extend(OutputToolBinding.from_schema_spec(spec).tool
                 for spec in ToolStrategy(TeamAssessment).schema_specs)
    bound = model.bind_tools(tools, tool_choice="any")
    print(json.dumps({"requested_tool_choice": "any", "effective_tool_choice": bound.kwargs.get("tool_choice")}))
    return probe("agent_initial_tool_call_auto", lambda: bound.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Analyze ticket 300000000000000000000001 using the database tools."},
    ]), require_tools=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-only", action="store_true", help="Skip the three completion checks that already passed.")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    if not settings.model.startswith("openai:") or not settings.model_base_url:
        raise ValueError("This probe requires the configured custom openai: model endpoint.")
    model_id = settings.model.split(":", 1)[1]
    print(json.dumps({"model": model_id, "base_url": settings.model_base_url,
                      "timeout_seconds": settings.model_timeout_seconds,
                      "max_tokens": settings.model_max_tokens, "max_retries": 0}))
    if not args.tools_only:
        messages = [{"role": "user", "content": [{"type": "text", "text": "Hello, world!"}]}]
        with OpenAI(base_url=settings.model_base_url, api_key=settings.model_api_key,
                    timeout=settings.model_timeout_seconds, max_retries=0) as client:
            # Match light.py first, then compare token parameter names independently.
            if not probe("minimal_like_light_py", lambda: client.chat.completions.create(
                model=model_id, messages=messages,
            )):
                return 1
            for token_parameter in ("max_tokens", "max_completion_tokens"):
                if not probe(token_parameter, lambda: client.chat.completions.create(
                    model=model_id, messages=messages, temperature=0, stream=False,
                    **{token_parameter: settings.model_max_tokens},
                )):
                    return 1
    if not check_tools(settings):
        return 1
    print("Selected probes passed, including a tool reply exchange. Full agent execution is still untested.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Model probe failed: {safe_error(error)}", file=sys.stderr)
        sys.exit(1)
