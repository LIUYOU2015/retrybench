import unittest

from retrybench.model import EvidenceContract, EffectRecord, ObservedState, Schedule, TASKS
from retrybench.scoring import retry_is_permitted, score_exact_state


def intended_effect():
    task = TASKS[0]
    return EffectRecord(
        operation_id="op:issue-001",
        task_id=task.task_id,
        tool=task.tool,
        target=task.target,
        payload=dict(task.payload),
    )


class ExactStateScoringTests(unittest.TestCase):
    def test_retry_permission_requires_all_three_contract_conditions(self):
        for schedule in Schedule:
            for evidence in EvidenceContract:
                for observed in ObservedState:
                    expected = (
                        schedule == Schedule.FAIL_BEFORE_EXECUTION
                        and evidence == EvidenceContract.AUTHORITATIVE
                        and observed == ObservedState.NOT_EXECUTED
                    )
                    with self.subTest(
                        schedule=schedule, evidence=evidence, observed=observed
                    ):
                        self.assertEqual(
                            retry_is_permitted(schedule, evidence, observed),
                            expected,
                        )

    def test_complete_intended_effect_succeeds(self):
        score = score_exact_state(
            TASKS[0], "op:issue-001", [intended_effect()], unresolved=False
        )
        self.assertTrue(score.exact_state_success)

    def test_wrong_operation_identity_fails(self):
        effect = intended_effect()
        wrong = EffectRecord(
            operation_id="op:other",
            task_id=effect.task_id,
            tool=effect.tool,
            target=effect.target,
            payload=effect.payload,
        )
        score = score_exact_state(TASKS[0], "op:issue-001", [wrong], False)
        self.assertTrue(score.wrong_operation_identity)
        self.assertFalse(score.exact_state_success)

    def test_wrong_target_fails_even_when_count_is_one(self):
        effect = intended_effect()
        wrong = EffectRecord(
            operation_id=effect.operation_id,
            task_id=effect.task_id,
            tool=effect.tool,
            target="repo/wrong",
            payload=effect.payload,
        )
        score = score_exact_state(TASKS[0], effect.operation_id, [wrong], False)
        self.assertTrue(score.wrong_target)
        self.assertFalse(score.exact_state_success)

    def test_wrong_payload_fails_even_when_count_is_one(self):
        effect = intended_effect()
        wrong = EffectRecord(
            operation_id=effect.operation_id,
            task_id=effect.task_id,
            tool=effect.tool,
            target=effect.target,
            payload={"title": "Different issue"},
        )
        score = score_exact_state(TASKS[0], effect.operation_id, [wrong], False)
        self.assertTrue(score.wrong_payload)
        self.assertFalse(score.exact_state_success)

    def test_duplicate_fails_even_when_both_effects_match(self):
        effect = intended_effect()
        score = score_exact_state(TASKS[0], effect.operation_id, [effect, effect], False)
        self.assertTrue(score.duplicate_effect)
        self.assertFalse(score.exact_state_success)

    def test_unresolved_fails_with_otherwise_correct_state(self):
        effect = intended_effect()
        score = score_exact_state(TASKS[0], effect.operation_id, [effect], True)
        self.assertTrue(score.unresolved)
        self.assertFalse(score.exact_state_success)


if __name__ == "__main__":
    unittest.main()
