"""Core Python backend for the IssueDesk bug and feature report system.

The server intentionally uses only Python's standard library so the project can
run without installing a web framework. It serves ``index.html`` and exposes a
small JSON API backed by SQLite.
"""

from __future__ import annotations

import json
import mimetypes
import sqlite3
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parent
DATABASE_DIR = ROOT_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "issuedesk.sqlite"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"
EXCLUDED_ARCHIVE_PARTS = {".git", "__pycache__"}


REQUIRED_REPORT_FIELDS = {
    "report_type",
    "priority",
    "title",
    "reporter_name",
    "reporter_email",
    "product_area",
    "description",
}


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for SQLite text storage."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dict_from_row(row: sqlite3.Row) -> dict[str, object]:
    """Convert a SQLite row into a plain dictionary for JSON responses."""
    return {key: row[key] for key in row.keys()}


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection configured for IssueDesk."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    """Create or update the local SQLite database from the checked-in schema."""
    with get_connection() as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def iter_project_files() -> list[Path]:
    """Return project files that should be included in the download archive."""
    files = []
    for file_path in ROOT_DIR.rglob("*"):
        relative_path = file_path.relative_to(ROOT_DIR)
        if not file_path.is_file():
            continue
        if any(part in EXCLUDED_ARCHIVE_PARTS for part in relative_path.parts):
            continue
        files.append(file_path)
    return sorted(files)


def build_project_archive() -> bytes:
    """Create a ZIP archive containing every IssueDesk project file."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in iter_project_files():
            archive.write(file_path, file_path.relative_to(ROOT_DIR))
    return buffer.getvalue()


def validate_report(payload: dict[str, object]) -> list[str]:
    """Return missing required report fields from a JSON payload."""
    missing = []
    for field in sorted(REQUIRED_REPORT_FIELDS):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    return missing


def insert_report(payload: dict[str, object]) -> dict[str, object]:
    """Persist a report and return the stored row with lookup display names."""
    now = utc_now()
    with get_connection() as connection:
        report_type_id = lookup_id(connection, "report_types", "type_name", payload["report_type"])
        priority_id = lookup_id(connection, "priorities", "priority_name", payload["priority"])
        status_id = lookup_id(connection, "statuses", "status_name", payload.get("status") or "New")

        cursor = connection.execute(
            """
            INSERT INTO reports (
                report_type_id, priority_id, status_id, title, reporter_name,
                reporter_email, product_area, version_build, environment_name,
                severity, requested_resolution_date, description,
                steps_to_reproduce, acceptance_criteria, actual_result,
                business_impact, assignee, labels, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_type_id,
                priority_id,
                status_id,
                clean(payload.get("title")),
                clean(payload.get("reporter_name")),
                clean(payload.get("reporter_email")),
                clean(payload.get("product_area")),
                clean(payload.get("version_build")),
                clean(payload.get("environment_name")),
                clean(payload.get("severity")),
                clean(payload.get("requested_resolution_date")) or None,
                clean(payload.get("description")),
                clean(payload.get("steps_to_reproduce")),
                clean(payload.get("acceptance_criteria")),
                clean(payload.get("actual_result")),
                clean(payload.get("business_impact")),
                clean(payload.get("assignee")),
                clean(payload.get("labels")),
                now,
                now,
            ),
        )
        report_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO report_status_history (
                report_id, old_status_id, new_status_id, changed_by, change_note, changed_at
            ) VALUES (?, NULL, ?, ?, ?, ?)
            """,
            (
                report_id,
                status_id,
                clean(payload.get("reporter_name")),
                "Report created from the web intake form.",
                now,
            ),
        )
        return fetch_report(connection, report_id)


