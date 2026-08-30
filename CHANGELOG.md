# Changelog

## 2.6.0 Mission Accuracy Hardened

- Reworked opcode 121 as a mission envelope instead of a challenge-only event.
- Added delimiter-free JSON parsing for observed SOOP mission payloads while retaining field-delimited compatibility.
- Normalized observed `CHALLENGE_GIFT` as `CHALLENGE_MISSION_GIFTED` / `challenge_mission`.
- Normalized observed opcode-121 `GIFT` as `BATTLE_MISSION_GIFTED` / `battle_mission`.
- Preserved unknown mission subtypes as notification events instead of guessing a donation type.
- Added mission metadata preservation for `chno`, `key`, `title`, relay/status/uuid fields and raw parsed data.
- Added tolerant snake_case/camelCase donor/count aliases and verified JSON Unicode nickname decoding.
- Improved opcode 125 settlement JSON preservation without guessing unverified challenge/battle settlement semantics.
- Kept legacy WebSocket `MISSION` subscription filters compatible with specialized mission event types.
- Added regression coverage for challenge, battle, delimiter variants, Unicode, aliases, unknown subtypes, malformed payloads, settlement parsing and filter compatibility.

## 2.5.0 Accuracy Ultimate

- Added strict SOOP wire normalization for string booleans, blank numerics, BNOs and VIEWPRESET data.
- Added runtime snapshot canonicalization and impossible-snapshot quarantine before consensus.
- Added upstream-family evidence voting so correlated wrappers cannot inflate independent confidence.
- Extended field-level consensus to live identity, metadata, realtime endpoint and numeric fields with temporal-skew/evidence metadata.
- Added BNO generation tracking, live BNO ↔ station broadNo cross-validation and one-shot mismatch revalidation.
- Added realtime socket-BNO binding visibility in `/state` and Studio.
- Added dual authenticated JOIN profiles with watchdog-driven fallback and VIEWPRESET-aware view_bps.
- Reclassified opcode 127 decoding as shape-checked viewer-presence candidate/unclassified instead of a hard subscriber-status assumption.
- Studio now exposes broadcast identity, generation, handshake profile and per-field evidence.
- Accuracy/regression suite expanded to 66 local compiled passes (2 WS runtime tests remain environment-skipped without installed ws).


## 2.4.0 P0 Production Hardened

- Added hard provider deadlines and partial-success collection so one hung fallback cannot block the whole request.
- `/state` now survives live/channel partial failure and reports structured errors.
- Stale-if-error responses now expose freshness age/reason and confidence is reduced for stale data.
- Reworked adaptive reliability by signal and removed self-confirming consensus disagreement penalties.
- Added field-level channel consensus instead of fixed pseudo-agreement.
- WebSocket protocol v4 adds explicit gap notifications, replay/resume, serialized subscription mutations and close-during-acquire leak protection.
- Optimized protocol drift rolling windows, dedup cleanup cadence and RAW per-stream storage hot paths.
- Added connection timeline diagnostics, possible-gap history and runtime CPU/memory/event-loop metrics.
- Added `/studio` operator UI and unauthenticated `/livez`/`/readyz`; Docker healthcheck now uses `/livez`.
- Upgraded soak runner to exercise REST + realtime WS and explicit gap/drop metrics.
- Regression suite expanded to 44 compiled tests.

## 2.3.0 Verified Hardened

- Reworked realtime dedup into one-to-one occurrence matching; stable provider event IDs suppress retransmits while legitimate repeated same-provider chat remains visible.
- Added RAW fixture replay utilities inspired by soopapi's packet fixture regression strategy.
- Added Protocol Drift flight recording bundles and bounded drift/anomaly/unknown-signature memory.
- Added SHA-256 hash-only write-session token storage; session listing exposes non-usable refs only.
- Added constant-time API-key comparison.
- Hardened downstream WebSocket server with client cap, payload cap, heartbeat/idle termination, backpressure protection and upgrade rate limiting.
- Bounded/pruned IP rate-limiter memory.
- Added validated/clamped numeric configuration ranges.
- Added reason-aware bounded auth/protocol reconnect terminal handling.
- Parallelized Java sidecar soopapi/soop4j observations with Virtual Threads.
- Aligned Java provider work with Node timeout budget so a slow sidecar provider cannot routinely outlive the caller.
- Added real-network soak workflow and soak runner.
- Expanded regression suite to 37 compiled tests.
- Raised Node runtime baseline to Node 22 and CI matrix to Node 22/24.
- Pinned direct package versions for more repeatable clean installs.

## 2.2.0 Hardened

- Added adaptive provider reliability based on EWMA success, latency and disagreement.
- Added provider provenance and diversity-aware consensus metadata.
- Added `uncertain` and `single-source` consensus states.
- Added robust viewer outlier rejection.
- Reworked circuit breaker with half-open single probe and adaptive cooldown.
- Enabled WebSocket TLS certificate verification by default.
- Added reason-aware reconnect policy and offline polling.
- Added JOIN and liveness watchdog diagnostics.
- Reworked realtime dedup to suppress cross-provider mirrors without deleting real same-provider repeated chat.
- Added protocol drift detector, anomaly ring and incident flight recorder.
- Expanded Prometheus metrics with labels and histograms.
- Added stale-if-error caching and diagnostics endpoints.

## 2.1.1

- Java sidecar async API / CI fixes.
