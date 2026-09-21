"""SQLite-backed local HTTP service for observable recovery experiments."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from .model import EvidenceContract, ObservedState, Schedule


TIMEOUT_BODY = {"error": "tool call timed out"}


class HTTPServiceStore:
    """Durable operation and effect ledger shared by HTTP request threads."""

    def __init__(self, database_path: Path, late_commit_delay: float) -> None:
        self.database_path = Path(database_path)
        self.late_commit_delay = late_commit_delay
        self._write_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS operations (
                    operation_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    state TEXT NOT NULL,
                    due_at REAL,
                    weak_probes INTEGER NOT NULL DEFAULT 0,
                    dedupe_enabled INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS effects (
                    effect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    committed_at REAL NOT NULL
                );
                """
            )

    @staticmethod
    def _payload_json(payload: object) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _insert_effect(
        self, connection: sqlite3.Connection, operation: sqlite3.Row, deduplicate: bool
    ) -> bool:
        if deduplicate:
            existing = connection.execute(
                "SELECT 1 FROM effects WHERE operation_id = ? LIMIT 1",
                (operation["operation_id"],),
            ).fetchone()
            if existing:
                return False
        connection.execute(
            """
            INSERT INTO effects (
                operation_id, task_id, tool, target, payload_json, committed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                operation["operation_id"],
                operation["task_id"],
                operation["tool"],
                operation["target"],
                operation["payload_json"],
                time.time(),
            ),
        )
        return True

    def start_operation(self, body: Dict[str, object]) -> None:
        operation_id = str(body["operation_id"])
        task = body["task"]
        if not isinstance(task, dict):
            raise ValueError("task must be an object")
        schedule = Schedule(str(body["schedule"]))
        state = "not_executed"
        due_at = None
        if schedule in {
            Schedule.COMMIT_THEN_DROP_RESPONSE,
            Schedule.STALE_NEGATIVE_AFTER_COMMIT,
        }:
            state = "committed"
        elif schedule == Schedule.IN_FLIGHT_LATE_COMMIT:
            state = "in_flight"
            due_at = time.time() + self.late_commit_delay

        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO operations (
                    operation_id, task_id, tool, target, payload_json,
                    schedule, state, due_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    str(task["task_id"]),
                    str(task["tool"]),
                    str(task["target"]),
                    self._payload_json(task["payload"]),
                    schedule.value,
                    state,
                    due_at,
                ),
            )
            if state == "committed":
                operation = connection.execute(
                    "SELECT * FROM operations WHERE operation_id = ?", (operation_id,)
                ).fetchone()
                self._insert_effect(connection, operation, deduplicate=False)

    def _settle_due(self, connection: sqlite3.Connection, operation_id: str) -> None:
        operation = connection.execute(
            "SELECT * FROM operations WHERE operation_id = ?", (operation_id,)
        ).fetchone()
        if not operation:
            raise KeyError(operation_id)
        if (
            operation["state"] == "in_flight"
            and operation["due_at"] is not None
            and operation["due_at"] <= time.time()
        ):
            self._insert_effect(
                connection, operation, deduplicate=bool(operation["dedupe_enabled"])
            )
            connection.execute(
                "UPDATE operations SET state = 'committed', due_at = NULL "
                "WHERE operation_id = ?",
                (operation_id,),
            )

    def status(self, operation_id: str, evidence: EvidenceContract) -> ObservedState:
        with self._write_lock, self._connect() as connection:
            self._settle_due(connection, operation_id)
            operation = connection.execute(
                "SELECT * FROM operations WHERE operation_id = ?", (operation_id,)
            ).fetchone()
            if evidence == EvidenceContract.NONE:
                return ObservedState.UNKNOWN

            if evidence == EvidenceContract.WEAK:
                observed = ObservedState.NOT_FOUND
                if operation["state"] == "committed":
                    stale_first_probe = (
                        operation["schedule"] == Schedule.STALE_NEGATIVE_AFTER_COMMIT.value
                        and operation["weak_probes"] == 0
                    )
                    if not stale_first_probe:
                        observed = ObservedState.COMMITTED
                connection.execute(
                    "UPDATE operations SET weak_probes = weak_probes + 1 "
                    "WHERE operation_id = ?",
                    (operation_id,),
                )
                return observed

            if operation["state"] == "not_executed":
                return ObservedState.NOT_EXECUTED
            if operation["state"] == "in_flight":
                return ObservedState.IN_FLIGHT
            return ObservedState.COMMITTED

    def retry(self, operation_id: str, stable_idempotency: bool) -> bool:
        with self._write_lock, self._connect() as connection:
            self._settle_due(connection, operation_id)
            operation = connection.execute(
                "SELECT * FROM operations WHERE operation_id = ?", (operation_id,)
            ).fetchone()
            if stable_idempotency:
                connection.execute(
                    "UPDATE operations SET dedupe_enabled = 1 WHERE operation_id = ?",
                    (operation_id,),
                )
            return self._insert_effect(connection, operation, stable_idempotency)

    def effects(self) -> list:
        with self._write_lock, self._connect() as connection:
            due = connection.execute(
                "SELECT operation_id FROM operations WHERE state = 'in_flight' "
                "AND due_at <= ?",
                (time.time(),),
            ).fetchall()
            for operation in due:
                self._settle_due(connection, operation["operation_id"])
            rows = connection.execute(
                "SELECT * FROM effects ORDER BY effect_id"
            ).fetchall()
        return [
            {
                "effect_id": row["effect_id"],
                "operation_id": row["operation_id"],
                "task_id": row["task_id"],
                "tool": row["tool"],
                "target": row["target"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]


class RetryBenchHTTPService:
    """Lifecycle wrapper for the local fault-injecting HTTP service."""

    def __init__(
        self,
        database_path: Path,
        host: str = "127.0.0.1",
        port: int = 0,
        late_commit_delay: float = 0.05,
    ) -> None:
        self.store = HTTPServiceStore(Path(database_path), late_commit_delay)
        self._server = ThreadingHTTPServer((host, port), self._handler_type())
        self._thread: Optional[threading.Thread] = None

    def _handler_type(self):
        store = self.store

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                return

            def _read_json(self) -> Dict[str, object]:
                length = int(self.headers.get("Content-Length", "0"))
                value = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("request body must be an object")
                return value

            def _write(self, status: int, body: Dict[str, object]) -> None:
                encoded = json.dumps(
                    body, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_POST(self):  # noqa: N802
                parsed = urlparse(self.path)
                try:
                    if parsed.path == "/operations":
                        store.start_operation(self._read_json())
                        self._write(HTTPStatus.GATEWAY_TIMEOUT, TIMEOUT_BODY)
                        return
                    operation_id, action = _operation_route(parsed.path)
                    if action == "retry":
                        body = self._read_json()
                        created = store.retry(
                            operation_id, bool(body.get("stable_idempotency", False))
                        )
                        self._write(
                            HTTPStatus.CREATED if created else HTTPStatus.OK,
                            {"effect_created": created},
                        )
                        return
                    self._write(HTTPStatus.NOT_FOUND, {"error": "not found"})
                except KeyError:
                    self._write(HTTPStatus.NOT_FOUND, {"error": "unknown operation"})
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    self._write(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                except sqlite3.IntegrityError:
                    self._write(HTTPStatus.CONFLICT, {"error": "operation already exists"})

            def do_GET(self):  # noqa: N802
                parsed = urlparse(self.path)
                try:
                    if parsed.path == "/health":
                        self._write(HTTPStatus.OK, {"status": "ok"})
                        return
                    if parsed.path == "/ledger":
                        self._write(HTTPStatus.OK, {"effects": store.effects()})
                        return
                    operation_id, action = _operation_route(parsed.path)
                    if action == "status":
                        query = parse_qs(parsed.query)
                        evidence = EvidenceContract(query.get("evidence", ["none"])[0])
                        observed = store.status(operation_id, evidence)
                        self._write(HTTPStatus.OK, {"observed_state": observed.value})
                        return
                    self._write(HTTPStatus.NOT_FOUND, {"error": "not found"})
                except KeyError:
                    self._write(HTTPStatus.NOT_FOUND, {"error": "unknown operation"})
                except ValueError as exc:
                    self._write(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        return Handler

    @property
    def address(self) -> Tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    @property
    def base_url(self) -> str:
        host, port = self.address
        return "http://%s:%d" % (host, port)

    def start(self) -> "RetryBenchHTTPService":
        if self._thread is None:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
        return self

    def serve_forever(self) -> None:
        """Serve synchronously until interrupted by the caller."""
        try:
            self._server.serve_forever()
        finally:
            self._server.server_close()

    def close(self) -> None:
        if self._thread is not None:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=5.0)
            self._thread = None

    def __enter__(self) -> "RetryBenchHTTPService":
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def _operation_route(path: str) -> Tuple[str, str]:
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "operations":
        return "", ""
    return unquote(parts[1]), parts[2]
