"""Optional Inspect AI bridge: one generation, one decision, no tool execution."""

from __future__ import annotations

import asyncio
import copy
import hashlib
from importlib.metadata import version
from pathlib import Path


class InspectAdapter:
    def __init__(self, model: str, max_output_tokens: int = 256,
                 temperature=None, reasoning_effort=None, timeout: float = 60,
                 model_args=None, cache_prompt=None, null_only_unkeyed: bool = False):
        try:
            from inspect_ai.model import GenerateConfig, get_model
        except ImportError as exc:
            raise RuntimeError("Inspect runner requires Python >=3.11 and pip install '.[inspect]'") from exc
        if max_output_tokens <= 0 or timeout <= 0:
            raise ValueError("max_output_tokens and timeout must be positive")
        self.config = GenerateConfig(max_tokens=max_output_tokens, max_retries=0,
                                     timeout=timeout, temperature=temperature,
                                     reasoning_effort=reasoning_effort,
                                     cache_prompt=cache_prompt,
                                     parallel_tool_calls=False)
        kwargs = dict(model_args or {})
        if any(k in kwargs for k in ("api_key", "default_headers", "http_client")):
            raise ValueError("supply credentials through the provider environment, not recorded model_args")
        if model == "mockllm/retrybench-defer":
            from inspect_ai.model import ChatMessageAssistant, ChatCompletionChoice, ModelOutput
            from inspect_ai.tool import ToolCall

            def mock_output(*args):
                return ModelOutput(model=model, choices=[ChatCompletionChoice(
                    message=ChatMessageAssistant(content="", tool_calls=[ToolCall(
                        id="synthetic", function="decision",
                        arguments={"action": "unresolved", "idempotency_key": None})]),
                    stop_reason="tool_calls")])

            kwargs["custom_outputs"] = mock_output
        self.model = get_model(model, config=self.config, memoize=False, **kwargs)
        self.null_only_unkeyed = null_only_unkeyed
        self.runner = asyncio.Runner()
        self.settings = {
            "adapter": "inspect", "inspect_ai_version": version("inspect-ai"),
            "adapter_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "generation": self.config.model_dump(mode="json", exclude_none=True),
            "model_args": dict(model_args or {}),
            "tool_choice": {"name": "decision"}, "cache": False,
            "interface": "single forced decision tool; no tool execution",
            "synthetic": model == "mockllm/retrybench-defer",
            "decision_interface": "inspect-null-only-unkeyed-v2" if null_only_unkeyed else "inspect-nullable-key-v1",
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            self.runner.run(self.model.__aexit__(*args))
        finally:
            self.runner.close()

    def __call__(self, case):
        return self.runner.run(self._generate(case))

    async def _generate(self, case):
        from inspect_ai.log import Transcript, transcript
        # Pinned Inspect 0.3.281's standalone default retains only five raw calls
        # per model. Install a per-decision transcript with explicit full capture.
        from inspect_ai.log._transcript import init_transcript
        from inspect_ai.model import ChatMessageSystem, ChatMessageUser
        from inspect_ai.tool import ToolFunction, ToolInfo, ToolParams

        messages = [ChatMessageSystem(content=case["instructions"]),
                    ChatMessageUser(content=case["prompt"])]
        schema = copy.deepcopy(case["decision_schema"])
        if self.null_only_unkeyed and "retry_with_key" not in schema["properties"]["action"]["enum"]:
            schema["properties"]["idempotency_key"] = {
                "type": "null", "description": "This case has no keyed retry action; this field must be null."}
        tool = ToolInfo(name="decision", description="Record the first recovery decision.",
                        parameters=ToolParams.model_validate(schema))
        init_transcript(Transcript(log_model_api=True))
        output, error = None, None
        try:
            output = await self.model.generate(messages, tools=[tool],
                                               tool_choice=ToolFunction(name="decision"),
                                               config=self.config, cache=False)
        except Exception as exc:
            error = "%s: %s" % (type(exc).__name__, exc)
        events = [event for event in transcript().events if event.event == "model"]
        calls = [event.call.model_dump(mode="json") for event in events if event.call is not None]
        record = {
            "raw_model_output": output.model_dump(mode="json") if output is not None else None,
            "raw_calls": calls,
            "transcript_attachments": dict(transcript().attachments),
            "raw_provider_response_available": any(c.get("response") is not None for c in calls),
            "request": {"messages": [m.model_dump(mode="json") for m in messages],
                        "tools": [tool.model_dump(mode="json")], **self.settings},
            "returned_model": output.model if output is not None else None,
        }
        if error is not None:
            return {**record, "status": "adapter_error", "error": error}
        if output.usage is not None:
            record["usage"] = output.usage.model_dump(mode="json", exclude_none=True)
            if output.usage.total_cost is not None:
                record["usage"]["cost_usd"] = output.usage.total_cost
        if output.error or len(output.choices) != 1:
            return {**record, "status": "invalid_output", "error": "expected one completed choice"}
        choice = output.choices[0]
        tools = choice.message.tool_calls or []
        if choice.stop_reason not in ("stop", "tool_calls") or len(tools) != 1:
            return {**record, "status": "invalid_output", "error": "expected one complete decision tool call"}
        call = tools[0]
        if (call.function != "decision" or call.parse_error or not isinstance(call.arguments, dict)
                or set(call.arguments) != {"action", "idempotency_key"}):
            return {**record, "status": "invalid_output", "error": "invalid decision tool arguments"}
        return {**record, "status": "complete", "action": call.arguments["action"],
                "arguments": {"idempotency_key": call.arguments["idempotency_key"]}}
