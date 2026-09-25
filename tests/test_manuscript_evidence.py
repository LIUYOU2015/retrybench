import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "paper" / "manuscript" / "evidence-ledger.json"
MANUSCRIPT = ROOT / "paper" / "manuscript" / "paper.md"


def resolve_pointer(value, pointer):
    current = value
    for token in pointer.strip("/").split("/") if pointer != "/" else []:
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


class ManuscriptEvidenceTests(unittest.TestCase):
    def test_every_ledger_assertion_matches_committed_artifact(self):
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        for claim in ledger["claims"]:
            source = json.loads((ROOT / claim["source"]).read_text(encoding="utf-8"))
            for assertion in claim["assertions"]:
                with self.subTest(claim=claim["id"], pointer=assertion["pointer"]):
                    self.assertEqual(
                        resolve_pointer(source, assertion["pointer"]),
                        assertion["expected"],
                    )

    def test_every_claim_id_is_used_in_manuscript(self):
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        manuscript = MANUSCRIPT.read_text(encoding="utf-8")
        for claim in ledger["claims"]:
            with self.subTest(claim=claim["id"]):
                self.assertIn("[%s]" % claim["id"], manuscript)

    def test_complete_markdown_manuscript_has_required_sections_and_sources(self):
        manuscript = MANUSCRIPT.read_text(encoding="utf-8")
        for heading in (
            "## Abstract",
            "## 1. Introduction",
            "## 2. Background and Related Work",
            "## 3. Method",
            "## 4. Results",
            "## 5. Discussion",
            "## 6. Threats to validity",
            "## 7. Artifact and Data Availability",
            "## 8. Conclusion",
            "## References",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, manuscript)
        for source_url in (
            "https://github.com/shushuyang231/ambiguous-tool-outcomes-benchmark",
            "https://arxiv.org/abs/2608.02645",
            "https://github.com/memovai/openonce",
            "https://github.com/gssanjana4/idempotencybench",
            "https://docs.aws.amazon.com/ec2/latest/devguide/eventual-consistency.html",
            "https://docs.stripe.com/api/idempotent_requests",
        ):
            with self.subTest(source_url=source_url):
                self.assertIn(source_url, manuscript)
        self.assertNotIn("TODO", manuscript)
        self.assertNotIn("methods-results.md", manuscript)
        self.assertNotIn(".tex", manuscript)


if __name__ == "__main__":
    unittest.main()
