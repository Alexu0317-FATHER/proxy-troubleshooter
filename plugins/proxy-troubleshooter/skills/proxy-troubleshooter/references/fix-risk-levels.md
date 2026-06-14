# Fix Risk Levels

`read_only` can run after the first-use notice:

- Inspect local ports, processes, system proxy, DNS/TUN state, proxy environment variables, and known proxy client paths.
- Parse non-sensitive config fields.
- Test target hosts through direct, system proxy, and explicit proxy paths.

`scoped_low_risk_agent_fix` needs concise authorization at action time:

- Add a small number of target-related domain rules to a local Clash/Mihomo override or custom rules area.
- Correct obvious syntax or spelling mistakes in rules relevant to the current target.
- Move only newly-added or clearly relevant local rules before a catch-all rule.
- Back up the affected file or API state.
- Validate changed state and verify the original target.

`connection_risk_fix` needs separate confirmation and offline recovery:

- Change system proxy, DNS, TUN, routes, virtual adapters, or broad app/browser proxy settings.
- Restart the proxy app or proxy core.

`sensitive_or_destructive_fix` should usually be avoided:

- Edit subscriptions, node credentials, controller secrets, certificates, MITM settings, account data, or generated full configs.
- Delete or reorder large rule sections.
- Read broad configuration directories when known client paths are enough.
- Apply changes that cannot be backed up or validated.
