# Playbook: App Not Using Proxy

Use when a browser works but a desktop app fails, or when command-line direct traffic fails while explicit proxy traffic works.

Check:

- System proxy state.
- Environment proxy variables.
- TUN or virtual adapter presence.
- Whether the app is known to ignore system proxy.
- Explicit proxy test result.

Do not toggle TUN or system proxy without separate confirmation and recovery steps.
