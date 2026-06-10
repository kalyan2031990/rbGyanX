# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |

## Reporting a vulnerability

Email the maintainer via GitHub issues (private security advisory preferred) at
[github.com/kalyan2031990/rbGyanX/security](https://github.com/kalyan2031990/rbGyanX/security).

Please include: affected version, reproduction steps, and impact assessment.

## Scope

- `engine/`, `rbgyanx/`, installer scripts
- Out of scope: third-party TPS exports, local PHI in `input_folders/`

## CI checks

- `bandit` on engine core and app logic
- `pip-audit` on locked dependencies (see `requirements-lock.txt`)
