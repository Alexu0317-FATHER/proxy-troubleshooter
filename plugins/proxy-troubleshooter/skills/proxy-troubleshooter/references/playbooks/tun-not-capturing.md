# Playbook: TUN Not Capturing

Use when browser traffic works but non-browser app traffic bypasses the proxy and no app-specific proxy setting exists.

Check:

- TUN or virtual adapter presence.
- System proxy state.
- Explicit proxy behavior for the app or equivalent command.
- Whether the app ignores system proxy.

Toggling TUN changes broad traffic behavior and may disconnect the assistant session. Treat it as `connection_risk_fix`.
