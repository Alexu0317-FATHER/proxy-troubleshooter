# Troubleshooting Flow

1. Look for a usable profile.
2. Initialize or refresh only the needed local facts.
3. Translate the symptom into observable facts.
4. Search confirmed local solutions.
5. Run read-only probes.
6. Request approval for gated probes only when needed.
7. Explain evidence, gaps, likely cause, and candidate fix.
8. Classify fix risk.
9. For scoped low-risk fixes, request authorization, back up, apply, validate, and verify.
10. For risky fixes, prepare offline recovery first.
11. Ask for feedback: fixed, unchanged, or new symptom.
12. Record feedback as a case.
13. Promote a solution only after confirmation or verification.

Common root causes:

- Proxy core is not running or the expected port is unavailable.
- System proxy is disabled or points at the wrong port.
- The target app bypasses the system proxy.
- TUN is disabled and non-browser traffic is not captured.
- A rule is missing, ordered incorrectly, or written in the wrong syntax.
- DNS resolution leaks or resolves to the wrong region.
- Exit region causes service-side redirect or blocking.
- GUI wrapper hides or overrides the core config.

Current lightweight classifications emitted by `diagnose_proxy.py`:

- `proxy-core-down-or-wrong-port`
- `unknown-gui-client`
- `rule-not-matched`
- `rule-ordered-after-catch-all`
- `app-not-using-proxy-or-rule-not-matched`
- `proxy-path-target-failure`
- `evidence-gap-config-permission`
- `insufficient-evidence`

When a target host is provided and a readable Clash/Mihomo config is found, `diagnose_proxy.py` emits a redacted `target_rule_evidence` summary. Use it to distinguish a missing target rule from a rule that exists after `MATCH`/`FINAL`. It also summarizes local rule-provider payloads under the same config directory. Do not ask the model to inspect or quote the full rule list.
