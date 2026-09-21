# Local HTTP fault service

The RetryBench HTTP service moves the four hidden schedules across an actual
network boundary and persists operation state and effects in SQLite. It is a
controlled experiment service, not evidence about production incident rates.

Start it with:

```bash
retrybench serve \
  --database results/retrybench.sqlite3 \
  --host 127.0.0.1 \
  --port 8765 \
  --late-commit-delay 1.0
```

## Start an operation

The experiment harness supplies the hidden schedule. The recovery agent receives
only the HTTP response.

```bash
curl -i -X POST http://127.0.0.1:8765/operations \
  -H 'content-type: application/json' \
  -d '{
    "operation_id": "op:issue-001",
    "schedule": "in_flight_late_commit",
    "task": {
      "task_id": "issue-001",
      "tool": "create_issue",
      "target": "repo/acme",
      "payload": {"title": "Fix race"}
    }
  }'
```

Every hidden schedule returns the same status and body at this decision point:

```text
HTTP/1.0 504 Gateway Timeout
{"error":"tool call timed out"}
```

## Query declared evidence

```bash
curl 'http://127.0.0.1:8765/operations/op%3Aissue-001/status?evidence=weak'
curl 'http://127.0.0.1:8765/operations/op%3Aissue-001/status?evidence=authoritative'
```

A weak query may return `not_found` while the original request is still in
flight, or for the first read after a committed but temporarily invisible
effect. An authoritative query distinguishes `not_executed`, `in_flight`, and
`committed` in the controlled service.

## Retry and inspect ground truth

```bash
curl -X POST \
  http://127.0.0.1:8765/operations/op%3Aissue-001/retry \
  -H 'content-type: application/json' \
  -d '{"stable_idempotency":false}'

curl http://127.0.0.1:8765/ledger
```

The ledger records operation identity, task, tool, target, and payload for exact
scoring. Setting `stable_idempotency` to true makes the service suppress a later
effect with the same logical operation identity, including a pending original
that commits after the retry.

## Frozen semantic checks

The test suite verifies:

- byte-equivalent JSON timeout bodies across all four hidden schedules;
- weak negative evidence followed by an in-flight late commit;
- a stale negative read after a committed effect;
- authoritative terminal versus in-flight evidence;
- stable-key suppression across a retry/late-commit race; and
- SQLite ledger survival across a server restart.
