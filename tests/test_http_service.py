import json
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from retrybench.http_service import RetryBenchHTTPService
from retrybench.model import Schedule, TASKS


def request_json(url, method="GET", body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=2)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


def operation_body(operation_id, schedule):
    task = TASKS[0]
    return {
        "operation_id": operation_id,
        "schedule": schedule.value,
        "task": {
            "task_id": task.task_id,
            "tool": task.tool,
            "target": task.target,
            "payload": task.payload,
        },
    }


class HTTPServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "retrybench.sqlite3"

    def tearDown(self):
        self.temporary.cleanup()

    def test_all_hidden_schedules_return_same_timeout(self):
        with RetryBenchHTTPService(self.database_path) as service:
            responses = []
            for index, schedule in enumerate(Schedule):
                responses.append(
                    request_json(
                        service.base_url + "/operations",
                        "POST",
                        operation_body("op-%d" % index, schedule),
                    )
                )
        self.assertEqual(
            responses,
            [(504, {"error": "tool call timed out"})] * len(Schedule),
        )

    def test_in_flight_weak_negative_then_late_commit(self):
        with RetryBenchHTTPService(
            self.database_path, late_commit_delay=0.04
        ) as service:
            request_json(
                service.base_url + "/operations",
                "POST",
                operation_body("op-late", Schedule.IN_FLIGHT_LATE_COMMIT),
            )
            status, first = request_json(
                service.base_url + "/operations/op-late/status?evidence=weak"
            )
            self.assertEqual((status, first), (200, {"observed_state": "not_found"}))
            time.sleep(0.06)
            _, ledger = request_json(service.base_url + "/ledger")
            self.assertEqual(len(ledger["effects"]), 1)
            self.assertEqual(ledger["effects"][0]["operation_id"], "op-late")

    def test_stale_negative_hides_existing_commit_once(self):
        with RetryBenchHTTPService(self.database_path) as service:
            request_json(
                service.base_url + "/operations",
                "POST",
                operation_body("op-stale", Schedule.STALE_NEGATIVE_AFTER_COMMIT),
            )
            url = service.base_url + "/operations/op-stale/status?evidence=weak"
            self.assertEqual(request_json(url)[1]["observed_state"], "not_found")
            self.assertEqual(request_json(url)[1]["observed_state"], "committed")

    def test_authoritative_status_distinguishes_terminal_and_in_flight(self):
        with RetryBenchHTTPService(
            self.database_path, late_commit_delay=2.0
        ) as service:
            request_json(
                service.base_url + "/operations",
                "POST",
                operation_body("op-failed", Schedule.FAIL_BEFORE_EXECUTION),
            )
            request_json(
                service.base_url + "/operations",
                "POST",
                operation_body("op-flight", Schedule.IN_FLIGHT_LATE_COMMIT),
            )
            failed = request_json(
                service.base_url + "/operations/op-failed/status?evidence=authoritative"
            )[1]
            flight = request_json(
                service.base_url + "/operations/op-flight/status?evidence=authoritative"
            )[1]
            self.assertEqual(failed["observed_state"], "not_executed")
            self.assertEqual(flight["observed_state"], "in_flight")

    def test_stable_retry_deduplicates_pending_original(self):
        with RetryBenchHTTPService(
            self.database_path, late_commit_delay=0.04
        ) as service:
            request_json(
                service.base_url + "/operations",
                "POST",
                operation_body("op-dedupe", Schedule.IN_FLIGHT_LATE_COMMIT),
            )
            request_json(
                service.base_url + "/operations/op-dedupe/retry",
                "POST",
                {"stable_idempotency": True},
            )
            time.sleep(0.06)
            ledger = request_json(service.base_url + "/ledger")[1]
            self.assertEqual(len(ledger["effects"]), 1)

    def test_effect_ledger_survives_server_restart(self):
        with RetryBenchHTTPService(self.database_path) as service:
            request_json(
                service.base_url + "/operations",
                "POST",
                operation_body("op-persist", Schedule.COMMIT_THEN_DROP_RESPONSE),
            )
        with RetryBenchHTTPService(self.database_path) as restarted:
            ledger = request_json(restarted.base_url + "/ledger")[1]
            self.assertEqual(len(ledger["effects"]), 1)
            self.assertEqual(ledger["effects"][0]["target"], TASKS[0].target)
            self.assertEqual(ledger["effects"][0]["payload"], TASKS[0].payload)


if __name__ == "__main__":
    unittest.main()
