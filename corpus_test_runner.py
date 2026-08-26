#!/usr/bin/env python3
"""
SuperDocs Public Golden Corpus API Test Runner.

Runs deterministic corpus suites against the running SuperDocs API.

Examples:
    python corpus_test_runner.py --suite smoke
    python corpus_test_runner.py --suite multilingual
    python corpus_test_runner.py --suite structural
    python corpus_test_runner.py --suite full
    python corpus_test_runner.py --suite unsupported

Default API:
    http://127.0.0.1:8000

Override:
    python corpus_test_runner.py --suite smoke --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request


REPO_ROOT = Path(__file__).resolve().parent

CORPUS_ROOT = (
    REPO_ROOT
    / "data"
    / "documents"
    / "public-golden-corpus"
)

TEST_SET_ROOT = CORPUS_ROOT / "test_sets"

RESULT_ROOT = (
    REPO_ROOT
    / "data"
    / "corpus-evaluations"
)

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

SUPPORTED_FORMATS = {
    "pdf",
    "docx",
    "txt",
}

# Based on the workflow contract used by the application.
# "awaiting_review" is intentionally treated as a successful
# analysis endpoint because the human review gate has not yet
# been completed.
SUCCESS_STATUSES = {
    "awaiting_review",
    "complete",
    "completed",
}

FAILURE_STATUSES = {
    "failed",
    "error",
    "cancelled",
}

ACTIVE_STATUSES = {
    "pending",
    "queued",
    "running",
    "in_progress",
}


class APIError(RuntimeError):
    """Raised when the SuperDocs API returns an unexpected response."""


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def load_suite(suite_name: str) -> dict:
    """Load a deterministic test-suite manifest."""
    manifest_path = TEST_SET_ROOT / f"{suite_name}.json"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Test suite not found: {manifest_path}"
        )

    with manifest_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def resolve_document(filename: str) -> Path:
    """
    Resolve a corpus-relative filename to a real local file.
    """
    path = CORPUS_ROOT / filename

    if not path.is_file():
        raise FileNotFoundError(
            f"Corpus document not found: {path}"
        )

    return path


def content_type_for(path: Path) -> str:
    """Return the MIME type supported by the current document service."""
    mapping = {
        ".pdf": "application/pdf",
        ".docx": (
            "application/"
            "vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        ".txt": "text/plain",
    }

    return mapping.get(
        path.suffix.lower(),
        "application/octet-stream",
    )


def build_multipart(
    field_name: str,
    path: Path,
) -> tuple[bytes, str]:
    """
    Build a multipart/form-data body without requiring the requests package.
    """
    boundary = (
        "----SuperDocsCorpusBoundary"
        + uuid.uuid4().hex
    )

    content_type = content_type_for(path)

    file_bytes = path.read_bytes()

    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; '
        f'name="{field_name}"; '
        f'filename="{path.name}"\r\n'
        f"Content-Type: {content_type}\r\n"
        f"\r\n"
    ).encode("utf-8")

    footer = (
        f"\r\n--{boundary}--\r\n"
    ).encode("utf-8")

    body = header + file_bytes + footer

    return body, f"multipart/form-data; boundary={boundary}"


def api_request(
    base_url: str,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    """
    Perform an HTTP request and decode the JSON response.
    """
    url = (
        base_url.rstrip("/")
        + "/"
        + path.lstrip("/")
    )

    request_headers = {
        "Accept": "application/json",
    }

    if headers:
        request_headers.update(headers)

    http_request = request.Request(
        url=url,
        data=body,
        headers=request_headers,
        method=method,
    )

    try:
        with request.urlopen(
            http_request,
            timeout=120,
        ) as response:
            raw = response.read()

            if not raw:
                return response.status, {}

            try:
                payload = json.loads(
                    raw.decode("utf-8")
                )
            except json.JSONDecodeError:
                payload = {
                    "raw": raw.decode(
                        "utf-8",
                        errors="replace",
                    )
                }

            return response.status, payload

    except error.HTTPError as exc:
        raw = exc.read()

        try:
            payload = json.loads(
                raw.decode("utf-8")
            )
        except json.JSONDecodeError:
            payload = {
                "raw": raw.decode(
                    "utf-8",
                    errors="replace",
                )
            }

        raise APIError(
            f"{method} {path} -> "
            f"HTTP {exc.code}: {payload}"
        ) from exc

    except error.URLError as exc:
        raise APIError(
            f"Cannot reach API at {url}: {exc.reason}"
        ) from exc


def upload_document(
    base_url: str,
    path: Path,
) -> dict:
    """
    Upload one document through POST /documents.
    """
    body, content_type = build_multipart(
        field_name="file",
        path=path,
    )

    _, payload = api_request(
        base_url,
        "POST",
        "/documents",
        body=body,
        headers={
            "Content-Type": content_type,
        },
    )

    required = {
        "document_id",
        "run_id",
        "filename",
        "status",
    }

    missing = required - payload.keys()

    if missing:
        raise APIError(
            "POST /documents response is missing fields: "
            + ", ".join(sorted(missing))
        )

    return payload


def get_run(
    base_url: str,
    run_id: str,
) -> dict:
    """
    Read the durable run state.
    """
    _, payload = api_request(
        base_url,
        "GET",
        f"/runs/{run_id}",
    )

    return payload


def resume_run(
    base_url: str,
    run_id: str,
) -> dict:
    """
    Execute/resume the workflow through the existing API endpoint.
    """
    _, payload = api_request(
        base_url,
        "POST",
        f"/runs/{run_id}/resume",
    )

    return payload


def get_findings(
    base_url: str,
    run_id: str,
) -> dict:
    """
    Fetch findings for a run.
    """
    _, payload = api_request(
        base_url,
        "GET",
        f"/runs/{run_id}/findings",
    )

    return payload


def wait_for_terminal_state(
    base_url: str,
    run_id: str,
    *,
    timeout_seconds: int,
    poll_seconds: float,
) -> dict:
    """
    Poll a run until it reaches a known terminal state.

    The current /resume route executes WorkflowRunner synchronously,
    but polling keeps the evaluator robust if execution later becomes
    asynchronous.
    """
    deadline = time.monotonic() + timeout_seconds

    while True:
        state = get_run(
            base_url,
            run_id,
        )

        status = str(
            state.get("status", "")
        ).lower()

        if status in SUCCESS_STATUSES:
            return state

        if status in FAILURE_STATUSES:
            return state

        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Run {run_id} did not reach a terminal state "
                f"within {timeout_seconds}s. "
                f"Last status={status!r}, "
                f"stage={state.get('current_stage')!r}"
            )

        time.sleep(poll_seconds)


def execute_document(
    base_url: str,
    document: dict,
    *,
    timeout_seconds: int,
    poll_seconds: float,
) -> dict:
    """
    Execute one document through ingestion and analysis.

    This intentionally stops at awaiting_review. It never automatically
    approves or rejects findings because human review is part of the
    application's workflow contract.
    """
    filename = document["filename"]
    path = resolve_document(filename)

    result = {
        "id": document["id"],
        "filename": filename,
        "format": document["format"],
        "language": document["language"],
        "expected": {
            "length_class": document["length_class"],
            "document_type": document["document_type"],
            "structural_features": document[
                "structural_features"
            ],
        },
        "started_at": utc_now(),
    }

    # ---------------------------------------------------------
    # Upload
    # ---------------------------------------------------------

    upload = upload_document(
        base_url,
        path,
    )

    result["upload"] = {
        "passed": True,
        "document_id": upload["document_id"],
        "run_id": upload["run_id"],
        "status": upload["status"],
    }

    run_id = upload["run_id"]

    # ---------------------------------------------------------
    # Inspect initial durable state
    # ---------------------------------------------------------

    initial_state = get_run(
        base_url,
        run_id,
    )

    result["initial_run"] = {
        "status": initial_state.get("status"),
        "current_stage": initial_state.get(
            "current_stage"
        ),
        "error": initial_state.get("error"),
    }

    status = str(
        initial_state.get("status", "")
    ).lower()

    # ---------------------------------------------------------
    # Execute/resume if the upload only created the run.
    # ---------------------------------------------------------

    if status not in SUCCESS_STATUSES | FAILURE_STATUSES:
        resumed = resume_run(
            base_url,
            run_id,
        )

        result["resume"] = {
            "passed": True,
            "status": resumed.get("status"),
            "current_stage": resumed.get(
                "current_stage"
            ),
            "error": resumed.get("error"),
        }

    # ---------------------------------------------------------
    # Wait for final automated state.
    # ---------------------------------------------------------

    final_state = wait_for_terminal_state(
        base_url,
        run_id,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )

    final_status = str(
        final_state.get("status", "")
    ).lower()

    result["run"] = {
        "passed": final_status in SUCCESS_STATUSES,
        "status": final_state.get("status"),
        "current_stage": final_state.get(
            "current_stage"
        ),
        "error": final_state.get("error"),
        "stages": final_state.get("stages", {}),
    }

    # ---------------------------------------------------------
    # Findings
    # ---------------------------------------------------------

    findings_payload = get_findings(
        base_url,
        run_id,
    )

    findings = findings_payload.get(
        "findings",
        [],
    )

    result["findings"] = {
        "passed": final_status in SUCCESS_STATUSES,
        "count": len(findings),
        "items": findings,
    }

    result["review"] = {
        "required": final_status == "awaiting_review",
        "automated": False,
        "note": (
            "Findings were intentionally not auto-approved. "
            "Human review remains a separate workflow step."
        ),
    }

    result["passed"] = (
        result["upload"]["passed"]
        and result["run"]["passed"]
        and result["findings"]["passed"]
    )

    result["completed_at"] = utc_now()

    return result


def save_results(
    suite_name: str,
    results: dict,
) -> Path:
    """
    Save an evaluation result artifact.
    """
    timestamp = (
        datetime.now(timezone.utc)
        .strftime("%Y%m%dT%H%M%SZ")
    )

    output_dir = (
        RESULT_ROOT
        / suite_name
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / f"{timestamp}.json"
    )

    output_path.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    return output_path


def print_document_result(
    index: int,
    total: int,
    result: dict,
) -> None:
    """Print a concise per-document result."""

    filename = result.get(
        "filename",
        "<unknown>",
    )

    print(
        f"\n[{index}/{total}] {filename}"
    )

    # Upload
    upload = result.get("upload")

    if upload is not None:
        print(
            f"  Upload       "
            f"{'PASS' if upload.get('passed') else 'FAIL'}"
        )

    # Run
    run = result.get("run")

    if run is not None:
        print(
            f"  Run          "
            f"{'PASS' if run.get('passed') else 'FAIL'} "
            f"({run.get('status')})"
        )

        print(
            f"  Stage        "
            f"{run.get('current_stage')}"
        )

        if run.get("error"):
            print(
                f"  Run error    "
                f"{run.get('error')}"
            )

    # Findings
    findings = result.get("findings")

    if findings is not None:
        print(
            f"  Findings     "
            f"{'PASS' if findings.get('passed') else 'FAIL'} "
            f"({findings.get('count', 0)})"
        )

    # Review
    review = result.get("review")

    if review and review.get("required"):
        print(
            "  Review       PENDING HUMAN REVIEW"
        )

    # Most important: show the actual exception.
    if result.get("error"):
        print(
            f"  ERROR        {result['error']}"
        )

def run_suite(
    suite_name: str,
    base_url: str,
    *,
    timeout_seconds: int,
    poll_seconds: float,
) -> int:
    """
    Execute a complete deterministic corpus suite.
    """
    suite = load_suite(suite_name)

    documents = suite.get(
        "documents",
        [],
    )

    print("=" * 60)
    print("SuperDocs Corpus Evaluation")
    print("=" * 60)
    print(f"Suite:       {suite_name}")
    print(f"Purpose:     {suite.get('purpose', '')}")
    print(f"Documents:   {len(documents)}")
    print(f"API:         {base_url}")
    print("=" * 60)

    if not documents:
        print("No documents in suite.")
        return 1

    results = {
        "suite": suite_name,
        "purpose": suite.get("purpose"),
        "api_base_url": base_url,
        "started_at": utc_now(),
        "documents_total": len(documents),
        "documents_passed": 0,
        "documents_failed": 0,
        "results": [],
    }

    for index, document in enumerate(
        documents,
        start=1,
    ):
        try:
            result = execute_document(
                base_url,
                document,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
            )

        except Exception as exc:
            result = {
                "id": document.get("id"),
                "filename": document.get(
                    "filename"
                ),
                "format": document.get(
                    "format"
                ),
                "language": document.get(
                    "language"
                ),
                "passed": False,
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "completed_at": utc_now(),
            }
        results["results"].append(result)

        if result.get("passed") is True:
            results["documents_passed"] += 1
        else:
            results["documents_failed"] += 1

        print_document_result(
            index,
            len(documents),
            result,
        )

    results["completed_at"] = utc_now()

    results["passed"] = (
        results["documents_failed"] == 0
    )

    output_path = save_results(
        suite_name,
        results,
    )

    print()
    print("=" * 60)
    print(
        "RESULT: "
        + (
            "PASS"
            if results["passed"]
            else "FAIL"
        )
    )
    print("=" * 60)
    print(
        f"Documents: "
        f"{results['documents_passed']}/"
        f"{results['documents_total']}"
    )
    print(
        f"Results:   {output_path}"
    )
    print("=" * 60)

    return 0 if results["passed"] else 1


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Run a deterministic Public Golden Corpus "
            "evaluation against SuperDocs."
        )
    )

    parser.add_argument(
        "--suite",
        required=True,
        choices=[
            "smoke",
            "multilingual",
            "structural",
            "full",
            "unsupported",
        ],
        help="Corpus test suite to execute.",
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=(
            "SuperDocs API base URL. "
            f"Default: {DEFAULT_BASE_URL}"
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum seconds to wait for one run.",
    )

    parser.add_argument(
        "--poll",
        type=float,
        default=1.0,
        help="Seconds between run-status polls.",
    )

    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = parse_args()

    try:
        return run_suite(
            suite_name=args.suite,
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            poll_seconds=args.poll,
        )

    except KeyboardInterrupt:
        print("\nEvaluation interrupted.")
        return 130

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

