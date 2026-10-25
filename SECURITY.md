# Security policy

## Supported versions

The project is under active development. Security fixes are applied to the latest version on the `main` branch only.

## Reporting a vulnerability

Please do not disclose a vulnerability in a public issue. Use **Security → Report a vulnerability** (GitHub private vulnerability reporting) on this repository, or contact the maintainer privately through [GitHub](https://github.com/sudemkirmiz).

If you can, include:

- the affected commit or version;
- reproducible steps and a proof of concept;
- the likely impact and the preconditions of the attack;
- a suggested fix or workaround, if you have one.

Do not include API keys, face photos, real user profiles or other personal data in the report. Use synthetic data only.

## Scope

Reports in these areas are especially valuable:

- authentication bypass or unauthorized access to another profile's data;
- path traversal, malicious image processing or resource exhaustion;
- leaks of API keys, photos, journal entries or reports;
- data sent to an AI provider beyond the documented scope;
- dependency and supply-chain risks.

## Built-in protections

Each of these is covered by automated tests in `tests/test_security.py` and `tests/test_api.py`:

- Every `/api` route requires the access token (only the `/api/health` readiness probe is open); the token is compared in constant time. The test walks all routes, so a new endpoint cannot ship unprotected.
- After 20 wrong tokens in an hour, an IP is paused, even for the right token.
- Cookies authenticate reads (GET/HEAD) only; every request that changes data must send headers, a second CSRF barrier on top of `SameSite=Strict`.
- With `PROFILE_SCOPE=device` each browser sees only its own profiles, records, journal and shelf; another device's data answers exactly like missing data. The server stores only the SHA-256 hash of the device key.
- Provider keys typed by users are validated for format and length, never stored on the server and never logged.
- Host and CORS allowlists; wildcards are rejected in public mode.
- The request-body limit is enforced before parsing; images are validated for type, integrity, size and decoded pixel count.
- CSP (as a response header, and as a meta tag in the built page), HSTS, COOP, CORP, X-Frame-Options, nosniff and a restrictive Permissions-Policy.
- Static file serving cannot leave the build folder; download file names are reduced to ASCII; CSV exports neutralize formula injection.
- Photos are never written to disk; the service worker caches only the public app shell.
- CI runs Ruff, Bandit, pip-audit, npm audit and CodeQL; Dependabot watches dependencies.

## Deployment responsibility

The access token and device-scoped profiles are designed for a small group of people who trust each other. An internet service with independent user accounts needs an identity provider, TLS termination, central rate limiting, backups and monitoring in front of the app. See the checklist in [docs/deployment.md](docs/deployment.md).
