# Clash And Mihomo Notes

Clash-style GUI clients are wrappers around a proxy core. The core config is commonly YAML, while GUI state may be JSON, SQLite, TOML, plist, shared preferences, or proprietary.

Low-risk rule edits are only low risk when they are narrow:

- Add a small number of target-related rules.
- Prefer a local override or custom rules area.
- Insert before catch-all rules such as `MATCH` or `FINAL`.
- Back up first.
- Validate changed state.
- Reload safely only when the client supports it.

Safe rule evidence:

- Count rules and catch-all lines.
- For the current target host, report whether a matching `DOMAIN`, `DOMAIN-SUFFIX`, or `DOMAIN-KEYWORD` rule appears before `MATCH`/`FINAL`.
- For local `rule-providers` inside the same config directory, read payload files and report only counts, hashes, and target match status.
- If a target-related rule appears only after `MATCH`/`FINAL`, classify it as a rule ordering problem.
- Hash policy or proxy group names instead of printing them.
- Do not emit full rule bodies.

Scoped ordering fix:

- Use `apply_scoped_rule_fix.py --move-existing` only when the existing matching rule is after `MATCH`/`FINAL`.
- Move only target-related `DOMAIN`, `DOMAIN-SUFFIX`, or `DOMAIN-KEYWORD` rules.
- Do not move provider rules, generated sections, or unrelated rules.

Do not edit subscriptions, generated provider files, node credentials, controller secrets, certificates, or large rule sections as a first response.
