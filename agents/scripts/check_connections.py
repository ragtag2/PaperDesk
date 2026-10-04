"""Check MongoDB and Groq access without sending database records to the model."""

import json

from groq import Groq

from agents.config import Settings
from agents.database import create_mongo_client
from agents.scripts.run_live import safe_error


def main() -> int:
    results = {}
    try:
        settings = Settings.from_env()
    except Exception as error:
        print(json.dumps({"configuration": {"ok": False, "error": safe_error(error)}}, indent=2))
        return 1
    try:
        with create_mongo_client(settings) as client:
            client.admin.command("ping")
            database = client[settings.mongodb_db_name]
            results["mongodb"] = {
                "ok": True,
                "tickets": database.tickets.count_documents({}),
                "teams": database.teams.count_documents({}),
                "activeTeamMembers": database.users.count_documents({
                    "isActive": True, "teamId": {"$type": "objectId"},
                }),
            }
    except Exception as error:
        results["mongodb"] = {"ok": False, "error": safe_error(error)}
    if settings.model.startswith("groq:"):
        try:
            model_id = settings.model.split(":", 1)[1]
            with Groq(timeout=settings.model_timeout_seconds, max_retries=0) as client:
                available = {model.id for model in client.models.list().data}
            results["groq"] = {"ok": model_id in available, "model": model_id}
            if model_id not in available:
                results["groq"]["error"] = "The selected model is not listed by Groq for this key."
        except Exception as error:
            results["groq"] = {"ok": False, "error": safe_error(error)}
    print(json.dumps(results, indent=2))
    return 0 if all(result["ok"] for result in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
