---
name: proxy-troubleshooter
description: Diagnose and fix local proxy, Clash/Mihomo, VPN-like routing, DNS, TUN, system proxy, app bypass, geo-redirect, and rule matching problems from local evidence. Use when a user says a site or app cannot connect, only some related services fail, traffic is not going through the proxy, a proxy client seems running but routing is wrong, or they want Claude Code, Claude Code Desktop, or Codex to inspect and safely repair local proxy configuration with permission.
---

# Proxy Troubleshooter

## Overview

Use local evidence first. The user is usually not a network specialist, so do not ask them to self-diagnose DNS, TUN, SNI, rule order, or routing mode before checking what can be checked locally.

This skill should feel like a local agent with permission, not a support article. Do not send the user to click through a GUI for repetitive low-risk edits after they authorize the agent to perform a narrow fix.

## Script Path Resolution

Resolve bundled scripts relative to this `SKILL.md`.

- In Claude Code or Claude Code Desktop plugin installs, prefer `${CLAUDE_SKILL_DIR}`.
- In Codex or a local checkout, resolve paths from the loaded skill directory.
- If neither runtime exposes a skill directory variable, inspect the plugin folder and use absolute paths.

## Required References

Read these before action:

- `references/privacy-and-safety.md`
- `references/fix-risk-levels.md`
- `references/troubleshooting-flow.md`

Read as needed:

- `references/local-state-schema.md` when creating or updating local state.
- `references/interaction-patterns.md` when the user's symptom is vague.
- `references/client-detectors.md` and `references/mihomo-clash-notes.md` for Clash/Mihomo or GUI wrapper cases.
- `references/risk-and-recovery.md` before any connection-risk or sensitive change.
- `references/playbooks/*.md` for symptom-specific diagnosis.

## Workflow

1. Check for an existing local profile in the platform state directory:
   - Windows: `%LOCALAPPDATA%\proxy-troubleshooter\`
   - macOS: `~/Library/Application Support/proxy-troubleshooter/`
   - Linux: `${XDG_STATE_HOME:-~/.local/state}/proxy-troubleshooter/`
2. If no usable profile exists, give the first-use notice from `references/privacy-and-safety.md`, then run only read-only discovery after acceptance.
3. If a profile exists, load it and refresh only facts that are missing or likely stale for the current problem.
4. Translate vague reports into visible facts. Ask what the user sees, which app/site fails, whether related sites work, and whether it started after a proxy or rule change.
5. Run read-only probes and classify the likely cause. Prefer the bundled script:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/diagnose_proxy.py" --target <hostname>
```

For initialization or profile refresh, save the redacted profile:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/diagnose_proxy.py" --save-profile
```

For a concrete problem, save both profile and run evidence:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/diagnose_proxy.py" --target <hostname> --save-profile --save-run
```

On Windows, this wrapper is also available:

```powershell
& "${CLAUDE_SKILL_DIR}/scripts/diagnose-proxy.ps1" -Target <hostname> -SaveProfile -SaveRun
```

6. If a gated probe is needed, explain why and ask for approval. If refused, record the evidence gap and continue only where the remaining evidence supports a conclusion.
7. Before any fix, classify it as `read_only`, `scoped_low_risk_agent_fix`, `connection_risk_fix`, or `sensitive_or_destructive_fix`.
8. For a scoped low-risk config fix, explain the exact change, backup path, validation, and rollback; request authorization; then execute after approval. For Clash/Mihomo rule additions, prefer:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/apply_scoped_rule_fix.py" --config <config.yaml> --domain <domain> --policy <policy>
python "${CLAUDE_SKILL_DIR}/scripts/apply_scoped_rule_fix.py" --config <config.yaml> --domain <domain> --policy <policy> --apply
```

If diagnosis says a target-related rule exists after `MATCH`/`FINAL`, move only that existing rule before the catch-all after authorization:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/apply_scoped_rule_fix.py" --config <config.yaml> --domain <domain> --move-existing
python "${CLAUDE_SKILL_DIR}/scripts/apply_scoped_rule_fix.py" --config <config.yaml> --domain <domain> --move-existing --apply
```

9. After a fix or suggested action, ask whether the original issue is fixed, unchanged, or changed into a new symptom. Save confirmed solutions only after user confirmation or independent verification.

Record the answer with:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/record_feedback.py" --run <state-dir>/runs/<run-file>.json --status fixed --solution-summary "Short confirmed fix"
python "${CLAUDE_SKILL_DIR}/scripts/record_feedback.py" --run <state-dir>/runs/<run-file>.json --status unchanged
python "${CLAUDE_SKILL_DIR}/scripts/record_feedback.py" --run <state-dir>/runs/<run-file>.json --status new-symptom --note "Short visible symptom"
```

Only `fixed` or `--verified` promotes an entry into `solutions/index.json`.

## Hard Boundaries

- Never print or store subscription URLs, node credentials, controller secrets, tokens, cookies, passwords, full account identifiers, or full config dumps.
- Never promise that nothing is uploaded if diagnostic output is shown in the assistant conversation. Promise redacted local summaries instead.
- Never silently change proxy configuration. Low-risk writes still need scoped authorization.
- Never change DNS, TUN, system proxy, routes, app-wide proxy settings, subscriptions, credentials, certificates, MITM settings, or restart proxy apps without separate confirmation and recovery steps.
- Prefer scripts and narrow tool wrappers over freehand edits to fragile proxy configuration.
