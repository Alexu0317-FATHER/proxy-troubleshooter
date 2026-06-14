# Interaction Patterns

Ask for visible facts, not jargon.

Good:

- What app or site is failing?
- What do you see: spinning, timeout, redirect, login error, certificate warning, or blocked page?
- Does a related site work?
- Does it fail in browser, desktop app, or both?
- Did this start after a proxy client, rule, subscription, or system setting change?

Avoid:

- "Is this a DNS leak?"
- "Is your SNI blocked?"
- "Is TUN capturing this app?"
- "Is the rule provider ordered before MATCH?"

When the user says "Google works but Gmail does not", treat it as related services taking different paths. Check browser failure shape, redirect/login stage, local rule coverage, DNS result, and explicit proxy behavior.

After any fix, ask the user to answer with one of: fixed, unchanged, or new symptom.
