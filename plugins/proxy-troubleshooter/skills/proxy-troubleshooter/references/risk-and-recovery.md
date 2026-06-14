# Risk And Recovery

Before a connection-risk or sensitive change:

- Warn that the change may disconnect the assistant session.
- Capture current settings needed for rollback.
- Prefer export, backup, or reversible temporary changes.
- Give recovery steps that work without proxy access or assistant availability.
- Confirm the user can open the proxy client UI before changing TUN, DNS, system proxy, or routes.
- Verify the target service and the assistant connection afterward where possible.

If no rollback path exists, do not perform the change. Try a lower-risk diagnostic step instead.
