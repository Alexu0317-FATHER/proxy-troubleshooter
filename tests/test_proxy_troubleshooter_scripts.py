import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "proxy-troubleshooter" / "skills" / "proxy-troubleshooter"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


diagnose_proxy = load_module("diagnose_proxy", SKILL / "scripts" / "diagnose_proxy.py")
rule_fix = load_module("apply_scoped_rule_fix", SKILL / "scripts" / "apply_scoped_rule_fix.py")
record_feedback = load_module("record_feedback", SKILL / "scripts" / "record_feedback.py")


class ProxyTroubleshooterScriptTests(unittest.TestCase):
    def test_rule_insert_happens_before_match(self):
        source = "mixed-port: 7890\nrules:\n  - DOMAIN-SUFFIX,google.com,Proxy\n  - MATCH,DIRECT\n"
        updated, metadata = rule_fix.insert_rules(source, ["DOMAIN-SUFFIX,gmail.com,Proxy"])

        self.assertEqual(metadata["inserted_count"], 1)
        self.assertLess(updated.index("DOMAIN-SUFFIX,gmail.com,Proxy"), updated.index("MATCH,DIRECT"))

    def test_rule_summary_matches_domain_suffix_without_emitting_policy(self):
        source = "rules:\n  - DOMAIN-SUFFIX,google.com,SecretProxyGroup\n  - MATCH,DIRECT\n"

        summary = diagnose_proxy.summarize_rules(source, "mail.google.com")

        match = summary["target_rule_match"]
        self.assertTrue(match["matching_before_catch_all"])
        self.assertEqual(match["first_match_type"], "DOMAIN-SUFFIX")
        self.assertIn("first_match_policy_fingerprint", match)
        self.assertNotIn("SecretProxyGroup", json.dumps(summary))

    def test_rule_summary_detects_missing_before_match(self):
        source = "rules:\n  - DOMAIN-SUFFIX,google.com,Proxy\n  - MATCH,DIRECT\n"

        summary = diagnose_proxy.summarize_rules(source, "gmail.com")

        match = summary["target_rule_match"]
        self.assertFalse(match["matching_before_catch_all"])
        self.assertTrue(match["missing_before_catch_all"])
        self.assertEqual(match["first_catch_all_line"], 3)

    def test_diagnosis_marks_rule_after_catch_all(self):
        report = {
            "system_proxy": {"ProxyEnable": 1},
            "listening_ports": {"ports": [{"port": 7890, "expected_proxy_port": True}]},
            "detected_proxy_clients": [{"process": "clash.exe", "hint": "clash"}],
            "config_candidates": [
                {
                    "exists": True,
                    "configs": [
                        {
                            "rules": {
                                "target_rule_match": {
                                    "matching_before_catch_all": False,
                                    "match_after_catch_all": True,
                                    "missing_before_catch_all": True,
                                }
                            }
                        }
                    ],
                }
            ],
        }

        diagnosis = diagnose_proxy.build_diagnosis(report)

        self.assertEqual(diagnosis["root_cause_classification"], "rule-ordered-after-catch-all")

    def test_diagnosis_marks_rule_not_matched(self):
        report = {
            "system_proxy": {"ProxyEnable": 1},
            "listening_ports": {"ports": [{"port": 7890, "expected_proxy_port": True}]},
            "detected_proxy_clients": [{"process": "clash.exe", "hint": "clash"}],
            "config_candidates": [
                {
                    "exists": True,
                    "configs": [
                        {
                            "rules": {
                                "target_rule_match": {
                                    "matching_before_catch_all": False,
                                    "match_after_catch_all": False,
                                    "missing_before_catch_all": True,
                                }
                            }
                        }
                    ],
                }
            ],
        }

        diagnosis = diagnose_proxy.build_diagnosis(report)

        self.assertEqual(diagnosis["root_cause_classification"], "rule-not-matched")

    def test_rule_provider_summary_matches_target_without_emitting_provider_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            provider_dir = root / "rules"
            provider_dir.mkdir()
            (provider_dir / "google.yaml").write_text(
                "payload:\n  - DOMAIN-SUFFIX,google.com\n",
                encoding="utf-8",
            )
            config = root / "config.yaml"
            config.write_text(
                "rule-providers:\n"
                "  private-google-provider:\n"
                "    type: file\n"
                "    behavior: classical\n"
                "    path: ./rules/google.yaml\n"
                "rules:\n"
                "  - RULE-SET,private-google-provider,SecretProxyGroup\n"
                "  - MATCH,DIRECT\n",
                encoding="utf-8",
            )

            summary = diagnose_proxy.summarize_config(config, "mail.google.com")

            serialized = json.dumps(summary)
            self.assertEqual(summary["rule_providers"]["target_provider_match_count"], 1)
            self.assertTrue(summary["rules"]["target_rule_match"]["matching_before_catch_all"])
            self.assertEqual(summary["rules"]["target_rule_match"]["matching_provider_count_before_catch_all"], 1)
            self.assertNotIn("private-google-provider", serialized)
            self.assertNotIn("SecretProxyGroup", serialized)

    def test_rule_provider_outside_config_dir_is_not_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            outside = root / "outside"
            config_dir = root / "config"
            outside.mkdir()
            config_dir.mkdir()
            (outside / "provider.yaml").write_text("payload:\n  - DOMAIN-SUFFIX,gmail.com\n", encoding="utf-8")
            config = config_dir / "config.yaml"
            config.write_text(
                "rule-providers:\n"
                "  outside-provider:\n"
                "    type: file\n"
                "    behavior: classical\n"
                "    path: ../outside/provider.yaml\n"
                "rules:\n"
                "  - RULE-SET,outside-provider,Proxy\n"
                "  - MATCH,DIRECT\n",
                encoding="utf-8",
            )

            summary = diagnose_proxy.summarize_config(config, "gmail.com")

            provider = summary["rule_providers"]["providers"][0]
            self.assertEqual(provider["path_kind"], "outside_config_dir")
            self.assertNotIn("target_rule_match", provider)

    def test_move_existing_rule_before_match(self):
        source = "rules:\n  - DOMAIN-SUFFIX,google.com,Proxy\n  - MATCH,DIRECT\n  - DOMAIN-SUFFIX,gmail.com,Proxy\n"

        updated, metadata = rule_fix.move_existing_rules_before_catch_all(source, ["gmail.com"])

        self.assertEqual(metadata["moved_count"], 1)
        self.assertLess(updated.index("DOMAIN-SUFFIX,gmail.com,Proxy"), updated.index("MATCH,DIRECT"))

    def test_move_existing_cli_dry_run_reports_no_write(self):
        fixture = ROOT / "tests" / "fixtures" / "sample-clash-ordered.yaml"

        completed = subprocess.run(
            [
                sys.executable,
                str(SKILL / "scripts" / "apply_scoped_rule_fix.py"),
                "--config",
                str(fixture),
                "--domain",
                "gmail.com",
                "--move-existing",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertFalse(result["applied"])
        self.assertTrue(result["changed"])
        self.assertEqual(result["operation"], "move_existing")
        self.assertEqual(result["metadata"]["moved_count"], 1)
        self.assertIn("Dry run only", result["message"])

    def test_profile_marks_config_read_permission_gap(self):
        report = {
            "platform": {"system": "Windows"},
            "detected_proxy_clients": [],
            "system_proxy": {"ProxyEnable": 1},
            "dns_and_adapters": {"tun_adapter_hints": []},
            "config_candidates": [
                {
                    "family": "clash-for-windows",
                    "path": "%USERPROFILE%\\.config\\clash\\config.yaml",
                    "exists": True,
                    "path_type": "file",
                    "configs": [{"path": "%USERPROFILE%\\.config\\clash\\config.yaml", "read_error": "PermissionError"}],
                }
            ],
        }

        profile = diagnose_proxy.build_profile(report)

        self.assertIn("proxy_config_read_permission", profile["missing_facts"])
        self.assertIn("proxy_config_fingerprint", profile["missing_facts"])

    def test_diagnosis_marks_proxy_port_gap(self):
        report = {
            "system_proxy": {"ProxyEnable": 1},
            "listening_ports": {"ports": []},
            "detected_proxy_clients": [],
            "config_candidates": [],
        }

        diagnosis = diagnose_proxy.build_diagnosis(report)

        self.assertEqual(diagnosis["root_cause_classification"], "proxy-core-down-or-wrong-port")

    def test_fixed_feedback_promotes_solution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = pathlib.Path(temp_dir)
            run_dir = state_dir / "runs"
            run_dir.mkdir(parents=True)
            run_path = run_dir / "run-test.json"
            run_path.write_text(
                json.dumps(
                    {
                        "schema": "proxy-troubleshooter.run.v1",
                        "target_host": "gmail.com",
                        "direct_test_result": {"ok": False},
                        "explicit_proxy_test_result": {"result": {"ok": True}},
                        "system_proxy_summary": {"ProxyEnable": 1},
                        "dns_summary": {"dns_servers": ["192.168.1.1"]},
                        "detected_proxy_clients": [],
                        "config_fingerprints": [{"path": "%USERPROFILE%\\.config\\clash\\config.yaml", "fingerprint": "abc"}],
                        "root_cause_classification": "app-not-using-proxy-or-rule-not-matched",
                        "recommended_next_action": "Added a target-related rule.",
                        "report_fingerprint": "report1",
                        "evidence_gaps": [],
                    }
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SKILL / "scripts" / "record_feedback.py"),
                    "--run",
                    str(run_path),
                    "--state-dir",
                    str(state_dir),
                    "--status",
                    "fixed",
                    "--note",
                    "It works now: https://mail.google.com/mail?token=abc token=abc",
                    "--solution-summary",
                    "Added a narrow Gmail rule.",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertTrue(result["promoted_to_solution"])
            self.assertTrue((state_dir / "solutions" / "index.json").exists())

            index = json.loads((state_dir / "solutions" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index["solutions"]), 1)
            self.assertEqual(index["solutions"][0]["target_host"], "gmail.com")

            updated_run = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(updated_run["feedback_status"], "fixed")

            cases = list((state_dir / "cases").glob("case-*.json"))
            self.assertEqual(len(cases), 1)
            case_payload = json.loads(cases[0].read_text(encoding="utf-8"))
            self.assertIn("https://mail.google.com/[redacted]", case_payload["feedback_note"])
            self.assertNotIn("token=abc", case_payload["feedback_note"])

    def test_unchanged_feedback_does_not_promote_solution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = pathlib.Path(temp_dir)
            run_dir = state_dir / "runs"
            run_dir.mkdir(parents=True)
            run_path = run_dir / "run-test.json"
            run_path.write_text(
                json.dumps({"schema": "proxy-troubleshooter.run.v1", "target_host": "gmail.com"}),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SKILL / "scripts" / "record_feedback.py"),
                    "--run",
                    str(run_path),
                    "--state-dir",
                    str(state_dir),
                    "--status",
                    "unchanged",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertFalse(result["promoted_to_solution"])
            self.assertFalse((state_dir / "solutions" / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
