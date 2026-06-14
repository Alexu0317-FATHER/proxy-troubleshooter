#!/usr/bin/env python3
"""Read-only local proxy diagnostics with redacted JSON output."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMMON_PROXY_PORTS = {1080, 20170, 20171, 2080, 33210, 6152, 7890, 7891, 7892, 7893, 7897, 9090}
CLIENT_HINTS = (
    "clash",
    "mihomo",
    "verge",
    "flclash",
    "v2ray",
    "xray",
    "sing-box",
    "singbox",
    "nekoray",
    "shadowsocks",
    "hiddify",
)
KNOWN_WINDOWS_CLIENT_PATHS = (
    ("clash-for-windows", "APPDATA", r"Clash for Windows\config.yaml"),
    ("clash-for-windows", "USERPROFILE", r".config\clash\config.yaml"),
    ("mihomo", "USERPROFILE", r".config\mihomo\config.yaml"),
    ("mihomo", "APPDATA", r"mihomo\config.yaml"),
    ("clash-verge", "APPDATA", r"clash-verge\profiles"),
    ("clash-verge-rev", "APPDATA", r"clash-verge-rev\profiles"),
    ("clash-verge-rev", "APPDATA", r"io.github.clash-verge-rev.clash-verge-rev\profiles"),
    ("flclash", "APPDATA", r"FlClash"),
    ("flclash", "LOCALAPPDATA", r"FlClash"),
    ("mihomo-party", "APPDATA", r"Mihomo Party"),
    ("v2rayn", "APPDATA", r"v2rayN"),
    ("nekoray", "APPDATA", r"nekoray"),
)
CONFIG_FILENAMES = {
    "config.yaml",
    "config.yml",
    "clash.yaml",
    "custom.yaml",
    "custom.yml",
    "mihomo.yaml",
    "merge.yaml",
    "merge.yml",
    "override.yaml",
    "override.yml",
    "profiles.yaml",
    "rules.yaml",
    "rules.yml",
}
MAX_CONFIG_BYTES = 5_000_000


def run_command(args: list[str], timeout: int = 5) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_file_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_state_dir() -> Path:
    system = platform.system().lower()
    if system == "windows":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        return Path(root) / "proxy-troubleshooter"
    if system == "darwin":
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


def ensure_state_layout(state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    for name in ("runs", "cases", "solutions"):
        (state_dir / name).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temp.replace(path)


def redact_proxy_value(value: str | None) -> dict[str, Any]:
    if not value:
        return {"set": False}
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme and parsed.netloc:
        host = parsed.hostname or "redacted-host"
        port = f":{parsed.port}" if parsed.port else ""
        return {"set": True, "redacted": f"{parsed.scheme}://{host}{port}"}
    if "@" in value:
        value = value.split("@", 1)[1]
    return {"set": True, "redacted": value}


def redacted_env_proxy() -> dict[str, Any]:
    keys = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"]
    out: dict[str, Any] = {}
    for key in keys:
        value = os.environ.get(key) or os.environ.get(key.lower())
        out[key] = redact_proxy_value(value)
    return out


def windows_system_proxy() -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"available": False, "reason": "not_windows"}
    try:
        import winreg  # type: ignore

        path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            result: dict[str, Any] = {"available": True}
            for name in ("ProxyEnable", "ProxyServer", "AutoConfigURL"):
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                    if name == "ProxyServer":
                        result[name] = redact_proxy_value(str(value))
                    elif name == "AutoConfigURL":
                        result[name] = redact_proxy_value(str(value))
                    else:
                        result[name] = value
                except FileNotFoundError:
                    result[name] = None
            return result
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": type(exc).__name__, "message": str(exc)}


def windows_winhttp_proxy() -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"available": False, "reason": "not_windows"}
    result = run_command(["netsh", "winhttp", "show", "proxy"])
    if not result.get("ok"):
        return {"available": False, "command": "netsh winhttp show proxy", "error": result}
    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    redacted = []
    for line in lines:
        redacted.append(re.sub(r"(https?=)([^;\s]+)", lambda m: m.group(1) + redact_proxy_value(m.group(2)).get("redacted", "set"), line))
    return {"available": True, "summary": redacted}


def windows_processes() -> list[str]:
    if platform.system().lower() != "windows":
        return []
    result = run_command(["tasklist", "/fo", "csv", "/nh"])
    if not result.get("ok"):
        return []
    names: list[str] = []
    reader = csv.reader(io.StringIO(result["stdout"]))
    for row in reader:
        if row:
            names.append(row[0])
    return sorted(set(names), key=str.lower)


def detect_proxy_clients(processes: list[str]) -> list[dict[str, str]]:
    found = []
    for name in processes:
        lower = name.lower()
        for hint in CLIENT_HINTS:
            if hint in lower:
                found.append({"process": name, "hint": hint})
                break
    return found


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def local_path_is_within(base: Path, target: Path) -> bool:
    try:
        resolved_base = base.resolve()
        resolved_target = target.resolve()
    except OSError:
        return False
    return str(resolved_target).lower().startswith(str(resolved_base).lower())


def safe_read_text(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > MAX_CONFIG_BYTES:
        raise ValueError("config_too_large")
    return data.decode("utf-8-sig", errors="replace")


def scalar_from_config(text: str, key: str) -> str | int | bool | None:
    match = re.search(rf"(?m)^{re.escape(key)}\s*:\s*([^#\r\n]+)", text)
    if not match:
        return None
    raw = match.group(1).strip().strip("'\"")
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    if key == "external-controller":
        return redact_proxy_value(raw)
    return raw


def nested_bool_from_config(text: str, section: str, key: str) -> bool | None:
    section_match = re.search(rf"(?ms)^{re.escape(section)}\s*:\s*\n(?P<body>(?:^[ \t]+.*\n?)*)", text)
    if not section_match:
        return None
    body = section_match.group("body")
    key_match = re.search(rf"(?m)^[ \t]+{re.escape(key)}\s*:\s*(true|false)\b", body, flags=re.IGNORECASE)
    if not key_match:
        return None
    return key_match.group(1).lower() == "true"


def normalize_host(host: str | None) -> str | None:
    if not host:
        return None
    parsed = urllib.parse.urlsplit(host if "://" in host else f"https://{host}")
    value = (parsed.hostname or host).strip().lower().rstrip(".")
    if not re.fullmatch(r"[a-z0-9.-]+", value):
        return None
    return value


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


def is_catch_all_rule(rule_type: str) -> bool:
    return rule_type in {"MATCH", "FINAL"}


def domain_rule_matches(rule_type: str, rule_target: str, host: str) -> bool:
    if rule_type == "DOMAIN":
        return host == rule_target
    if rule_type == "DOMAIN-SUFFIX":
        return host == rule_target or host.endswith(f".{rule_target}")
    if rule_type == "DOMAIN-KEYWORD":
        return rule_target in host
    return False


def section_lines(text: str, section: str) -> tuple[int, list[tuple[int, str, int]]]:
    lines = text.splitlines()
    start = -1
    base_indent = 0
    body: list[tuple[int, str, int]] = []
    for index, line in enumerate(lines, start=1):
        if re.match(rf"^\s*{re.escape(section)}\s*:\s*(?:#.*)?$", line):
            start = index
            base_indent = len(line) - len(line.lstrip(" "))
            break
    if start < 0:
        return -1, []
    for index, line in enumerate(lines[start:], start=start + 1):
        if not line.strip() or line.lstrip().startswith("#"):
            body.append((index, line, len(line) - len(line.lstrip(" "))))
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= base_indent:
            break
        body.append((index, line, indent))
    return start, body


def parse_provider_entries(text: str) -> list[dict[str, Any]]:
    _, body = section_lines(text, "rule-providers")
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_indent = 0
    for line_no, line, indent in body:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        provider_match = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(?:#.*)?$", stripped)
        if provider_match and (current is None or indent <= current_indent):
            current = {"name": provider_match.group(1), "line": line_no, "fields": {}}
            current_indent = indent
            entries.append(current)
            continue
        if current is None:
            continue
        field_match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.+?)\s*(?:#.*)?$", stripped)
        if field_match and indent > current_indent:
            current["fields"][field_match.group(1)] = field_match.group(2).strip().strip("'\"")
    return entries


def parse_provider_payload_rules(text: str, behavior: str | None) -> list[dict[str, Any]]:
    _, body = section_lines(text, "payload")
    rows: list[dict[str, Any]] = []
    for line_no, line, _ in body:
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped[1:].strip().strip("'\"")
        if not item or item.startswith("#"):
            continue
        parsed = parse_rule_value(f"- {item}")
        if parsed and parsed[0] in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}:
            rule_type, rule_target, policy = parsed
            rows.append({"line": line_no, "type": rule_type, "target": rule_target, "policy": policy, "catch_all": False})
            continue
        normalized_item = item.lstrip("+.").lstrip(".").lower()
        if behavior == "domain" and re.fullmatch(r"[a-z0-9*.-]+", normalized_item):
            rows.append({"line": line_no, "type": "DOMAIN-SUFFIX", "target": normalized_item, "policy": None, "catch_all": False})
    return rows


def provider_name_hashes_before_catch_all(rule_rows: list[dict[str, Any]], first_catch_all_line: int | None) -> set[str]:
    hashes = set()
    for row in rule_rows:
        if row["type"] != "RULE-SET" or not row.get("target"):
            continue
        if first_catch_all_line is None or row["line"] < first_catch_all_line:
            hashes.add(hash_text(row["target"]))
    return hashes


def summarize_target_rule_match(
    rule_rows: list[dict[str, Any]],
    host: str | None,
    provider_summaries: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized = normalize_host(host)
    if not normalized:
        return None

    first_catch_all_line = None
    matches = []
    for row in rule_rows:
        if first_catch_all_line is None and row["catch_all"]:
            first_catch_all_line = row["line"]
        if domain_rule_matches(row["type"], row["target"], normalized):
            matches.append(row)

    referenced_provider_hashes = provider_name_hashes_before_catch_all(rule_rows, first_catch_all_line)
    provider_matches = []
    for provider in (provider_summaries or {}).get("providers", []):
        if provider.get("name_fingerprint") not in referenced_provider_hashes:
            continue
        target_match = provider.get("target_rule_match")
        if isinstance(target_match, dict) and target_match.get("matching_before_catch_all"):
            provider_matches.append(provider)

    first_match = matches[0] if matches else None
    direct_matching_before_catch_all = bool(
        first_match and (first_catch_all_line is None or first_match["line"] < first_catch_all_line)
    )
    matching_before_catch_all = direct_matching_before_catch_all or bool(provider_matches)
    match_after_catch_all = bool(first_match and first_catch_all_line is not None and first_match["line"] > first_catch_all_line)
    missing_before_catch_all = not matching_before_catch_all

    summary: dict[str, Any] = {
        "host": normalized,
        "matching_rule_count_total": len(matches),
        "matching_rule_count_before_catch_all": sum(
            1 for item in matches if first_catch_all_line is None or item["line"] < first_catch_all_line
        ),
        "matching_provider_count_before_catch_all": len(provider_matches),
        "matching_before_catch_all": matching_before_catch_all,
        "match_after_catch_all": match_after_catch_all,
        "missing_before_catch_all": missing_before_catch_all,
        "first_catch_all_line": first_catch_all_line,
    }
    if first_match:
        summary["first_match_line"] = first_match["line"]
        summary["first_match_type"] = first_match["type"]
        if first_match.get("policy"):
            summary["first_match_policy_fingerprint"] = hash_text(first_match["policy"])
    if provider_matches:
        summary["first_provider_match_fingerprint"] = provider_matches[0].get("name_fingerprint")
    return summary


def summarize_rules(
    text: str,
    target_host: str | None = None,
    provider_summaries: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lines = text.splitlines()
    in_rules = False
    base_indent = 0
    rule_count = 0
    catch_all_lines: list[int] = []
    rule_rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        if re.match(r"^\s*rules\s*:\s*(?:#.*)?$", line):
            in_rules = True
            base_indent = len(line) - len(line.lstrip(" "))
            continue
        if not in_rules:
            continue
        if line.strip() and not line.lstrip().startswith("#"):
            indent = len(line) - len(line.lstrip(" "))
            if indent <= base_indent and not line.startswith(" " * (base_indent + 1)):
                break
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        parsed = parse_rule_value(stripped)
        if not parsed:
            continue
        rule_type, rule_target, policy = parsed
        rule_count += 1
        catch_all = is_catch_all_rule(rule_type)
        if catch_all:
            catch_all_lines.append(index)
        rule_rows.append(
            {
                "line": index,
                "type": rule_type,
                "target": rule_target,
                "policy": policy,
                "catch_all": catch_all,
            }
        )
    summary: dict[str, Any] = {"rule_count": rule_count, "catch_all_lines": catch_all_lines[:5]}
    target_summary = summarize_target_rule_match(rule_rows, target_host, provider_summaries)
    if target_summary is not None:
        summary["target_rule_match"] = target_summary
    return summary


def summarize_local_rule_provider(provider: dict[str, Any], config_path: Path, target_host: str | None) -> dict[str, Any]:
    fields = provider.get("fields", {})
    name = provider.get("name", "")
    provider_type = fields.get("type")
    behavior = fields.get("behavior")
    provider_path = fields.get("path")
    summary: dict[str, Any] = {
        "name_fingerprint": hash_text(str(name)),
        "line": provider.get("line"),
        "type": provider_type,
        "behavior": behavior,
        "has_path": bool(provider_path),
    }
    if not provider_path:
        return summary
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", provider_path):
        summary["path_kind"] = "remote"
        return summary

    path = Path(provider_path)
    if not path.is_absolute():
        path = config_path.parent / path
    try:
        resolved = path.resolve()
    except OSError as exc:
        summary["read_error"] = type(exc).__name__
        return summary
    if not local_path_is_within(config_path.parent, resolved):
        summary["path_kind"] = "outside_config_dir"
        return summary
    summary["path_kind"] = "local"
    summary["path"] = redact_path(resolved)
    if not resolved.exists() or not resolved.is_file():
        summary["exists"] = False
        return summary
    summary["exists"] = True
    if resolved.stat().st_size > MAX_CONFIG_BYTES:
        summary["skipped"] = "too_large"
        return summary
    try:
        text = safe_read_text(resolved)
    except Exception as exc:  # noqa: BLE001
        summary["read_error"] = type(exc).__name__
        return summary
    payload_rows = parse_provider_payload_rules(text, behavior)
    summary["fingerprint"] = sha256_file(resolved)
    summary["payload_rule_count"] = len(payload_rows)
    target_summary = summarize_target_rule_match(payload_rows, target_host)
    if target_summary is not None:
        summary["target_rule_match"] = target_summary
    return summary


def summarize_rule_providers(text: str, config_path: Path, target_host: str | None) -> dict[str, Any]:
    providers = parse_provider_entries(text)
    summaries = [summarize_local_rule_provider(provider, config_path, target_host) for provider in providers]
    return {
        "provider_count": len(providers),
        "local_provider_count": sum(1 for item in summaries if item.get("path_kind") == "local"),
        "readable_provider_count": sum(1 for item in summaries if item.get("fingerprint")),
        "target_provider_match_count": sum(
            1 for item in summaries if item.get("target_rule_match", {}).get("matching_before_catch_all")
        ),
        "providers": summaries,
    }


def summarize_config(path: Path, target_host: str | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": redact_path(path),
        "exists": path.exists(),
        "kind": "file",
    }
    if not path.exists() or not path.is_file():
        return summary
    size = path.stat().st_size
    summary["size_bytes"] = size
    if size > MAX_CONFIG_BYTES:
        summary["skipped"] = "too_large"
        return summary
    try:
        text = safe_read_text(path)
    except Exception as exc:  # noqa: BLE001
        summary["read_error"] = type(exc).__name__
        return summary
    summary["fingerprint"] = sha256_file(path)
    fields: dict[str, Any] = {}
    for key in ("mode", "mixed-port", "port", "socks-port", "redir-port", "tproxy-port", "allow-lan", "external-controller"):
        value = scalar_from_config(text, key)
        if value is not None:
            fields[key] = value
    tun_enabled = nested_bool_from_config(text, "tun", "enable")
    dns_enabled = nested_bool_from_config(text, "dns", "enable")
    if tun_enabled is not None:
        fields["tun.enable"] = tun_enabled
    if dns_enabled is not None:
        fields["dns.enable"] = dns_enabled
    summary["safe_fields"] = fields
    provider_summary = summarize_rule_providers(text, path, target_host)
    if provider_summary["provider_count"]:
        summary["rule_providers"] = provider_summary
    summary["rules"] = summarize_rules(text, target_host, provider_summary)
    return summary


def candidate_files_from_dir(directory: Path) -> list[Path]:
    files: list[Path] = []
    try:
        for child in directory.iterdir():
            if child.is_file() and child.name.lower() in CONFIG_FILENAMES:
                files.append(child)
            elif child.is_dir() and child.name.lower() in {"profiles", "profile", "clash", "mihomo"}:
                for grandchild in child.iterdir():
                    if grandchild.is_file() and grandchild.suffix.lower() in {".yaml", ".yml"}:
                        files.append(grandchild)
    except OSError:
        return []
    return sorted(files, key=lambda item: str(item).lower())[:20]


def windows_config_candidates(target_host: str | None = None) -> list[dict[str, Any]]:
    if platform.system().lower() != "windows":
        return []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for family, env_name, relative in KNOWN_WINDOWS_CLIENT_PATHS:
        base = os.environ.get(env_name)
        if not base:
            continue
        path = Path(base) / relative
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        entry: dict[str, Any] = {
            "family": family,
            "path": redact_path(path),
            "exists": path.exists(),
            "path_type": "directory" if path.is_dir() else "file" if path.is_file() else "missing",
        }
        if path.is_file():
            entry["configs"] = [summarize_config(path, target_host)]
        elif path.is_dir():
            files = candidate_files_from_dir(path)
            entry["candidate_config_count"] = len(files)
            entry["configs"] = [summarize_config(item, target_host) for item in files]
        candidates.append(entry)
    return candidates


def extract_ports_from_value(value: Any) -> set[int]:
    text = json.dumps(value, ensure_ascii=True) if not isinstance(value, str) else value
    ports = set()
    for match in re.finditer(r":(\d{2,5})", text):
        port = int(match.group(1))
        if 0 < port <= 65535:
            ports.add(port)
    return ports


def windows_listening_ports(expected_ports: set[int]) -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"available": False, "reason": "not_windows"}
    result = run_command(["netstat", "-ano", "-p", "tcp"], timeout=8)
    if not result.get("ok"):
        return {"available": False, "error": result}
    ports = []
    seen = set()
    other_loopback_count = 0
    for line in result["stdout"].splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local = parts[1]
        state = parts[3].upper()
        pid = parts[4]
        if state != "LISTENING":
            continue
        match = re.search(r":(\d+)$", local)
        if not match:
            continue
        port = int(match.group(1))
        host = local.rsplit(":", 1)[0].strip("[]")
        is_expected = port in expected_ports
        is_common = port in COMMON_PROXY_PORTS
        is_loopback = host in {"127.0.0.1", "::1"}
        if not is_expected and not is_common:
            if is_loopback:
                other_loopback_count += 1
            continue
        key = (host, port, pid)
        if key in seen:
            continue
        seen.add(key)
        ports.append({"host": host, "port": port, "pid": pid, "common_proxy_port": is_common, "expected_proxy_port": is_expected})
    return {
        "available": True,
        "ports": ports,
        "other_loopback_listening_count": other_loopback_count,
    }


def windows_dns_and_adapters() -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"available": False, "reason": "not_windows"}
    result = run_command(["ipconfig", "/all"], timeout=8)
    if not result.get("ok"):
        return {"available": False, "error": result}
    dns_servers: list[str] = []
    adapter_hints: list[str] = []
    current_adapter = None
    for raw in result["stdout"].splitlines():
        line = raw.rstrip()
        header = re.match(r"^[A-Za-z].*adapter (.+):$", line)
        if header:
            current_adapter = header.group(1)
            lower = current_adapter.lower()
            if any(token in lower for token in ("tun", "wintun", "clash", "mihomo", "wireguard", "sing")):
                adapter_hints.append(current_adapter)
        if "DNS Servers" in line or (dns_servers and raw.startswith(" " * 36)):
            matches = re.findall(r"(?:(?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F:]{3,})", line)
            dns_servers.extend(matches)
    return {
        "available": True,
        "dns_servers": sorted(set(dns_servers)),
        "tun_adapter_hints": sorted(set(adapter_hints)),
    }


def resolve_host(host: str) -> dict[str, Any]:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ips = sorted({info[4][0] for info in infos})
        return {"ok": True, "addresses": ips[:8], "address_count": len(ips)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}


def fetch_target(host: str, proxy: str | None = None) -> dict[str, Any]:
    url = f"https://{host}/"
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "proxy-troubleshooter/0.1"})
    started = time.time()
    try:
        with opener.open(request, timeout=8) as response:
            return {
                "ok": True,
                "status": response.status,
                "elapsed_ms": int((time.time() - started) * 1000),
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": True,
            "status": exc.code,
            "elapsed_ms": int((time.time() - started) * 1000),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": type(exc).__name__,
            "message": str(exc),
            "elapsed_ms": int((time.time() - started) * 1000),
        }


def fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def observed_proxy_ports(report: dict[str, Any]) -> list[int]:
    ports: set[int] = set()
    ports.update(extract_ports_from_value(report.get("env_proxy")))
    ports.update(extract_ports_from_value(report.get("system_proxy")))
    ports.update(extract_ports_from_value(report.get("winhttp_proxy")))
    listening = report.get("listening_ports", {})
    if isinstance(listening, dict):
        for item in listening.get("ports", []):
            if isinstance(item, dict) and isinstance(item.get("port"), int):
                ports.add(item["port"])
    return sorted(ports)


def config_fingerprints(config_candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for candidate in config_candidates:
        for config in candidate.get("configs", []):
            fingerprint_value = config.get("fingerprint")
            path = config.get("path")
            if fingerprint_value and path:
                out.append({"path": path, "fingerprint": fingerprint_value})
    return out


def has_any_existing_config(config_candidates: list[dict[str, Any]]) -> bool:
    for candidate in config_candidates:
        if candidate.get("exists"):
            return True
    return False


def has_config_read_error(config_candidates: list[dict[str, Any]]) -> bool:
    for candidate in config_candidates:
        for config in candidate.get("configs", []):
            if config.get("read_error"):
                return True
    return False


def target_rule_evidence(config_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = []
    for candidate in config_candidates:
        for config in candidate.get("configs", []):
            rules = config.get("rules", {})
            target_summary = rules.get("target_rule_match")
            if isinstance(target_summary, dict):
                summaries.append(target_summary)

    if not summaries:
        return {"available": False}

    matching_before = any(item.get("matching_before_catch_all") for item in summaries)
    match_after = any(item.get("match_after_catch_all") for item in summaries)
    missing_before = all(item.get("missing_before_catch_all") for item in summaries)
    return {
        "available": True,
        "checked_config_count": len(summaries),
        "matching_before_catch_all": matching_before,
        "match_after_catch_all": match_after,
        "missing_before_catch_all": missing_before,
        "summaries": summaries,
    }


def build_diagnosis(report: dict[str, Any]) -> dict[str, Any]:
    listening = report.get("listening_ports", {})
    listening_ports = listening.get("ports", []) if isinstance(listening, dict) else []
    expected_listening = [item for item in listening_ports if isinstance(item, dict) and item.get("expected_proxy_port")]
    config_candidates = report.get("config_candidates", [])
    target = report.get("target", {})
    direct = target.get("direct_https") if isinstance(target, dict) else None
    explicit = target.get("explicit_proxy", {}).get("result") if isinstance(target, dict) else None
    rule_evidence = target_rule_evidence(config_candidates)

    evidence_gaps = []
    if has_config_read_error(config_candidates):
        evidence_gaps.append("proxy_config_read_permission")
    if not report.get("detected_proxy_clients"):
        evidence_gaps.append("proxy_client_process")

    if report.get("system_proxy", {}).get("ProxyEnable") and not expected_listening:
        return {
            "root_cause_classification": "proxy-core-down-or-wrong-port",
            "recommended_next_action": "Verify the proxy client is running and that system proxy points to a listening local port.",
            "evidence_gaps": evidence_gaps,
        }

    if expected_listening and not report.get("detected_proxy_clients") and not has_any_existing_config(config_candidates):
        return {
            "root_cause_classification": "unknown-gui-client",
            "recommended_next_action": "Use the unknown GUI client playbook; avoid broad directory reads unless the user approves a gated probe.",
            "evidence_gaps": evidence_gaps,
        }

    if rule_evidence.get("available") and rule_evidence.get("match_after_catch_all"):
        return {
            "root_cause_classification": "rule-ordered-after-catch-all",
            "recommended_next_action": "A target-related rule appears after a catch-all rule. Request authorization to move only the relevant rule before the catch-all.",
            "evidence_gaps": evidence_gaps,
            "target_rule_evidence": rule_evidence,
        }

    if rule_evidence.get("available") and rule_evidence.get("missing_before_catch_all"):
        return {
            "root_cause_classification": "rule-not-matched",
            "recommended_next_action": "No target-related rule matches before the catch-all. If proxy tests support it, request authorization to add a narrow domain rule.",
            "evidence_gaps": evidence_gaps,
            "target_rule_evidence": rule_evidence,
        }

    if explicit and explicit.get("ok") and direct and not direct.get("ok"):
        return {
            "root_cause_classification": "app-not-using-proxy-or-rule-not-matched",
            "recommended_next_action": "Check whether the failing app is bypassing system proxy or whether a target-related rule is missing.",
            "evidence_gaps": evidence_gaps,
            "target_rule_evidence": rule_evidence,
        }

    if explicit and not explicit.get("ok") and direct and direct.get("ok"):
        return {
            "root_cause_classification": "proxy-path-target-failure",
            "recommended_next_action": "The target works directly but not through the explicit proxy; inspect proxy exit, rule, or client compatibility evidence.",
            "evidence_gaps": evidence_gaps,
            "target_rule_evidence": rule_evidence,
        }

    if has_config_read_error(config_candidates):
        return {
            "root_cause_classification": "evidence-gap-config-permission",
            "recommended_next_action": "Request scoped permission to read the detected proxy config if rule matching or config fingerprint is required.",
            "evidence_gaps": evidence_gaps,
        }

    return {
        "root_cause_classification": "insufficient-evidence",
        "recommended_next_action": "Use the selected playbook and gather only the missing evidence needed for the user's symptom.",
        "evidence_gaps": evidence_gaps,
        "target_rule_evidence": rule_evidence,
    }


def build_profile(report: dict[str, Any]) -> dict[str, Any]:
    config_candidates = report.get("config_candidates", [])
    missing_facts = []
    if not report.get("detected_proxy_clients"):
        missing_facts.append("proxy_client_process")
    if has_config_read_error(config_candidates):
        missing_facts.append("proxy_config_read_permission")
    if not config_fingerprints(config_candidates):
        missing_facts.append("proxy_config_fingerprint")
    return {
        "schema": "proxy-troubleshooter.profile.v1",
        "created_or_updated_at": utc_now(),
        "platform": report.get("platform"),
        "detected_proxy_clients": report.get("detected_proxy_clients", []),
        "candidate_config_paths": config_candidates,
        "last_known_proxy_ports": observed_proxy_ports(report),
        "system_proxy_commonly_enabled": bool(report.get("system_proxy", {}).get("ProxyEnable")),
        "tun_adapters_seen": report.get("dns_and_adapters", {}).get("tun_adapter_hints", []),
        "config_fingerprints": config_fingerprints(config_candidates),
        "profile_completeness": "partial" if missing_facts else "usable",
        "missing_facts": missing_facts,
    }


def save_profile(report: dict[str, Any], state_dir: Path) -> Path:
    ensure_state_layout(state_dir)
    profile = build_profile(report)
    path = state_dir / "profile.json"
    write_json(path, profile)
    return path


def save_run(report: dict[str, Any], state_dir: Path) -> Path:
    ensure_state_layout(state_dir)
    target = report.get("target", {}).get("host") or "general"
    safe_target = re.sub(r"[^a-zA-Z0-9.-]+", "_", str(target))[:80].strip("._") or "general"
    path = state_dir / "runs" / f"run-{utc_file_stamp()}-{safe_target}.json"
    run_payload = {
        "schema": "proxy-troubleshooter.run.v1",
        "created_at": utc_now(),
        "target_host": report.get("target", {}).get("host"),
        "platform": report.get("platform"),
        "direct_test_result": report.get("target", {}).get("direct_https"),
        "explicit_proxy_test_result": report.get("target", {}).get("explicit_proxy"),
        "system_proxy_summary": report.get("system_proxy"),
        "dns_summary": report.get("dns_and_adapters"),
        "detected_proxy_clients": report.get("detected_proxy_clients", []),
        "config_fingerprints": config_fingerprints(report.get("config_candidates", [])),
        "target_rule_evidence": report.get("diagnosis", {}).get("target_rule_evidence"),
        "root_cause_classification": report.get("diagnosis", {}).get("root_cause_classification"),
        "recommended_next_action": report.get("diagnosis", {}).get("recommended_next_action"),
        "report_fingerprint": report.get("fingerprint"),
        "fix_risk_level_considered": "read_only",
        "evidence_gaps": report.get("diagnosis", {}).get("evidence_gaps", build_profile(report).get("missing_facts", [])),
        "feedback_status": "not_confirmed",
    }
    write_json(path, run_payload)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only local proxy diagnostics.")
    parser.add_argument("--target", help="Hostname to test, without path or query.")
    parser.add_argument("--proxy", help="Explicit proxy URL for target testing, for example http://127.0.0.1:7890.")
    parser.add_argument("--state-dir", help="Override local state directory.")
    parser.add_argument("--save-profile", action="store_true", help="Write or refresh profile.json in the local state directory.")
    parser.add_argument("--save-run", action="store_true", help="Save a redacted run record in the local state directory.")
    args = parser.parse_args()

    target = None
    if args.target:
        parsed = urllib.parse.urlsplit(args.target if "://" in args.target else f"https://{args.target}")
        target = parsed.hostname
        if not target:
            print(json.dumps({"ok": False, "error": "invalid_target"}, indent=2))
            return 2

    processes = windows_processes()
    env_proxy = redacted_env_proxy()
    system_proxy = windows_system_proxy()
    winhttp_proxy = windows_winhttp_proxy()
    expected_ports = set()
    expected_ports.update(extract_ports_from_value(env_proxy))
    expected_ports.update(extract_ports_from_value(system_proxy))
    expected_ports.update(extract_ports_from_value(winhttp_proxy))
    report: dict[str, Any] = {
        "ok": True,
        "schema": "proxy-troubleshooter.diagnose.v1",
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "env_proxy": env_proxy,
        "system_proxy": system_proxy,
        "winhttp_proxy": winhttp_proxy,
        "listening_ports": windows_listening_ports(expected_ports),
        "detected_proxy_clients": detect_proxy_clients(processes),
        "dns_and_adapters": windows_dns_and_adapters(),
        "config_candidates": windows_config_candidates(target),
    }

    if target:
        report["target"] = {
            "host": target,
            "dns": resolve_host(target),
            "direct_https": fetch_target(target),
        }
        if args.proxy:
            report["target"]["explicit_proxy"] = {
                "proxy": redact_proxy_value(args.proxy),
                "result": fetch_target(target, args.proxy),
            }

    report["diagnosis"] = build_diagnosis(report)
    report["fingerprint"] = fingerprint(report)
    if args.save_profile or args.save_run:
        state_dir = Path(args.state_dir).expanduser().resolve() if args.state_dir else default_state_dir()
        report["state"] = {"state_dir": str(state_dir)}
        if args.save_profile:
            report["state"]["profile_path"] = str(save_profile(report, state_dir))
        if args.save_run:
            report["state"]["run_path"] = str(save_run(report, state_dir))
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
