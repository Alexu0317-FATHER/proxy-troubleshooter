#!/usr/bin/env python3
"""Record user feedback and promote confirmed local solutions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_STATUSES = {"fixed", "unchanged", "new-symptom", "unconfirmed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_file_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_state_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        return Path(root) / "proxy-troubleshooter"
    if os.uname().sysname == "Darwin":  # type: ignore[attr-defined]
        return Path.home() / "Library" / "Application Support" / "proxy-troubleshooter"
    return Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")) / "proxy-troubleshooter"


def redact_path(path: Path | str) -> str:
    text = str(path)
    replacements = []
    for name in ("USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        value = os.environ.get(name)
        if value:
            replacements.append((value, f"%{name}%"))
    replacements.append((str(Path.home()), "~"))
    for raw, token in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        if text.lower().startswith(raw.lower()):
            return token + text[len(raw):]
    return text


def sanitize_text(value: str | None, limit: int = 500) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    text = re.sub(r"https?://([^/\s?#]+)[^\s]*", r"https://\1/[redacted]", text)
    text = re.sub(r"(?i)(token|secret|password|passwd|cookie|authorization)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    return text[:limit]


def stable_id(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temp.replace(path)


def ensure_state_layout(state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    for name in ("runs", "cases", "solutions"):
        (state_dir / name).mkdir(parents=True, exist_ok=True)


def update_run_feedback(run_path: Path, status: str, case_id: str, note: str | None) -> None:
    payload = read_json(run_path)
    payload["feedback_status"] = status
    payload["feedback_updated_at"] = utc_now()
    payload["case_id"] = case_id
    if note:
        payload["feedback_note"] = note
    write_json(run_path, payload)


def build_case(run_payload: dict[str, Any], run_path: Path, status: str, note: str | None) -> dict[str, Any]:
    target = run_payload.get("target_host")
    evidence = {
        "direct_test_result": run_payload.get("direct_test_result"),
        "explicit_proxy_test_result": run_payload.get("explicit_proxy_test_result"),
        "system_proxy_summary": run_payload.get("system_proxy_summary"),
        "dns_summary": run_payload.get("dns_summary"),
        "detected_proxy_clients": run_payload.get("detected_proxy_clients", []),
        "config_fingerprints": run_payload.get("config_fingerprints", []),
        "evidence_gaps": run_payload.get("evidence_gaps", []),
    }
    case = {
        "schema": "proxy-troubleshooter.case.v1",
        "case_id": stable_id({"run": str(run_path), "status": status, "time": utc_now()}),
        "created_at": utc_now(),
        "source_run": redact_path(run_path),
        "target_host": target,
        "user_visible_symptom": sanitize_text(run_payload.get("symptom_class")) or target or "general proxy problem",
        "feedback_status": status,
        "feedback_note": note,
        "most_relevant_evidence": evidence,
        "actions_attempted": run_payload.get("actions_attempted", []),
        "final_or_current_diagnosis": sanitize_text(run_payload.get("root_cause_classification"))
        or sanitize_text(run_payload.get("recommended_next_action")),
    }
    return case


def load_solution_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": "proxy-troubleshooter.solutions.v1", "solutions": []}
    payload = read_json(path)
    if "solutions" not in payload or not isinstance(payload["solutions"], list):
        payload["solutions"] = []
    return payload


def promote_solution(
    state_dir: Path,
    case_payload: dict[str, Any],
    run_payload: dict[str, Any],
    confirmation_source: str,
    solution_summary: str | None,
) -> Path:
    index_path = state_dir / "solutions" / "index.json"
    index = load_solution_index(index_path)
    solution_id = stable_id(
        {
            "target_host": case_payload.get("target_host"),
            "report_fingerprint": run_payload.get("report_fingerprint"),
            "case_id": case_payload.get("case_id"),
        }
    )
    entry = {
        "solution_id": solution_id,
        "created_at": utc_now(),
        "case_id": case_payload.get("case_id"),
        "target_host": case_payload.get("target_host"),
        "confirmation_source": confirmation_source,
        "solution_summary": solution_summary or case_payload.get("final_or_current_diagnosis"),
        "report_fingerprint": run_payload.get("report_fingerprint"),
        "config_fingerprints": run_payload.get("config_fingerprints", []),
    }
    existing = index["solutions"]
    for item_index, item in enumerate(existing):
        if isinstance(item, dict) and item.get("solution_id") == solution_id:
            existing[item_index] = entry
            break
    else:
        existing.append(entry)
    write_json(index_path, index)
    return index_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Record proxy-troubleshooter user feedback.")
    parser.add_argument("--run", required=True, help="Path to a runs/*.json file.")
    parser.add_argument("--state-dir", help="Override local state directory.")
    parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    parser.add_argument("--note", help="Short user-visible note. URLs and secret-looking values are redacted.")
    parser.add_argument("--verified", action="store_true", help="Independent verification proved the original target works.")
    parser.add_argument("--solution-summary", help="Short confirmed solution summary.")
    args = parser.parse_args()

    run_path = Path(args.run).expanduser().resolve()
    if not run_path.exists() or not run_path.is_file():
        print(json.dumps({"ok": False, "code": "missing_run", "message": "Run file does not exist."}, indent=2))
        return 2

    state_dir = Path(args.state_dir).expanduser().resolve() if args.state_dir else default_state_dir()
    ensure_state_layout(state_dir)

    run_payload = read_json(run_path)
    note = sanitize_text(args.note)
    solution_summary = sanitize_text(args.solution_summary)
    case_payload = build_case(run_payload, run_path, args.status, note)

    safe_target = re.sub(r"[^a-zA-Z0-9.-]+", "_", str(case_payload.get("target_host") or "general"))[:80].strip("._") or "general"
    case_path = state_dir / "cases" / f"case-{utc_file_stamp()}-{safe_target}.json"
    write_json(case_path, case_payload)
    update_run_feedback(run_path, args.status, case_payload["case_id"], note)

    result: dict[str, Any] = {
        "ok": True,
        "schema": "proxy-troubleshooter.feedback.v1",
        "status": args.status,
        "case_path": redact_path(case_path),
        "run_path": redact_path(run_path),
        "promoted_to_solution": False,
    }

    if args.status == "fixed" or args.verified:
        index_path = promote_solution(
            state_dir,
            case_payload,
            run_payload,
            "independent_verification" if args.verified else "user_feedback",
            solution_summary,
        )
        result["promoted_to_solution"] = True
        result["solution_index_path"] = redact_path(index_path)
    else:
        result["message"] = "Case saved but not promoted because the issue is not confirmed fixed."

    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
