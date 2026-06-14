# Privacy

Proxy Troubleshooter is designed to run local diagnostics through Codex on the user's machine.

## Data Collection

This repository does not collect diagnostics, profiles, run logs, cases, proxy configuration, subscription URLs, credentials, or feedback records.

Runtime files are written only to local state directories when the user authorizes profile or run persistence. Those files are intentionally ignored by git.

## Local Data

The plugin may inspect local proxy evidence such as:

- proxy ports and listening processes
- system proxy and WinHTTP proxy state
- DNS and TUN hints
- likely proxy client process names
- non-sensitive Clash/Mihomo configuration shape
- redacted rule summaries and config fingerprints

The plugin must not print or store subscription URLs, node credentials, controller secrets, tokens, cookies, passwords, full account identifiers, or full config dumps.

## Assistant Provider Boundary

Text shown in a Codex conversation may be processed by the assistant provider. Do not paste unredacted subscription links, credentials, cookies, access tokens, or full private proxy configs into the conversation.

## Changes To Local Files

Read-only diagnostics and write actions are separate. Low-risk writes still require scoped authorization. Any rule-editing helper should back up the target config before writing and provide rollback guidance.
