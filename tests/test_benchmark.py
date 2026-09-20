import unittest

from retrybench.benchmark import run_episode, run_matrix
from retrybench.metrics import summarize
from retrybench.model import EvidenceContract, PolicyName, Schedule, TASKS


class BenchmarkTests(unittest.TestCase):
    def test_all_initial_observations_are_identical(self):
        observations = {
            run_episode(TASKS[0], schedule, EvidenceContract.NONE, PolicyName.ALWAYS_STOP).initial_observation
            for schedule in Schedule
        }
        self.assertEqual(observations, {"timeout"})

    def test_blind_retry_duplicates_after_lost_response(self):
        row = run_episode(
            TASKS[0],
            Schedule.COMMIT_THEN_DROP_RESPONSE,
            EvidenceContract.NONE,
            PolicyName.ALWAYS_RETRY,
        )
        self.assertTrue(row.duplicate_effect)
        self.assertEqual(row.effect_count, 2)

    def test_blind_stop_omits_pre_execution_failure(self):
        row = run_episode(
            TASKS[0],
            Schedule.FAIL_BEFORE_EXECUTION,
            EvidenceContract.NONE,
            PolicyName.ALWAYS_STOP,
        )
        self.assertTrue(row.omission)

    def test_single_weak_negative_is_unsafe_for_in_flight_call(self):
        row = run_episode(
            TASKS[0],
            Schedule.IN_FLIGHT_LATE_COMMIT,
            EvidenceContract.WEAK,
            PolicyName.SINGLE_STATUS,
        )
        self.assertEqual(row.policy_observations, ["not_found"])
        self.assertTrue(row.duplicate_effect)

    def test_backoff_observes_late_commit(self):
        row = run_episode(
            TASKS[0],
            Schedule.IN_FLIGHT_LATE_COMMIT,
            EvidenceContract.WEAK,
            PolicyName.TRI_STATE_BACKOFF,
        )
        self.assertEqual(row.policy_observations, ["not_found", "committed"])
        self.assertTrue(row.exact_state_success)

    def test_authoritative_non_execution_permits_retry(self):
        row = run_episode(
            TASKS[0],
            Schedule.FAIL_BEFORE_EXECUTION,
            EvidenceContract.AUTHORITATIVE,
            PolicyName.TRI_STATE_BACKOFF,
        )
        self.assertEqual(row.policy_observations, ["not_executed"])
        self.assertTrue(row.exact_state_success)

    def test_stable_idempotency_is_safe_across_schedules(self):
        for schedule in Schedule:
            with self.subTest(schedule=schedule):
                row = run_episode(
                    TASKS[0], schedule, EvidenceContract.NONE, PolicyName.STABLE_IDEMPOTENCY
                )
                self.assertTrue(row.exact_state_success)

    def test_default_matrix_and_denominators(self):
        rows = list(run_matrix())
        expected = len(TASKS) * len(Schedule) * len(EvidenceContract) * len(PolicyName)
        self.assertEqual(len(rows), expected)
        report = summarize(rows)
        self.assertEqual(report["overall"]["episodes"], expected)


if __name__ == "__main__":
    unittest.main()

