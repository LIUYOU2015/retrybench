import unittest

from retrybench.analysis import exact_mcnemar_p, sanitize_row


class PilotAnalysisTests(unittest.TestCase):
    def test_exact_mcnemar_extreme_discordance(self):
        self.assertAlmostEqual(exact_mcnemar_p(9, 0), 2 / (2**9))
        self.assertEqual(exact_mcnemar_p(0, 0), 1.0)

    def test_sanitizer_removes_provider_response_id(self):
        row = {
            "cell_id": "pilot-001",
            "decision": {
                "action": "wait",
                "rationale": "Insufficient evidence.",
                "response_id": "sensitive-provider-id",
            },
        }
        sanitized = sanitize_row(row)
        self.assertNotIn("response_id", sanitized["decision"])
        self.assertEqual(sanitized["decision"]["action"], "wait")


if __name__ == "__main__":
    unittest.main()
