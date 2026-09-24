import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "paper" / "manuscript" / "evidence-ledger.json"
MANUSCRIPT = ROOT / "paper" / "manuscript" / "methods-results.md"


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


if __name__ == "__main__":
    unittest.main()
