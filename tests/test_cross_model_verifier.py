import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("cross_model_verifier", Path(__file__).resolve().parents[1] / "scripts/verify_cross_model_pilot.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class VerifierTests(unittest.TestCase):
    def test_resolves_nested_raw_arguments_without_mutating_records(self):
        saved = {"output": [{"arguments": "attachment://abc"}]}
        attachments = {"abc": '{"action":"retry_with_key","idempotency_key":"key-A"}'}
        expanded = verifier.resolve_attachments(saved, attachments)
        self.assertEqual(expanded["output"][0]["arguments"], attachments["abc"])
        self.assertEqual(saved["output"][0]["arguments"], "attachment://abc")

    def test_missing_and_cyclic_capture_fail_closed(self):
        for value, attachments in (("attachment://absent", {}), ("attachment://a", {"a": "attachment://a"})):
            with self.assertRaises(ValueError):
                verifier.resolve_attachments(value, attachments)

    def test_json_text_is_not_rewritten_internally(self):
        value = '{"key":"attachment://literal"}'
        self.assertEqual(verifier.resolve_attachments(value, {}), value)


if __name__ == "__main__":
    unittest.main()
