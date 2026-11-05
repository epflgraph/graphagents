# GraphAuth — security tooling & hardening reference

## Secret-scan tooling

- `.githooks/pre-commit` → `scripts/security/scan-staged.sh`: scans staged Git contents for secrets and FAILS CLOSED if scanning fails. Never bypass or weaken this hook.
- `scripts/security/scan-leaks.sh`: audits secrets in PUBLISHED history — fetches all origin branches into an isolated bare clone (local-only commits/staged/workdir excluded), then TruffleHog (with live verification) + gitleaks against `.gitleaks.toml`.
  - Usage: `./scripts/security/scan-leaks.sh` or `--json report.json`.
  - Exit codes: 0 clean, 1 findings, 2 scan failed.
- `FAKE-CREDENTIALS-hook-test.txt`: deliberate fake-credential fixture for verifying the pre-commit hook actually fires — keep it fake; never replace with real values.

These scripts are the seed patterns for the `graphsecurity` repo — when generalizing them there, keep the fail-closed behavior and the exit-code convention.

## Known hardening candidates (2026-10 onboarding review — verify before acting)

- `GRAPHAUTH_SESSION_SECRET` falls back to a value derived from the DB password when empty — deterministic; consider making it required.
- No rate limiting on `/v1/verify` yet; 256-bit keys make brute force impractical, but a limiter also protects the MariaDB round-trip cost per request.
- Decision audit log is on the roadmap (`/v1/verify_many` too) — a detective control worth prioritizing.
- Everything is plain HTTP until the edge reverse proxy + TLS lands; ports are loopback-protected in the meantime — keep it that way.
- Admin-UI session cookie flags (HttpOnly/SameSite/Secure) are worth verifying in `admin.py`.
