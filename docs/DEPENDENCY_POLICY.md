# Dependency Update Policy

This document records dependency constraints that require a deliberate review.

## Netmiko and Paramiko

- Keep `paramiko==5.0.0` as the project's current security baseline.
- Keep `netmiko==4.6.0` until a stable Netmiko release officially supports
  Paramiko 5.
- Do not downgrade Paramiko to 4.x to satisfy a Netmiko dependency constraint.
- Do not force-install an upstream-declared unsupported Netmiko/Paramiko
  combination with `--no-deps`, constraints overrides, or equivalent methods.

Netmiko 4.7.0 requires `paramiko>=3.5.0,<5.0`; it cannot be resolved with this
project's Paramiko pin. Netmiko's maintainers introduced the upper bound after
Paramiko 5 removed SHA-1 support and related workarounds, which can affect
network-device compatibility.

The detailed decision record and re-evaluation criteria are tracked in
[issue #181](https://github.com/icecake0141/nw-diff/issues/181).

## Dependency PR checklist

Before merging a dependency-update pull request:

1. Confirm that all direct dependency pins and upstream package metadata can be
   resolved together.
2. Check open dependency-compatibility issues, including issue #181 for any
   Netmiko or Paramiko change.
3. Preserve security-pinned dependency versions unless an approved replacement
   maintains or improves the security baseline.
4. Run the applicable test suite, static analysis, `pip-audit`, and Docker
   integration checks.
5. For SSH-library updates, run connection smoke tests against the supported
   target devices, including any devices that use legacy SSH algorithms.
