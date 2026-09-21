import json
import unittest

from retrybench.model import EvidenceContract, ObservedState, TASKS
from retrybench.openai_adapter import (
    BudgetExceeded,
    CostBudget,
    OpenAIResponsesPolicy,
    TokenUsage,
    calculate_cost,
)


def fake_response(api_key, payload):
    assert api_key == "test-key"
    assert payload["store"] is False
    return {
        "id": "resp_test",
        "model": "gpt-5.4-mini-2026-03-17",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps({"action": "unresolved", "rationale": "Evidence is weak."}),
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens": 20},
            "output_tokens": 30,
            "output_tokens_details": {"reasoning_tokens": 10},
        },
    }


class OpenAIAdapterTests(unittest.TestCase):
    def test_cost_uses_cached_rate(self):
        usage = TokenUsage(100, 20, 30, 10)
        expected = (80 * 0.75 + 20 * 0.075 + 30 * 4.5) / 1_000_000
        self.assertAlmostEqual(calculate_cost("gpt-5.4-mini-2026-03-17", usage), expected)

    def test_structured_decision_and_usage(self):
        policy = OpenAIResponsesPolicy(api_key="test-key", transport=fake_response)
        budget = CostBudget(0.01)
        decision = policy.decide(
            TASKS[0], EvidenceContract.WEAK, ObservedState.NOT_FOUND, False, budget
        )
        self.assertEqual(decision.action.value, "unresolved")
        self.assertEqual(decision.usage.reasoning_tokens, 10)
        self.assertEqual(budget.requests, 1)
        self.assertGreater(budget.spent_usd, 0)

    def test_budget_blocks_before_transport(self):
        called = []

        def transport(api_key, payload):
            called.append(True)
            return fake_response(api_key, payload)

        policy = OpenAIResponsesPolicy(api_key="test-key", transport=transport)
        with self.assertRaises(BudgetExceeded):
            policy.decide(
                TASKS[0],
                EvidenceContract.WEAK,
                ObservedState.NOT_FOUND,
                False,
                CostBudget(0.0000001),
            )
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()

