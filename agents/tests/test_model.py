"""Check custom endpoint routing and credentials without provider requests."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from openai.types.chat import ChatCompletion

from agents.config import Settings
from agents.model import LightningDeepSeekChatOpenAI, create_model
from agents.reporting import redact_secrets
from experiments.check_model import main as check_model


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "MONGODB_URI": "mongodb://127.0.0.1:27017",
            "AGENT_MODEL": "openai:lightning-ai/deepseek-v4.1-flash",
            "AGENT_MODEL_BASE_URL": "https://lightning.ai/api/v1/",
            "AGENT_MODEL_API_KEY": "lightning-test-credential",
            "AGENT_MODEL_TIMEOUT_SECONDS": "20",
            "AGENT_MODEL_MAX_TOKENS": "2048",
        }
        self.enterContext(patch("agents.config.load_dotenv"))
        self.enterContext(patch.dict("os.environ", self.environment, clear=True))

    def test_lightning_adapter_preserves_api_model_and_can_bind_agent_tools(self):
        settings = Settings.from_env()
        model = create_model(settings)

        self.assertIsInstance(model, ChatOpenAI)
        self.assertIsInstance(model, LightningDeepSeekChatOpenAI)
        self.assertEqual(model.model_name, "lightning-ai/deepseek-v4.1-flash")
        self.assertEqual(model.openai_api_base, "https://lightning.ai/api/v1/")
        self.assertFalse(model.use_responses_api)
        self.assertEqual(model.request_timeout, 20)
        self.assertEqual(model.max_tokens, 2048)
        self.assertEqual(model.max_retries, 0)
        self.assertNotIn(settings.model_api_key, repr(settings))

        def read_ticket(ticket_id: str) -> str:
            """Read the current ticket by ID."""
            return ticket_id

        bound = model.bind_tools([read_ticket])
        function = bound.kwargs["tools"][0]["function"]
        self.assertEqual(function["name"], "read_ticket")
        self.assertEqual(function["parameters"]["properties"]["ticket_id"]["type"], "string")

    def test_lightning_deepseek_tool_strategy_uses_auto_and_preserves_tool_schema(self):
        model = create_model(Settings.from_env())

        def read_ticket(ticket_id: str) -> str:
            """Read a ticket by ID."""
            return ticket_id

        ordinary = model.bind_tools([read_ticket], tool_choice="auto")
        for selection in ("any", "required", True):
            with self.subTest(selection=selection):
                bound = model.bind_tools([read_ticket], tool_choice=selection)
                self.assertEqual(bound.kwargs["tool_choice"], "auto")
                self.assertEqual(bound.kwargs["tools"], ordinary.kwargs["tools"])

    def test_deepseek_reasoning_survives_response_and_followup_request(self):
        model = create_model(Settings.from_env())
        response = {
            "id": "test-completion", "object": "chat.completion", "created": 0,
            "model": "lightning-ai/deepseek-v4.1-flash",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": "", "reasoning_content": "Probe reasoning.",
                "tool_calls": [{"id": "probe-call", "type": "function", "function": {
                    "name": "read_ticket", "arguments": '{"ticket_id": "300000000000000000000001"}',
                }}],
            }}],
        }
        for completion in (response, ChatCompletion.model_validate(response)):
            with self.subTest(typed_response=isinstance(completion, ChatCompletion)):
                assistant = model._create_chat_result(completion).generations[0].message
                self.assertEqual(assistant.additional_kwargs["reasoning_content"], "Probe reasoning.")
                payload = model._get_request_payload([
                    {"role": "user", "content": "Read the ticket."}, assistant,
                    ToolMessage(content="Ticket data", tool_call_id="probe-call"),
                ])
                self.assertEqual(payload["messages"][1]["reasoning_content"], "Probe reasoning.")
                self.assertEqual(payload["messages"][1]["tool_calls"][0]["id"], "probe-call")
                self.assertEqual(payload["messages"][2]["tool_call_id"], "probe-call")

    def test_deepseek_compatibility_is_scoped_to_lightning_endpoint(self):
        with patch.dict("os.environ", {"AGENT_MODEL_BASE_URL": "https://another-provider.example/v1"}):
            model = create_model(Settings.from_env())
        self.assertIsInstance(model, ChatOpenAI)
        self.assertNotIsInstance(model, LightningDeepSeekChatOpenAI)
        bound = model.bind_tools([], tool_choice="required")
        self.assertEqual(bound.kwargs["tool_choice"], "required")

    def test_custom_endpoint_requires_both_settings_and_openai_adapter(self):
        for overrides in (
            {"AGENT_MODEL_API_KEY": ""},
            {"AGENT_MODEL_BASE_URL": ""},
            {"AGENT_MODEL": "groq:qwen/qwen3.8-27b", "GROQ_API_KEY": "groq-test"},
        ):
            with self.subTest(overrides=overrides), patch.dict("os.environ", overrides):
                with self.assertRaises(ValueError):
                    Settings.from_env()

    def test_standard_openai_settings_do_not_require_custom_endpoint(self):
        with patch.dict("os.environ", {
            "AGENT_MODEL": "openai:test-model",
            "AGENT_MODEL_BASE_URL": "",
            "AGENT_MODEL_API_KEY": "",
            "OPENAI_API_KEY": "standard-test-credential",
        }):
            model = create_model(Settings.from_env())
        self.assertIsInstance(model, ChatOpenAI)
        self.assertEqual(model.model_name, "test-model")
        self.assertEqual(model.openai_api_key.get_secret_value(), "standard-test-credential")

    def test_lightning_credential_is_redacted_from_nested_payloads(self):
        payload = {"error": [f"Provider error: {self.environment['AGENT_MODEL_API_KEY']}"]}
        self.assertEqual(redact_secrets(payload), {"error": ["Provider error: [redacted]"]})

    def test_probe_stops_after_minimal_request_fails_and_redacts_error(self):
        with patch("experiments.check_model.OpenAI") as raw_client, \
                patch("experiments.check_model.create_model") as adapter, \
                patch("builtins.print") as output:
            client = raw_client.return_value.__enter__.return_value
            client.chat.completions.create.side_effect = RuntimeError(self.environment["AGENT_MODEL_API_KEY"])
            self.assertEqual(check_model([]), 1)
        client.chat.completions.create.assert_called_once()
        adapter.assert_not_called()
        printed = " ".join(str(call) for call in output.call_args_list)
        self.assertIn("minimal_like_light_py", printed)
        self.assertNotIn(self.environment["AGENT_MODEL_API_KEY"], printed)
        self.assertIn("[redacted]", printed)

    def test_probe_isolates_completion_token_parameter_before_agent_tools(self):
        response = SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content="Hello"),
        )])
        with patch("experiments.check_model.OpenAI") as raw_client, \
                patch("experiments.check_model.create_model") as adapter, \
                patch("builtins.print"):
            client = raw_client.return_value.__enter__.return_value
            client.chat.completions.create.side_effect = [response, response, RuntimeError("unsupported parameter")]
            self.assertEqual(check_model([]), 1)
        calls = client.chat.completions.create.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertNotIn("max_tokens", calls[0].kwargs)
        self.assertEqual(calls[1].kwargs["max_tokens"], 2048)
        self.assertNotIn("max_completion_tokens", calls[1].kwargs)
        self.assertEqual(calls[2].kwargs["max_completion_tokens"], 2048)
        self.assertNotIn("max_tokens", calls[2].kwargs)
        adapter.assert_not_called()

    def test_tools_only_probe_skips_previously_passed_completion_requests(self):
        with patch("experiments.check_model.OpenAI") as raw_client, \
                patch("experiments.check_model.check_tools", return_value=False) as tools, \
                patch("builtins.print"):
            self.assertEqual(check_model(["--tools-only"]), 1)
        raw_client.assert_not_called()
        tools.assert_called_once()


if __name__ == "__main__":
    unittest.main()
