"""Verify the configured Langfuse endpoint and keys without creating a trace."""

import json

from agents.config import Settings
from agents.reporting import safe_error
from agents.tracing import AnalysisTracing


def main() -> int:
    tracing = None
    try:
        settings = Settings.from_env()
        tracing = AnalysisTracing.from_settings(settings)
        if tracing.client is None:
            raise ValueError("Configure both Langfuse keys and enable tracing in agents/.env.")
        if not tracing.client.auth_check():
            raise ValueError("Langfuse authentication failed. Check the endpoint and keys.")
        print(json.dumps({"langfuse": {
            "ok": True, "baseUrl": settings.langfuse_base_url,
            "environment": settings.langfuse_environment,
        }}, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"langfuse": {"ok": False, "error": safe_error(error)}}, indent=2))
        return 1
    finally:
        if tracing is not None:
            tracing.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
