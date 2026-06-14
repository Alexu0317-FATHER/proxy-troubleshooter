#!/usr/bin/env python3
"""Apply a narrow Clash/Mihomo domain rule fix with backup."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_RULE_TYPES = {"DOMAIN-SUFFIX", "DOMAIN", "DOMAIN-KEYWORD"}


def fail(message: str, code: str = "error", status: int = 1) -> int:
    print(json.dumps({"ok": False, "code": code, "message": message}, indent=2))
    return status


def normalize_domain(domain: str) -> str:
    value = domain.strip().lower().lstrip(".")
    if not re.fullmatch(r"[a-z0-9*.-]+", value) or ".." in value or not value:
        raise ValueError(f"Invalid domain: {domain}")
    return value


def validate_policy(policy: str) -> str:
    value = policy.strip()
    if not value or "," in value or "\n" in value or "\r" in value:
        raise ValueError("Policy must be a non-empty Clash/Mihomo policy name without commas.")
    return value


def sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


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


def find_rules_block(lines: list[str]) -> tuple[int, int, str]:
    start = -1
    base_indent = ""
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)rules\s*:\s*(?:#.*)?$", line)
        if match:
            start = index
            base_indent = match.group(1)
            break
    if start < 0:
        raise ValueError("Could not find a top-level rules: block.")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent_len = len(line) - len(line.lstrip(" "))
        if indent_len <= len(base_indent) and not line.startswith(base_indent + " "):
            end = index
            break

    rule_indent = base_indent + "  "
    for index in range(start + 1, end):
        match = re.match(r"^(\s*)-\s+", lines[index])
        if match:
            rule_indent = match.group(1)
            break
    return start, end, rule_indent


def build_rule(rule_type: str, domain: str, policy: str) -> str:
    return f"{rule_type},{domain},{policy}"


def parse_rule_value(line: str) -> tuple[str, str, str | None] | None:
    stripped = line.strip()
    if not stripped.startswith("-"):
        return None
    rule_value = stripped[1:].strip().strip("'\"")
    if not rule_value or rule_value.startswith("#"):
        return None
    parts = [part.strip() for part in rule_value.split(",")]
    if not parts:
        return None
    rule_type = parts[0].upper()
    rule_target = parts[1].lower().lstrip(".") if len(parts) > 1 else ""
    policy = parts[2] if len(parts) > 2 else None
    return rule_type, rule_target, policy


def is_catch_all_rule(line: str) -> bool:
    parsed = parse_rule_value(line)
    return bool(parsed and parsed[0] in {"MATCH", "FINAL"})


def domain_rule_matches(rule_type: str, rule_target: str, domain: str) -> bool:
    normalized = domain.lower().lstrip(".")
    if rule_type == "DOMAIN":
        return normalized == rule_target
    if rule_type == "DOMAIN-SUFFIX":
        return normalized == rule_target or normalized.endswith(f".{rule_target}") or rule_target.endswith(f".{normalized}")
    if rule_type == "DOMAIN-KEYWORD":
        return rule_target in normalized
    return False


def insert_rules(text: str, new_rules: list[str]) -> tuple[str, dict[str, Any]]:
    lines = text.splitlines()
    had_trailing_newline = text.endswith(("\n", "\r\n"))
    start, end, rule_indent = find_rules_block(lines)

    existing = set()
    insert_at = end
    for index in range(start + 1, end):
        stripped = lines[index].strip()
        if stripped.startswith("-"):
            rule_value = stripped[1:].strip().strip("'\"")
            existing.add(rule_value.lower())
            if insert_at == end and is_catch_all_rule(stripped):
                insert_at = index

    inserted = []
    for rule in new_rules:
        if rule.lower() not in existing:
            inserted.append(f"{rule_indent}- {rule}")

    if inserted:
        lines[insert_at:insert_at] = inserted

    output = "\n".join(lines)
    if had_trailing_newline:
        output += "\n"
    return output, {
        "rules_block_start_line": start + 1,
        "rules_block_end_line": end,
        "insert_line": insert_at + 1,
        "inserted_count": len(inserted),
        "skipped_existing_count": len(new_rules) - len(inserted),
    }


def move_existing_rules_before_catch_all(text: str, domains: list[str]) -> tuple[str, dict[str, Any]]:
    lines = text.splitlines()
    had_trailing_newline = text.endswith(("\n", "\r\n"))
    start, end, _ = find_rules_block(lines)

    catch_all_index = None
    for index in range(start + 1, end):
        if is_catch_all_rule(lines[index].strip()):
            catch_all_index = index
            break
    if catch_all_index is None:
        output = "\n".join(lines)
        if had_trailing_newline:
            output += "\n"
        return output, {
            "rules_block_start_line": start + 1,
            "rules_block_end_line": end,
            "moved_count": 0,
            "reason": "no_catch_all_rule",
        }

    move_indices = []
    for index in range(catch_all_index + 1, end):
        parsed = parse_rule_value(lines[index])
        if not parsed:
            continue
        rule_type, rule_target, _ = parsed
        if rule_type not in ALLOWED_RULE_TYPES:
            continue
        if any(domain_rule_matches(rule_type, rule_target, domain) for domain in domains):
            move_indices.append(index)

    if not move_indices:
        output = "\n".join(lines)
        if had_trailing_newline:
            output += "\n"
        return output, {
            "rules_block_start_line": start + 1,
            "rules_block_end_line": end,
            "moved_count": 0,
            "insert_line": catch_all_index + 1,
        }

    moved_lines = [lines[index] for index in move_indices]
    remaining = [line for index, line in enumerate(lines) if index not in set(move_indices)]
    adjusted_insert_at = catch_all_index - sum(1 for index in move_indices if index < catch_all_index)
    remaining[adjusted_insert_at:adjusted_insert_at] = moved_lines

    output = "\n".join(remaining)
    if had_trailing_newline:
        output += "\n"
    return output, {
        "rules_block_start_line": start + 1,
        "rules_block_end_line": end,
        "insert_line": adjusted_insert_at + 1,
        "moved_count": len(moved_lines),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Add or move narrow Clash/Mihomo domain rules with backup.")
    parser.add_argument("--config", required=True, help="Path to a Clash/Mihomo YAML config file.")
    parser.add_argument("--domain", action="append", required=True, help="Domain to add. Repeat for multiple domains.")
    parser.add_argument("--policy", help="Policy or proxy group name to route matching domains to.")
    parser.add_argument("--rule-type", default="DOMAIN-SUFFIX", choices=sorted(ALLOWED_RULE_TYPES))
    parser.add_argument("--move-existing", action="store_true", help="Move existing target-related domain rules before MATCH/FINAL.")
    parser.add_argument("--apply", action="store_true", help="Write the change. Without this flag, run a dry-run.")
    args = parser.parse_args()

    try:
        config_path = Path(args.config).expanduser().resolve()
        if not config_path.exists() or not config_path.is_file():
            return fail("Config path does not exist or is not a file.", "missing_config")
        if config_path.stat().st_size > 5_000_000:
            return fail("Config is too large for this narrow fixer.", "config_too_large")

        domains = [normalize_domain(item) for item in args.domain]
        original = config_path.read_text(encoding="utf-8-sig")
        if args.move_existing:
            rules = []
            updated, metadata = move_existing_rules_before_catch_all(original, domains)
        else:
            if not args.policy:
                return fail("--policy is required unless --move-existing is used.", "missing_policy", 2)
            policy = validate_policy(args.policy)
            rules = [build_rule(args.rule_type, domain, policy) for domain in domains]
            updated, metadata = insert_rules(original, rules)
        changed = updated != original

        result: dict[str, Any] = {
            "ok": True,
            "schema": "proxy-troubleshooter.scoped-rule-fix.v1",
            "applied": False,
            "changed": changed,
            "config_path": redact_path(config_path),
            "config_hash_before": sha256_short(original),
            "operation": "move_existing" if args.move_existing else "insert_rules",
            "planned_rules": rules,
            "metadata": metadata,
        }

        if args.apply and changed:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = config_path.with_name(f"{config_path.name}.proxy-troubleshooter.{timestamp}.bak")
            shutil.copy2(config_path, backup_path)
            config_path.write_text(updated, encoding="utf-8")
            result["applied"] = True
            result["backup_path"] = redact_path(backup_path)
            result["config_hash_after"] = sha256_short(updated)
            result["rollback"] = f"Restore backup file: {redact_path(backup_path)}"
        elif args.apply and not changed:
            result["message"] = "No write performed because all planned rules already exist."
        else:
            result["message"] = "Dry run only. Re-run with --apply after user authorization."

        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail(str(exc), type(exc).__name__)


if __name__ == "__main__":
    raise SystemExit(main())
