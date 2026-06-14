# Privacy And Safety

First-use notice:

> To diagnose proxy problems with local evidence, I need to read local network and proxy state on this computer: proxy ports, system proxy settings, DNS/TUN state, likely proxy clients, and non-sensitive configuration fields. The initial profile setup is read-only. If a concrete problem has a narrow low-risk fix, such as adding or correcting a small number of related routing rules, I will explain exactly what I plan to change, back up the affected config or API state, request authorization, apply the change after approval, validate it, and show how to roll it back. I will not edit subscriptions or node credentials, change DNS/TUN/system proxy, restart proxy apps, or make changes that may disconnect this conversation without separate confirmation and recovery steps. Anything shown in this conversation may be processed by the assistant provider, so subscription links, tokens, account data, passwords, cookies, and secrets must be redacted before any output, log, or local case record is produced. Continue only if this is acceptable.

Rules:

- Redact before stdout, logs, files, or tool results.
- Store runtime state outside the plugin package.
- Store hostnames rather than full URLs by default.
- Do not emit raw configs. Emit hashes, counts, selected non-sensitive fields, and evidence summaries.
- If the user refuses local inspection, stop the automatic workflow and offer a limited manual checklist.
- If the user refuses a gated probe, mark an evidence gap rather than pretending the hypothesis was ruled out.
