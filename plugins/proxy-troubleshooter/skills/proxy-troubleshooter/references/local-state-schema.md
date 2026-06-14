# Local State Schema

Default state directories:

- Windows: `%LOCALAPPDATA%\proxy-troubleshooter\`
- macOS: `~/Library/Application Support/proxy-troubleshooter/`
- Linux: `${XDG_STATE_HOME:-~/.local/state}/proxy-troubleshooter/`

Layout:

```text
proxy-troubleshooter-state/
├── profile.json
├── cases/
│   └── case-*.json
├── solutions/
│   └── index.json
└── runs/
    └── run-*.json
```

`profile.json` stores stable local facts: OS, detected clients, candidate config paths, last known ports, common system proxy state, TUN/adapter presence, config fingerprints, completeness, and missing facts.

`runs/*.json` stores one diagnosis: target host/app, symptom class, direct/system/explicit proxy test results, DNS summary, config fingerprint, likely cause, target rule evidence when available, evidence gaps, fix risk level, backup or rollback handle, and feedback status.

`target_rule_evidence` is a redacted summary of whether the target host matched a domain rule before a catch-all rule. It must not contain full rule bodies or raw policy names.

`cases/*.json` stores summarized problem cards.

`solutions/index.json` stores only confirmed local solutions.

Current script support:

```bash
python scripts/diagnose_proxy.py --save-profile
python scripts/diagnose_proxy.py --target <hostname> --save-profile --save-run
python scripts/diagnose_proxy.py --state-dir <path> --save-profile --save-run
```

The script creates `profile.json`, `runs/`, `cases/`, and `solutions/` when saving state. It writes redacted JSON only.

Feedback support:

```bash
python scripts/record_feedback.py --run <run.json> --status fixed --solution-summary "Short confirmed fix"
python scripts/record_feedback.py --run <run.json> --status unchanged
python scripts/record_feedback.py --run <run.json> --status new-symptom --note "Short visible symptom"
```

`record_feedback.py` writes a `cases/*.json` card for every status. It promotes to `solutions/index.json` only when status is `fixed` or the command includes `--verified`.
