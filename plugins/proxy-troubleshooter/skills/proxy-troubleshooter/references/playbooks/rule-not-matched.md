# Playbook: Rule Not Matched

Use when a related site works but the target site fails, or when explicit proxy tests work while normal app/browser traffic does not.

Evidence to gather:

- Target hostname and related working hostname.
- Current proxy mode if visible from non-sensitive config fields.
- Rule list fingerprint and count.
- Whether a matching domain rule exists before catch-all rules.
- Direct, system proxy, and explicit proxy test results.

Candidate fix:

- If evidence points to missing rule coverage, request authorization for `scoped_low_risk_agent_fix`.
- Add only target-related domain suffix rules.
- Back up and verify.
