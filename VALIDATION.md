# Validation record — v2.4.0 P0 Production Hardened

Validation date: 2026-08-17 (Asia/Seoul)

## Passed in this workspace

- Repository integrity script: passed after final tree hardening.
- TypeScript strict/full type-check with TypeScript 5.8.3: passed.
- Clean TypeScript compile to `dist/`: passed.
- Compiled JavaScript unit/regression suite: **46 passed / 0 failed (2 WS runtime integration tests skipped locally because the offline validation workspace lacks the installed `ws` runtime package)**.
- Java sidecar API-shape compile: passed under available JDK 21 using temporary compile-only stubs matching the reviewed current upstream method signatures.
- Source security scan: no production `rejectUnauthorized:false`; auth-session list does not expose bearer session IDs; session storage is hash-only.
- Direct dependency ranges were pinned to exact versions in `package.json` to reduce clean-install drift.

## Regression coverage

The compiled suite covers:

- SOOP packet UTF-8 framing / declared-length validation
- 97-event catalogue and privileged/raw-only policy
- single-flight request coalescing, explicit stale freshness metadata and confidence decay
- robust viewer consensus, field-level channel consensus, `uncertain`, `single-source`, outlier rejection
- signal-isolated adaptive provider reliability without consensus self-penalty
- half-open circuit breaker and adaptive cooldown
- one-to-one cross-provider dedup, repeated identical chat preservation, stable provider event-ID retransmit suppression
- protocol drift multi-stream incident detection
- binary RAW fixture replay / truncation / absurd-length rejection
- bounded RAW unknown-signature registry
- reconnect reason classification and bounded auth/protocol retries
- Prometheus labels/histograms
- API-key constant-time equality behavior
- HTTP error mapping
- bounded/pruned rate-limiter state
- numeric config validation/clamping
- source security invariants
- Java sidecar timeout-budget propagation
- repository/tree integrity


## v2.4 P0 additions validated locally

- provider hard-deadline helper rejects hung calls
- stale fallback reports age/reason
- channel field disagreement produces `uncertain` rather than fixed 0.96 agreement
- reliability penalties are signal-isolated and consensus disagreement alone does not reduce weight
- full clean TypeScript compile followed by compiled regression run: 46 pass / 0 fail; 2 WS runtime integration tests environment-skipped
- repository integrity and security-source tests pass after the P0 changes

The real-network SOOP smoke/long soak limitations below still apply; this artifact does not claim network certification from the offline sandbox.

## soopapi / reindeer benchmark verification

Reviewed `getCurrentThread/soopapi` v0.14.x source included:

- `SOOPConnection` connection/reconnect serialization
- `WebSocketManager` retry/ping/reconnect future lifecycle
- `WebSocketPacketBuilder` UTF-8 packet framing and command builders
- `WebSocketPacketBuilderTest` framing/whisper/Unicode tests
- `RawPacketFixtureTest` binary fixture regression model
- `SOOPLive` authenticated live-detail flow and chat-port normalization

Reviewed `reindeer002/soop` TypeScript chat implementation for handshake/packet shape and raw `CHPT + 1` WebSocket port behavior.

The Native Core keeps its independent implementation; upstream projects are validation/fallback references rather than copied runtime internals.

## Additional hardening found during review

The v2.3 review found and corrected several issues that would not have been visible from the earlier high-level design alone:

1. Cross-provider duplicate pairing could suppress a later legitimate identical chat after a mirror pair. It now consumes duplicate occurrences one-to-one.
2. `/v1/auth/sessions` could have become a bearer-token disclosure point if raw session IDs were listed. Session tokens are now returned once, hash-only at rest, and listings expose a non-usable ref.
3. Protocol drift could be inflated by mirrored duplicate events. Dedup now precedes drift observation.
4. Java sidecar internal provider timeout could outlive the Node caller timeout. The Node-side budget is now propagated and the sidecar clamps work inside that deadline.
5. Rate-limiter, unknown-signature and drift-window structures now have hard memory bounds for long-running operation.
6. Numeric environment configuration is clamped to safe operational ranges rather than accepting negative/absurd values.
7. The manual smoke script now fails on HTTP/JSON/schema errors instead of only printing responses.

## Environment limitations — not claimed as passed

The execution container used for this artifact does **not** have outbound DNS/package-registry access, a Docker daemon, or the required JDK 25 + Gradle dependency environment. Therefore these checks could not be truthfully completed locally:

- clean `npm install` from the public registry
- source-mode `npm test` using a freshly downloaded `tsx`
- actual JDK 25 Gradle/JitPack dependency resolution/build of the sidecar
- Docker image builds
- real SOOP HTTP/WebSocket integration against public streams
- long-duration real-network soak

The TypeScript compile used the available global compiler plus temporary type-only validation shims for external types. Those shims and validation `node_modules` are not included in the release ZIP.

## Production gate included in repository

Before production use, GitHub/network-capable CI should pass all of the following:

1. Node 22 and Node 24 clean dependency install, build, source tests, compiled tests.
2. JDK 25 + Gradle 9.3.1 `java-sidecar` `clean installDist`.
3. Node and Java Docker image builds.
4. Manual real SOOP smoke workflow against a known public streamer.
5. Real-network soak workflow across multiple streamers.
6. Operational observation of forced provider failure/recovery and WebSocket reconnect before declaring long-term production stability.

This artifact is therefore **source/compile/regression hardened and CI-gated**, but it does not claim an impossible real-network certification from an offline build sandbox.
