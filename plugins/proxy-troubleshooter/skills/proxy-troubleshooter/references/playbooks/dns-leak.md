# Playbook: DNS Leak Or Wrong Resolution

Use when target behavior changes by region, redirects unexpectedly, or explicit proxy path differs from normal path.

Check:

- Local DNS server summary.
- Direct DNS result for the hostname.
- Whether proxy DNS mode or fake-ip mode is enabled when visible from safe config fields.
- Whether the target is resolved before entering the proxy.

Changing DNS mode is a connection-risk fix and needs separate confirmation.
