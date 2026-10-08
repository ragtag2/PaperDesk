"""Optional Langfuse traces around the complete incident coordination workflow."""

import logging
from contextlib import ExitStack, contextmanager

from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler
from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

from .config import Settings
from .reporting import AnalysisReport, redact_secrets, safe_error


logger = logging.getLogger(__name__)


def mask_payload(*, data, **_kwargs):
    return redact_secrets(data)


def mask_exported_spans(*, params):
    """Also redact exception/attribute text created by callback instrumentation."""
    patches = {}
    for identifier, span in params.spans.items():
        replacements = {}
        for key, value in span.attributes.items():
            masked = redact_secrets(value)
            if masked != value:
                replacements[key] = masked
        if replacements:
            patches[identifier] = OtelSpanPatch(set_attributes=replacements)
    return MaskOtelSpansResult(span_patches=patches) if patches else None


class RedactingCallbackHandler(CallbackHandler):
    """Redact callback errors before the SDK writes their OTel status text."""

    @staticmethod
    def tracing_error(error):
        return RuntimeError(safe_error(error)) if redact_secrets(str(error)) != str(error) else error

    def on_llm_error(self, error, **kwargs):
        return super().on_llm_error(self.tracing_error(error), **kwargs)

    def on_tool_error(self, error, **kwargs):
        return super().on_tool_error(self.tracing_error(error), **kwargs)

    def on_chain_error(self, error, **kwargs):
        return super().on_chain_error(self.tracing_error(error), **kwargs)


def close_trace_context(stack: ExitStack):
    try:
        stack.close()
    except Exception as error:
        logger.warning("Could not close Langfuse observation: %s", safe_error(error))


class AnalysisTrace:
    """Per-request tracing state; tracing failures never replace application errors."""

    def __init__(self, client=None, observation=None, callback=None):
        self.client = client
        self.observation = observation
        self.callbacks = [callback] if callback is not None else []

    def update(self, **values):
        if self.observation is not None:
            try:
                self.observation.update(**values)
            except Exception as error:
                logger.warning("Could not update Langfuse observation: %s", safe_error(error))

    @contextmanager
    def step(self, name: str, *, input=None):
        stack = ExitStack()
        step = AnalysisTrace()
        if self.client is not None:
            try:
                observation = stack.enter_context(self.client.start_as_current_observation(
                    name=name, as_type="span", input=input,
                ))
                step = AnalysisTrace(self.client, observation)
            except Exception as error:
                close_trace_context(stack)
                logger.warning("Could not start Langfuse step: %s", safe_error(error))
        try:
            yield step
        except Exception as error:
            step.update(level="ERROR", status_message=safe_error(error))
            raise
        finally:
            # Close without forwarding the exception; its redacted form is above.
            close_trace_context(stack)


class AnalysisTracing:
    def __init__(self, client=None, *, public_key: str | None = None, trace_url_template: str | None = None):
        self.client = client
        self.public_key = public_key
        self.trace_url_template = trace_url_template

    @classmethod
    def from_settings(cls, settings: Settings):
        if not settings.langfuse_tracing_enabled:
            return cls()
        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            if settings.langfuse_public_key or settings.langfuse_secret_key:
                logger.warning("Both Langfuse keys are required; tracing is disabled.")
            return cls()
        try:
            client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_base_url,
                environment=settings.langfuse_environment,
                timeout=2,
                mask=mask_payload,
                mask_otel_spans=mask_exported_spans,
            )
        except Exception as error:
            logger.warning("Langfuse initialization failed; tracing is disabled: %s", safe_error(error))
            return cls()
        tracing = cls(client, public_key=settings.langfuse_public_key)
        # Resolve the project once at startup, never during a ticket analysis.
        placeholder = "0" * 32
        try:
            url = client.get_trace_url(trace_id=placeholder)
            if url:
                tracing.trace_url_template = url.replace(placeholder, "{trace_id}")
                logger.info("Langfuse tracing ready at %s.", settings.langfuse_base_url)
            else:
                logger.warning("Langfuse trace links are unavailable; check the endpoint and keys.")
        except Exception as error:
            logger.warning("Could not resolve Langfuse trace links: %s", safe_error(error))
        return tracing

    @contextmanager
    def analysis(self, report: AnalysisReport, prompt_version: str):
        stack = ExitStack()
        trace = AnalysisTrace()
        if self.client is not None:
            try:
                metadata = {
                    "ticketId": report.data["ticketId"],
                    "analysisId": report.data["analysisId"],
                    "model": report.data["model"],
                    "promptVersion": prompt_version,
                }
                observation = stack.enter_context(self.client.start_as_current_observation(
                    name="ticket-analysis", as_type="agent",
                    input={"ticketId": report.data["ticketId"]},
                    metadata=metadata, version=prompt_version,
                ))
                stack.enter_context(propagate_attributes(
                    trace_name="ticket-analysis", session_id=report.data["ticketId"],
                    metadata=metadata, version=prompt_version, tags=["ticket-analysis"],
                ))
                trace_id = observation.trace_id
                trace = AnalysisTrace(self.client, observation, RedactingCallbackHandler(public_key=self.public_key))
                report.data["langfuseTraceId"] = trace_id
                report.data["langfuseTraceUrl"] = (
                    self.trace_url_template.format(trace_id=trace_id)
                    if self.trace_url_template else None
                )
            except Exception as error:
                close_trace_context(stack)
                trace = AnalysisTrace()
                logger.warning("Could not start Langfuse analysis: %s", safe_error(error))
        try:
            yield trace
        finally:
            trace.update(
                output=report.data["result"],
                level="ERROR" if report.data["status"] == "failed" else "DEFAULT",
                status_message=report.data.get("error"),
                metadata={
                    "status": report.data["status"], "httpStatus": report.data["httpStatus"],
                    "analysisSeconds": report.data.get("analysisSeconds"),
                    "metrics": report.data["metrics"], "checks": report.data["checks"],
                },
            )
            close_trace_context(stack)

    def shutdown(self):
        if self.client is not None:
            try:
                self.client.shutdown()
            except Exception as error:
                logger.warning("Could not flush Langfuse during shutdown: %s", safe_error(error))
