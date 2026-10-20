import importlib.util
import tempfile
import unittest
from pathlib import Path

from retrybench import evaluate, public_cases


@unittest.skipUnless(importlib.util.find_spec("inspect_ai"), "optional Inspect AI is not installed")
class InspectAdapterTests(unittest.TestCase):
    def test_versioned_null_only_interface_changes_only_unkeyed_schema(self):
        from retrybench.inspect_adapter import InspectAdapter
        cases = public_cases()
        with InspectAdapter("mockllm/retrybench-defer", null_only_unkeyed=True) as adapter:
            for case in (cases[0], cases[-1]):
                record = adapter(case)
                actual = record["request"]["tools"][0]["parameters"]["properties"]["idempotency_key"]["type"]
                keyed = "retry_with_key" in case["decision_schema"]["properties"]["action"]["enum"]
                self.assertEqual(actual, ["string", "null"] if keyed else "null")
                self.assertEqual(case["decision_schema"]["properties"]["idempotency_key"]["type"], ["string", "null"])
            self.assertEqual(adapter.settings["decision_interface"], "inspect-null-only-unkeyed-v2")

    def test_real_inspect_mock_provider_and_raw_capture(self):
        from retrybench.inspect_adapter import InspectAdapter
        with tempfile.TemporaryDirectory() as d, InspectAdapter("mockllm/retrybench-defer") as adapter:
            result = evaluate("mockllm/retrybench-defer", adapter, settings=adapter.settings,
                              limit=12, output_dir=Path(d))
            self.assertEqual(result.report["metrics"]["status_counts"], {"valid": 12, "missing": 228})
            for p in result.predictions:
                self.assertTrue(p["raw_provider_response_available"])
                self.assertEqual(p["raw_model_output"]["choices"][0]["message"]["tool_calls"][0]["arguments"],
                                 {"action": "unresolved", "idempotency_key": None})
            self.assertEqual(adapter.settings["generation"]["max_retries"], 0)

    def test_multiple_tool_calls_and_truncation_are_invalid(self):
        from retrybench.inspect_adapter import InspectAdapter
        from inspect_ai.model import ModelOutput, ChatCompletionChoice, ChatMessageAssistant, get_model
        from inspect_ai.tool import ToolCall
        for count, reason in ((2, "tool_calls"), (1, "max_tokens"), (0, "stop")):
            out = ModelOutput(model="mock", choices=[ChatCompletionChoice(
                message=ChatMessageAssistant(content="", tool_calls=[
                    ToolCall(id=str(i), function="decision", arguments={"action": "stop", "idempotency_key": None})
                    for i in range(count)]), stop_reason=reason)])
            with InspectAdapter("mockllm/retrybench-defer") as adapter:
                adapter.model = get_model("mockllm/model", custom_outputs=[out], memoize=False)
                record = adapter(public_cases()[0])
                self.assertEqual(record["status"], "invalid_output")
                self.assertIn("raw_model_output", record)

    def test_provider_exception_is_not_retried_and_request_is_retained(self):
        from retrybench.inspect_adapter import InspectAdapter
        from inspect_ai.model import get_model
        calls = []
        def fail(*args):
            calls.append(1)
            raise RuntimeError("synthetic failure")
        with InspectAdapter("mockllm/retrybench-defer") as adapter:
            adapter.model = get_model("mockllm/model", custom_outputs=fail, memoize=False)
            result = evaluate("mockllm/model", adapter, limit=2)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(result.predictions), 1)
            self.assertEqual(result.predictions[0]["status"], "adapter_error")
            self.assertIn("request", result.predictions[0])
            self.assertIn("synthetic failure", result.predictions[0]["error"])


if __name__ == "__main__":
    unittest.main()
