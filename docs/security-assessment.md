# Security Assessment

## Evidence status

This document records tested behavior, design limitations, and hypotheses that still require live packet-level experiments. It does not claim a vulnerability count in advance.

## Confirmed controls

- Share endpoints reject requests without the configured `X-Party-Token`.
- Request models reject unexpected fields and bound the serialized share size.
- Duplicate enrollment writes are rejected.
- Authentication fails closed when shares are missing or inconsistent.
- The user-facing authentication path opens only the MPyC decision to party 0; it does not reconstruct the enrolled template in the coordinator.

## Design limitations

- The local launcher writes the query embedding to a temporary file shared by local party processes. This is not suitable for remote query confidentiality.
- The HTTP party token is a shared bearer credential and is not mutual TLS or per-party identity.
- Replay protection and request freshness are not implemented for the party control API. The current operations are idempotent or duplicate-protected, but a future authenticated protocol must bind requests to sessions and nonces.
- MPyC provides passive-security guarantees under its configured honest-majority model, not malicious-party security.
- Three processes on one host are not independent trust domains.

## Required experiments

1. Capture loopback traffic during synthetic enrollment/authentication and record whether TLS is enabled in the deployment under test.
2. Replay a captured request and determine whether it changes state or only produces an idempotent response.
3. Modify a response and verify schema/integrity handling.
4. Stop each party during authentication and record fail-closed behavior and latency.

No item above is reported as a confirmed vulnerability until the experiment demonstrates a security-impacting outcome.

## Executed controlled API experiment

Run:

```bash
venv/bin/python scripts/security_experiments.py
```

The in-process experiment uses synthetic data only. Expected observations are:

| Experiment | Observed behavior | Interpretation |
|---|---:|---|
| Unauthenticated retrieval | `401` | Authentication control works |
| Initial create | `204` | State is stored |
| Replay of create | `409` | Duplicate create is rejected |
| Tampered serialized share | `400` | Invalid share is rejected |
| Unexpected request field | `422` | Schema rejects extra input |

A replayed replacement request is intentionally not treated as a confirmed vulnerability by itself: replacement is an authorized state-changing operation. Its security significance depends on the threat model and whether the attacker possesses the valid bearer token.