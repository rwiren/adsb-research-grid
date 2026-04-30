# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 5.0.x   | ✅ Active          |
| < 5.0   | ❌ No longer supported |

## Reporting a Vulnerability

If you discover a security vulnerability in SecuringSkies / ADS-B Research Grid,
please contact the maintainers directly via Signal (`@rwiren.94`) or the
project issue tracker at https://github.com/rwiren/adsb-research-grid.

Please **do not** open public issues for undisclosed security bugs.

## Hardcoded Secrets Policy

- No credentials may be committed to the repository.
- All production secrets must be injected via environment variables or
  on-disk files outside the project tree (e.g. `/etc/securing-skies/mqtt_secret`).
- `.env` and `*.secret` are listed in `.gitignore` and must remain untracked.

## Disclosure Timeline

- Initial response: within 5 business days.
- Fix + release: within 30 days for critical issues, 90 days for moderate.
