# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.3.x   | ✅ Active          |
| < 1.3   | ❌ No longer supported |

## Reporting a Vulnerability

If you discover a security vulnerability in SecuringSkies / ADS-B Research Grid,
please contact the maintainers directly via the project issue tracker at
https://github.com/rwiren/adsb-research-grid/security/advisories.

Please **do not** open public issues for undisclosed security bugs.

## Hardcoded Secrets Policy

- No credentials may be committed to the repository.
- All production secrets must be injected via environment variables or
  on-disk files outside the project tree (e.g. `/etc/securing-skies/mqtt_secret`).
- `.env`, `*.secret`, `*.pem`, and `*.key` are listed in `.gitignore` and must remain untracked.
- MQTT usernames in code are acceptable (non-sensitive); passwords must never appear.
- WebXR client credentials are passed exclusively via URL parameters, never hardcoded.

## Branch Protection

- `main` branch is protected: no force pushes, no deletions.
- All changes to `main` must go through a pull request.
- Feature branches should be created from `develop`.

## Dependency Policy

- Pin all Python dependencies to exact versions in `requirements.txt`.
- Frontend dependencies loaded from CDN with integrity hashes where available.
- No third-party MQTT brokers — all data flows through self-hosted Mosquitto with TLS.

## Disclosure Timeline

- Initial response: within 5 business days.
- Fix + release: within 30 days for critical issues, 90 days for moderate.
