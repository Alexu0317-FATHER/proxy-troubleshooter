# Proxy Troubleshooter

Version: 0.2.0

[简体中文](README.zh.md) | English

If YouTube works but Gmail refuses to load; if Google opens fine but LinkedIn mysteriously does not; or even if Claude Code works while Codex keeps reconnecting...

If these problems look related to network proxies and, like me, you keep asking AI about them, the AI ends up spending tokens over and over collecting the same local facts: system proxy state, Clash/Mihomo config, DNS, TUN, and routing rules.

Try Proxy Troubleshooter. It uses local evidence to diagnose proxy and VPN-like routing problems, and records investigated issues as local, redacted cases. When a similar issue comes back, you do not have to burn tokens collecting everything from scratch. If a config change is needed, it also gives backup and rollback guidance from a safety angle.

## What It Contains

- A shared plugin at `plugins/proxy-troubleshooter`.
- A Codex manifest at `plugins/proxy-troubleshooter/.codex-plugin/plugin.json`.
- A Claude Code manifest at `plugins/proxy-troubleshooter/.claude-plugin/plugin.json`.
- A Codex marketplace catalog at `.agents/plugins/marketplace.json`.
- A Claude Code marketplace catalog at `.claude-plugin/marketplace.json`.
- One bundled skill, `proxy-troubleshooter`.
- Read-only diagnostic helpers for local proxy state.
- A scoped Clash/Mihomo rule-fix helper that backs up the config before writing.
- A feedback helper for recording whether a fix worked, without uploading local cases to this repository.
- Tests under `tests/`.

## Install In Codex

Add this repository as a Codex plugin marketplace:

```powershell
codex plugin marketplace add Alexu0317-FATHER/proxy-troubleshooter
```

Then open the Codex plugin directory, install **Proxy Troubleshooter**, enable it, and start a new thread.

For local development from the repository root:

```powershell
codex plugin marketplace add .
```

If Codex does not show the plugin in the current thread, start a new Codex thread or restart the Codex app.

## Install In Claude Code Or Claude Code Desktop

This is a Claude Code plugin. Claude Code's official docs cover terminal, IDE, desktop app, and browser surfaces, so the same plugin applies to Claude Code Desktop.

Inside Claude Code or Claude Code Desktop:

```text
/plugin marketplace add Alexu0317-FATHER/proxy-troubleshooter
/plugin install proxy-troubleshooter@proxy-troubleshooter
/reload-plugins
```

You can then invoke the skill directly:

```text
/proxy-troubleshooter:proxy-troubleshooter
```

For non-interactive CLI setup:

```powershell
claude plugin marketplace add Alexu0317-FATHER/proxy-troubleshooter
claude plugin install proxy-troubleshooter@proxy-troubleshooter
```

For local development from the repository root:

```powershell
claude plugin validate .
claude plugin marketplace add .
claude plugin install proxy-troubleshooter@proxy-troubleshooter
```

To load the plugin directly for a single Claude Code session:

```powershell
claude --plugin-dir .\plugins\proxy-troubleshooter
```

## Safety Model

The plugin separates local diagnosis from local changes:

- Read-only discovery can inspect proxy ports, system proxy state, DNS/TUN hints, likely proxy clients, and non-sensitive config shape.
- Low-risk writes still require scoped authorization.
- Rule fixes are intentionally narrow and backed up before writing.
- The plugin must not print or store subscription URLs, node credentials, controller secrets, tokens, cookies, passwords, full account identifiers, or full config dumps.
- DNS, TUN, system proxy, route, certificate, MITM, app restart, and subscription changes require separate confirmation and recovery steps.

Local profiles, runs, cases, and backups are runtime state. They are intentionally ignored by git. See `PRIVACY.md` for the data boundary.

## Development

Run the script tests:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Validate the Codex skill and plugin with the bundled Codex validators when available:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" ".\plugins\proxy-troubleshooter\skills\proxy-troubleshooter"
python "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" ".\plugins\proxy-troubleshooter"
```

Validate the Claude marketplace and plugin when Claude Code is installed:

```powershell
claude plugin validate .
claude plugin validate .\plugins\proxy-troubleshooter
```

## Official Codex Plugin Directory

OpenAI's public Codex docs currently describe the app's Plugin Directory as including curated OpenAI plugins, plugins shared with a workspace, and plugins created or added by the user. They also document repo marketplaces as a way to share plugins.

The docs do not currently describe a self-serve public submission flow for third-party plugins to enter the official curated directory. Treat this repository marketplace as the public distribution path until OpenAI publishes an official submission process.

## Official Claude Plugin Marketplaces

Anthropic's Claude Code docs describe two public marketplaces:

- `claude-plugins-official`: curated by Anthropic. There is no application process.
- `claude-community`: the third-party community marketplace. Submit through Anthropic's in-app forms after running `claude plugin validate`.

Until this plugin is accepted into `claude-community`, install it directly from this GitHub marketplace repository.