def lookup_id(connection: sqlite3.Connection, table: str, column: str, value: object) -> int:
    """Find a lookup-table row id by its human-readable value."""
    row = connection.execute(
        f"SELECT id FROM {table} WHERE {column} = ?",
        (clean(value),),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown {column}: {value}")
    return int(row["id"])


def clean(value: object) -> str:
    """Normalize optional JSON values before SQLite insertion."""
    if value is None:
        return ""
    return str(value).strip()


def fetch_report(connection: sqlite3.Connection, report_id: int) -> dict[str, object]:
    """Load one report with lookup names."""
    row = connection.execute(
        """
        SELECT
            reports.id,
            report_types.type_name AS report_type,
            priorities.priority_name AS priority,
            statuses.status_name AS status,
            reports.title,
            reports.reporter_name,
            reports.reporter_email,
            reports.product_area,
            reports.version_build,
            reports.environment_name,
            reports.severity,
            reports.requested_resolution_date,
            reports.description,
            reports.steps_to_reproduce,
            reports.acceptance_criteria,
            reports.actual_result,
            reports.business_impact,
            reports.assignee,
            reports.labels,
            reports.created_at,
            reports.updated_at
        FROM reports
        JOIN report_types ON report_types.id = reports.report_type_id
        JOIN priorities ON priorities.id = reports.priority_id
        JOIN statuses ON statuses.id = reports.status_id
        WHERE reports.id = ?
        """,
        (report_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"Report {report_id} was not found")
    return dict_from_row(row)


def list_reports(report_type: str = "") -> list[dict[str, object]]:
    """Return the newest reports, optionally filtered by report type."""
    params: list[object] = []
    filter_clause = ""
    if report_type:
        filter_clause = "WHERE report_types.type_name = ?"
        params.append(report_type)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT
                reports.id,
                report_types.type_name AS report_type,
                priorities.priority_name AS priority,
                statuses.status_name AS status,
                reports.title,
                reports.product_area,
                reports.assignee,
                reports.created_at,
                reports.updated_at
            FROM reports
            JOIN report_types ON report_types.id = reports.report_type_id
            JOIN priorities ON priorities.id = reports.priority_id
            JOIN statuses ON statuses.id = reports.status_id
            {filter_clause}
            ORDER BY reports.created_at DESC
            LIMIT 100
            """,
            params,
        ).fetchall()
        return [dict_from_row(row) for row in rows]


def get_report_with_comments(report_id: int) -> dict[str, object]:
    """Return a report with its comment thread."""
    with get_connection() as connection:
        report = fetch_report(connection, report_id)
        rows = connection.execute(
            """
            SELECT *
            FROM report_comments
            WHERE report_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (report_id,),
        ).fetchall()
        report["comments"] = [dict_from_row(row) for row in rows]
        return report


def update_report(report_id: int, payload: dict[str, object]) -> dict[str, object]:
    """Update a report and return the refreshed row."""
    missing = validate_report(payload)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    now = utc_now()
    with get_connection() as connection:
        current = fetch_report(connection, report_id)
        old_status_id = lookup_id(connection, "statuses", "status_name", current["status"])
        report_type_id = lookup_id(connection, "report_types", "type_name", payload["report_type"])
        priority_id = lookup_id(connection, "priorities", "priority_name", payload["priority"])
        status_id = lookup_id(connection, "statuses", "status_name", payload.get("status") or "New")

        connection.execute(
            """
            UPDATE reports
            SET report_type_id = ?, priority_id = ?, status_id = ?, title = ?,
                reporter_name = ?, reporter_email = ?, product_area = ?,
                version_build = ?, environment_name = ?, severity = ?,
                requested_resolution_date = ?, description = ?,
                steps_to_reproduce = ?, acceptance_criteria = ?, actual_result = ?,
                business_impact = ?, assignee = ?, labels = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                report_type_id,
                priority_id,
                status_id,
                clean(payload.get("title")),
                clean(payload.get("reporter_name")),
                clean(payload.get("reporter_email")),
                clean(payload.get("product_area")),
                clean(payload.get("version_build")),
                clean(payload.get("environment_name")),
                clean(payload.get("severity")),
                clean(payload.get("requested_resolution_date")) or None,
                clean(payload.get("description")),
                clean(payload.get("steps_to_reproduce")),
                clean(payload.get("acceptance_criteria")),
                clean(payload.get("actual_result")),
                clean(payload.get("business_impact")),
                clean(payload.get("assignee")),
                clean(payload.get("labels")),
                now,
                report_id,
            ),
        )
        if old_status_id != status_id:
            connection.execute(
                """
                INSERT INTO report_status_history (
                    report_id, old_status_id, new_status_id, changed_by, change_note, changed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    old_status_id,
                    status_id,
                    clean(payload.get("reporter_name")) or "System",
                    "Status changed from the detail page.",
                    now,
                ),
            )
        return fetch_report(connection, report_id)


def delete_report(report_id: int) -> None:
    """Delete a report and cascading related records."""
    with get_connection() as connection:
        fetch_report(connection, report_id)
        connection.execute("DELETE FROM reports WHERE id = ?", (report_id,))


def report_id_from_path(path: str) -> int | None:
    """Extract a report id from /api/reports/{id} style paths."""
    parts = path.strip("/").split("/")
    if len(parts) == 3 and parts[:2] == ["api", "reports"] and parts[2].isdigit():
        return int(parts[2])
    return None


def insert_comment(payload: dict[str, object]) -> dict[str, object]:
    """Persist a comment for a report."""
    report_id = int(payload.get("report_id") or 0)
    author_name = clean(payload.get("author_name")) or "Anonymous"
    comment_body = clean(payload.get("comment_body"))
    if report_id <= 0 or not comment_body:
        raise ValueError("report_id and comment_body are required")

    now = utc_now()
    with get_connection() as connection:
        fetch_report(connection, report_id)
        cursor = connection.execute(
            """
            INSERT INTO report_comments (
                report_id, author_name, author_email, comment_body, created_at, is_internal
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                author_name,
                clean(payload.get("author_email")),
                comment_body,
                now,
                1 if payload.get("is_internal") else 0,
            ),
        )
        row = connection.execute(
            "SELECT * FROM report_comments WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict_from_row(row)


class IssueDeskHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the static UI and JSON API."""

    server_version = "IssueDeskCorePython/1.0"

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
        parsed = urlparse(self.path)
        if parsed.path == "/api/reports":
            query = parse_qs(parsed.query)
            report_type = clean(query.get("type", [""])[0])
            self.send_json({"reports": list_reports(report_type)})
            return
        report_id = report_id_from_path(parsed.path)
        if report_id is not None:
            try:
                self.send_json({"report": get_report_with_comments(report_id)})
            except LookupError as error:
                self.send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
            return
        if parsed.path == "/download/issuedesk-files.zip":
            self.send_download(
                build_project_archive(),
                "issuedesk-files.zip",
                "application/zip",
            )
            return
        if parsed.path == "/" or parsed.path == "/index.html":
            self.serve_file(ROOT_DIR / "index.html")
            return
        self.serve_file(ROOT_DIR / parsed.path.lstrip("/"))

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        parsed = urlparse(self.path)
        try:
            payload = self.read_json_body()
            if parsed.path == "/api/reports":
                missing = validate_report(payload)
                if missing:
                    self.send_json({"error": "Missing required fields", "fields": missing}, HTTPStatus.BAD_REQUEST)
                    return
                self.send_json({"report": insert_report(payload)}, HTTPStatus.CREATED)
                return
            if parsed.path == "/api/comments":
                self.send_json({"comment": insert_comment(payload)}, HTTPStatus.CREATED)
                return
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, LookupError, sqlite3.Error) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def do_PUT(self) -> None:  # noqa: N802 - stdlib hook name
        parsed = urlparse(self.path)
        report_id = report_id_from_path(parsed.path)
        if report_id is None:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json_body()
            self.send_json({"report": update_report(report_id, payload)})
        except LookupError as error:
            self.send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
        except (ValueError, sqlite3.Error) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib hook name
        parsed = urlparse(self.path)
        report_id = report_id_from_path(parsed.path)
        if report_id is None:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            delete_report(report_id)
            self.send_json({"deleted": True})
        except LookupError as error:
            self.send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
        except sqlite3.Error as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(raw_body)
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload

    def serve_file(self, path: Path) -> None:
        resolved = path.resolve()
        if ROOT_DIR not in resolved.parents and resolved != ROOT_DIR:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not resolved.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type, _ = mimetypes.guess_type(resolved.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(resolved.stat().st_size))
        self.end_headers()
        self.wfile.write(resolved.read_bytes())

    def send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_download(self, body: bytes, filename: str, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Keep default request logging, but make the type checker happy."""
        super().log_message(format, *args)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    initialize_database()
    server = ThreadingHTTPServer((host, port), IssueDeskHandler)
    print(f"IssueDesk running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
