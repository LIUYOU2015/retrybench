import copy
import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

from retrybench import evaluate, public_cases, score_predictions
from retrybench.cli import main
from retrybench.evaluation import load_predictions, load_suite, SUITE_SHA256
from retrybench.serialization import canonical_json_sha256


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = load_suite()
        cls.public = public_cases()

    def predictions(self, action="unresolved"):
        return [{"case_id": c["case_id"], "action": action} for c in self.public]

    def key_case(self, present=True):
        return next(c for c in self.suite["cases"] if c["block"] == "supplied_key"
                    and (c["original_key"] is not None) == present)

    def test_frozen_suite_and_export_hide_gold(self):
        self.assertEqual(canonical_json_sha256(self.suite), SUITE_SHA256)
        self.assertEqual(len(self.public), 240)
        self.assertEqual(sum(len(c["schedules"]) for c in self.suite["cases"]), 480)
        self.assertEqual(len({c["case_id"] for c in self.public}), 240)
        for case in self.public:
            self.assertEqual(set(case), {"schema_version", "suite", "suite_sha256", "case_id",
                                        "instructions", "prompt", "transcript_sha256", "decision_schema"})
            self.assertEqual(case["transcript_sha256"], canonical_json_sha256({
                k: case[k] for k in ("instructions", "prompt")}))

    def test_defer_is_safe_but_makes_no_permitted_progress(self):
        result = score_predictions(self.predictions())
        m = result.report["metrics"]
        self.assertEqual(result.false_retry_permission_rate, 0)
        self.assertEqual(m["permitted_progress"]["planned_denominator"], 80)
        self.assertEqual(m["permitted_progress"]["count"], 0)
        self.assertEqual(m["outcomes"]["unresolved"]["count"], 480)
        self.assertEqual(m["outcomes"]["exact_state_success"]["count"], 0)
        self.assertTrue(result.report["complete"])

    def test_always_retry_known_counts(self):
        m = score_predictions(self.predictions("retry")).report["metrics"]
        self.assertEqual(m["false_retry_permission"]["count"], 200)
        self.assertEqual(m["false_retry_permission"]["planned_denominator"], 240)
        self.assertEqual(m["outcomes"]["false_retry_permission"]["count"], 440)
        self.assertEqual(m["permitted_progress"]["count"], 40)
        self.assertEqual(m["outcomes"]["duplicate_effect"]["count"], 320)

    def test_keys_require_exact_original_match_and_preserve_pending_original(self):
        for present in (True, False):
            case = self.key_case(present)
            for key in ("key-A", "key-B", "key-A ", "invented"):
                with self.subTest(present=present, key=key):
                    result = score_predictions([{"case_id": case["case_id"], "action": "RETRY",
                                                 "arguments": {"idempotency_key": key}}])
                    score = next(c for c in result.cases if c["case_id"] == case["case_id"])
                    protected = present and key == "key-A"
                    self.assertEqual(score["false_retry_permission"], not protected)
                    self.assertEqual(sum(w["duplicate_effect"] for w in score["outcomes"]), 0 if protected else 2)
                    self.assertEqual(sum(w["permitted_progress"] for w in score["outcomes"]), 3 if protected else 0)

    def test_missing_and_invalid_are_unknown_not_safe_deferrals(self):
        p = self.predictions()[:2]
        p[0]["action"] = "bad"
        result = score_predictions(p)
        m = result.report["metrics"]
        self.assertEqual(m["status_counts"], {"invalid": 1, "valid": 1, "missing": 238})
        self.assertEqual(m["false_retry_permission"]["planned_rate_bounds"], [0, 239 / 240])
        self.assertEqual(m["protocol_validity"]["rate_among_known"], 1 / 240)
        self.assertFalse(result.report["complete"])
        invalid = result.cases[0]
        self.assertIsNone(invalid["false_retry_permission"])
        self.assertTrue(all(w["exact_state_success"] is None for w in invalid["outcomes"]))

    def test_empty_has_no_point_rate(self):
        result = score_predictions([])
        self.assertIsNone(result.false_retry_permission_rate)
        self.assertEqual(result.report["metrics"]["false_retry_permission"]["planned_rate_bounds"], [0, 1])

    def test_invalid_arguments_and_metadata_do_not_slip_through(self):
        evidence = self.public[0]
        cases = [
            {"action": []}, {"action": "retry", "arguments": []},
            {"action": "retry", "arguments": {"payload": "mutated"}},
            {"action": "retry", "arguments": {"idempotency_key": "key-A"}},
            {"action": "retry_with_key", "idempotency_key": "key-A"},
            {"action": "stop", "status": "error"},
            {"action": "stop", "suite_sha256": "bad"},
            {"action": "stop", "schema_version": "bad"},
            {"action": "stop", "transcript_sha256": "bad"},
            {"action": "stop", "arguments": {"idempotency_key": None}, "idempotency_key": None},
        ]
        for p in cases:
            with self.subTest(p=p):
                result = score_predictions([dict(p, case_id=evidence["case_id"])])
                self.assertEqual(result.cases[0]["status"], "invalid")

    def test_key_output_schema(self):
        case = self.key_case()
        for key in (None, "", 12, [], True):
            p = {"case_id": case["case_id"], "action": "retry_with_key", "idempotency_key": key}
            result = score_predictions([p])
            score = next(c for c in result.cases if c["case_id"] == case["case_id"])
            self.assertEqual(score["status"], "invalid")

    def test_non_retry_alias_does_not_claim_completion(self):
        for action in ("NOT_RETRY", "VERIFY_FIRST"):
            m = score_predictions(self.predictions(action)).report["metrics"]
            self.assertEqual(m["outcomes"]["unresolved"]["count"], 480)
            self.assertEqual(m["outcomes"]["exact_state_success"]["count"], 0)

    def test_duplicate_unknown_ids_and_nonobject_rejected(self):
        for p in ([self.predictions()[0]] * 2, [{"case_id": "unknown"}], [None], [{"case_id": 1}]):
            with self.assertRaises(ValueError):
                score_predictions(p)

    def test_usage_unknown_not_zero_and_usage_is_per_response(self):
        p = self.predictions()
        p[-1]["usage"] = {"input_tokens": 10, "output_tokens": 2, "cost_usd": 0.1}
        p[-2]["usage"] = {"input_tokens": -1, "cost_usd": -1}
        r = score_predictions(p).report["usage"]
        self.assertEqual(r["input_tokens"]["reported_total"], 10)
        self.assertEqual(r["cost_usd"]["reported_records"], 1)
        self.assertIsNone(score_predictions([]).report["usage"]["cost_usd"]["reported_total"])

    def test_adapter_receives_only_visible_cases_and_retains_raw_output(self):
        seen = []
        def adapter(case):
            seen.append(copy.deepcopy(case))
            case["prompt"] = "adapter mutation"
            return {"action": "unresolved", "raw_response": {"fixture": "synthetic"}}
        result = evaluate("test-fixture", adapter)
        self.assertEqual(seen, self.public)
        self.assertEqual(len(result.predictions), 240)
        self.assertTrue(all(p["raw_response"]["fixture"] == "synthetic" for p in result.predictions))
        self.assertEqual(public_cases(), self.public)

    def test_adapter_exception_halts_and_journals_without_retry(self):
        calls = []
        def adapter(case):
            calls.append(case)
            raise RuntimeError("synthetic transport error")
        with tempfile.TemporaryDirectory() as d:
            result = evaluate("fixture", adapter, output_dir=Path(d))
            self.assertEqual(len(calls), 1)
            self.assertEqual(result.report["metrics"]["status_counts"], {"invalid": 1, "missing": 239})
            self.assertEqual(len(load_predictions(Path(d) / "predictions.jsonl")), 1)
            self.assertFalse((Path(d) / "pending.json").exists())
            with self.assertRaises(ValueError):
                evaluate("fixture", adapter, output_dir=Path(d))
            self.assertEqual(len(calls), 1)

    def test_limit_preserves_full_denominator(self):
        result = evaluate("fixture", lambda c: {"action": "stop"}, limit=2)
        self.assertEqual(result.report["metrics"]["planned_cases"], 240)
        self.assertEqual(result.report["metrics"]["status_counts"]["missing"], 238)

    def test_strict_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "p.jsonl"
            for text in ('[]', '{"case_id":"a","case_id":"b"}', '{"n":NaN}', '{bad}'):
                p.write_text(text)
                with self.assertRaises(ValueError):
                    load_predictions(p)

    def test_cli_export_score_and_dry_run_without_provider(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            p = Path(d)
            self.assertEqual(main(["export", "--output", str(p / "cases.jsonl")]), 0)
            self.assertEqual(len(load_predictions(p / "cases.jsonl")), 240)
            (p / "predictions.jsonl").write_text("\n".join(json.dumps(x) for x in self.predictions()))
            self.assertEqual(main(["score", "--predictions", str(p / "predictions.jsonl"), "--output-dir", str(p / "score")]), 0)
            self.assertTrue(json.loads((p / "score/report.json").read_text())["complete"])
            (p / "empty.jsonl").write_text("")
            self.assertEqual(main(["score", "--predictions", str(p / "empty.jsonl"), "--output-dir", str(p / "partial")]), 2)
            self.assertEqual(main(["eval", "--model", "unused/provider", "--dry-run"]), 0)

    def test_evidence_replay_matches_legacy_scorer_for_every_action(self):
        from retrybench.confirmation import load_confirmation_manifest
        from retrybench.external import score_external_decisions
        from retrybench.model import Action
        root = Path(__file__).resolve().parents[1]
        rows = load_confirmation_manifest(root / "protocol/confirmation-v2-manifest.jsonl")
        for action in Action:
            legacy = score_external_decisions(rows, {r.response_group_id: action for r in rows})
            new = score_predictions(self.predictions(action.value))
            worlds = {(r["case_id"], w["schedule"]): w for r in new.cases if r["block"] == "evidence" for w in r["outcomes"]}
            for old in legacy:
                world = worlds[(old["case_id"], old["schedule"])]
                for metric in ("false_retry_permission", "exact_state_success", "duplicate_effect", "omission", "unresolved", "effect_count"):
                    self.assertEqual(world[metric], old[metric])

    def test_key_prompts_are_model_independent_copies_of_frozen_source(self):
        root = Path(__file__).resolve().parents[1]
        with zipfile.ZipFile(root / "artifacts/reproduction-v1.zip") as archive:
            source = [json.loads(line) for line in archive.read("protocol/candidate-presence-v1/manifest.jsonl").decode().splitlines() if line.strip()]
        public_keys = [c for c in self.suite["cases"] if c["block"] == "supplied_key"]
        self.assertEqual(len(public_keys), 80)
        for c in public_keys:
            archived = next(r for r in source if "key:" + r["case_id"] == c["case_id"])
            for key in ("prompt", "instructions", "transcript_sha256", "original_key", "schedules", "allowed_actions"):
                self.assertEqual(c[key], archived[key])
            peers = [r for r in source if all(r[k] == archived[k] for k in (
                "task_id", "repetition", "candidate", "original_key_state"))]
            self.assertEqual(len(peers), 3)
            self.assertTrue(all(r["prompt"] == c["prompt"] for r in peers))

    def test_nonfinite_python_predictions_are_rejected(self):
        with self.assertRaises(ValueError):
            score_predictions([dict(self.predictions()[0], usage={"cost_usd": float("nan")})])


if __name__ == "__main__":
    unittest.main()
