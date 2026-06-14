# Playbook: Proxy Core Down

Use when expected proxy ports are not listening or explicit proxy tests fail before reaching the target.

Check:

- Proxy client process presence.
- Listening loopback ports.
- System proxy target port.
- Recent profile port fingerprints.

Restarting a proxy app or core is a connection-risk fix. Ask for confirmation and recovery steps first.
