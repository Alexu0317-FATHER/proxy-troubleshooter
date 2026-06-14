# Proxy Troubleshooter

Version: 0.1.0

Proxy Troubleshooter is a Codex plugin for diagnosing local proxy, Clash/Mihomo, routing rule, DNS, TUN, app bypass, and geo-redirect problems from local evidence.

It is designed for users who cannot describe proxy failures in specialist terms. The plugin guides Codex to inspect local proxy state, classify likely causes, and request scoped permission before applying narrow reversible fixes.

## What It Contains

- A Codex plugin at `plugins/proxy-troubleshooter`.
- One bundled skill, `proxy-troubleshooter`.
- Read-only diagnostic helpers for local proxy state.
- A scoped Clash/Mihomo rule-fix helper that backs up the config before writing.
- A feedback helper for recording whether a fix worked, without uploading local cases to this repository.
- Tests under `tests/`.

## Install From A Marketplace Repository

After this repository is published on GitHub, add it as a Codex plugin marketplace:

```powershell
codex plugin marketplace add Alexu0317-FATHER/proxy-troubleshooter
```

Then open the Codex plugin directory, install **Proxy Troubleshooter**, enable it, and start a new thread.

## Install From A Local Checkout

From the repository root:

```powershell
codex plugin marketplace add .
```

If Codex does not show the plugin in the current thread, start a new Codex thread or restart the Codex app.

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

Validate the skill and plugin with the bundled Codex validators when available:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" ".\plugins\proxy-troubleshooter\skills\proxy-troubleshooter"
python "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" ".\plugins\proxy-troubleshooter"
```

## Official Codex Plugin Directory

OpenAI's public Codex docs currently describe the app's Plugin Directory as including curated OpenAI plugins, plugins shared with a workspace, and plugins created or added by the user. They also document repo marketplaces as a way to share plugins.

The docs do not currently describe a self-serve public submission flow for third-party plugins to enter the official curated directory. Treat this repository marketplace as the public distribution path until OpenAI publishes an official submission process.
