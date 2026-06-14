# Playbook: Geo Redirect

Use when the site opens but redirects to an unexpected region, language, login endpoint, or blocked variant.

Check:

- Direct and explicit proxy target behavior.
- Exit-region clues from non-sensitive test responses.
- DNS result differences.
- Whether related domains use different routing rules.

Treat broad node or region changes as user-directed actions, not automatic fixes.
