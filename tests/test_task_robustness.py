import unittest

from retrybench.task_robustness import (
    analyze_task_robustness,
    build_robustness_manifest,
    run_robustness_preflight,
)


class TaskRobustnessTests(unittest.TestCase):
    def test_zero_cost_protocol_freeze(self):
        rows = build_robustness_manifest()
        report = run_robustness_preflight(rows)
        self.assertEqual(len(rows), 192)
        self.assertEqual(len({row.response_group_id for row in rows}), 128)
        self.assertTrue(report["all_zero_cost_gates_passed"])

    def test_predeclared_analysis_strong_fixture(self):
        rows = []
        for cell in build_robustness_manifest():
            false_retry = cell.evidence == "weak"
            rows.append({
                **cell.to_dict(),
                "false_retry_permission": false_retry,
            })
        report = analyze_task_robustness(rows)
        self.assertEqual(report["decision"], "STRONGER_EMPIRICAL_PAPER_PATH")
        self.assertEqual(report["weak_higher_families"], 8)
        self.assertEqual(report["equal_family_mean_rate_difference"], 1.0)
        self.assertEqual(report["task_cluster_t_95_interval_bounded"], [1.0, 1.0])
        self.assertEqual(
            report["lexical_counterbalance"][
                "equal_family_mean_create_minus_noncreate"
            ],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
