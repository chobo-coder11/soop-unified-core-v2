# Validation record — v2.5.0 Accuracy Ultimate

Validation date: 2026-08-23 (Asia/Seoul)

## Local validation

- Repository integrity: PASS after v2.5 critical-file expansion.
- Accuracy-only pure TypeScript modules (`normalize`, `consensus`, broadcast identity/generation, snapshot validation, handshake): strict compile PASS.
- Compiled regression suite: **66 passed / 0 failed / 2 WS runtime integration tests environment-skipped** because the local workspace does not contain the installed `ws` runtime package.
- Studio browser JavaScript extraction: `node --check` PASS.

## New v2.5 regression coverage

- string `"0"` is false, not truthy; blank numerics remain unknown instead of becoming zero
- zero is still preserved when zero is a valid viewer/favorite/subscriber count
- VIEWPRESET bitrate is kept separately from broadcast BPS
- fallback provider snapshots are runtime-canonicalized before consensus
- online-without-BNO, negative viewers and invalid ports are quarantined before voting
- correlated implementations sharing one upstream family cannot inflate independent confidence
- independent BNO disagreement produces an uncertain result
- BNO generation increments only when broadcast identity changes
- BNO ↔ station broadNo mismatch is represented explicitly
- both authenticated JOIN profiles produce expected metadata; fallback profile is not the default
- opcode 127 viewer-shaped payload is a candidate and ambiguous payload remains unclassified

## Existing v2.4 coverage retained

Provider deadlines, partial state, stale freshness, signal-isolated adaptive reliability, circuit breaker recovery, dedup occurrence matching, protocol drift, RAW fixture replay, reconnect classification, metrics, security source invariants, rate-limit bounds, WebSocket gap/replay/resume and connection diagnostics remain covered by the existing suite.

## Clean-build gate

This workspace cannot complete a clean npm registry install. The full project compiler therefore sees missing external `@types/node`, `@types/ws` and `ws` packages locally even though v2.5 modules themselves pass targeted strict compilation. GitHub CI is the authoritative clean environment gate and must pass Node 22 and Node 24 build/source/compiled tests before the v2.5 commit is promoted to `main`.

## Real-network limitations

Even a green CI build does not prove long-duration SOOP behavior. The included smoke/soak workflows remain necessary for real public-stream verification, especially JOIN fallback behavior and protocol-drift monitoring.

No claim is made that the heuristic evidence confidence score is a calibrated probability.
