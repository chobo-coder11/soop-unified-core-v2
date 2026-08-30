# Validation record — v2.6.0 Accuracy Hardened

Validation date: 2026-08-31 (Asia/Seoul)

## CI authority

The authoritative promotion gate is GitHub CI on the exact PR head. Main is not promoted until all of the following pass:

- repository integrity
- Node 22 build + source tests + compiled tests
- Node 24 build + source tests + compiled tests
- Java 25 sidecar compile
- Node Docker image build
- Java sidecar Docker image build

## New v2.6 regression coverage

- delimiter-free opcode 121 JSON is parsed directly from packet payload
- field-delimited opcode 121 JSON remains compatible
- `CHALLENGE_GIFT` becomes `CHALLENGE_MISSION_GIFTED` / `challenge_mission`
- observed opcode-121 `GIFT` becomes `BATTLE_MISSION_GIFTED` / `battle_mission`
- snake_case and camelCase donor/count aliases normalize consistently
- JSON Unicode escapes decode to the real nickname
- unknown opcode-121 subtype stays `MISSION` / `notification` and is never guessed as a donation
- malformed opcode-121 JSON becomes `raw-only` and cannot create a false donation
- opcode 125 settlement JSON is preserved without invented challenge/battle semantics
- specialized mission events still match legacy WebSocket `MISSION` subscriptions
- specialized mission events also match specialized type, numeric opcode and `donation` category filters

## Existing accuracy coverage retained

- strict boolean/number/BNO normalization
- zero-value preservation where zero is legitimate
- VIEWPRESET bitrate handling
- provider snapshot canonicalization before consensus
- impossible-snapshot quarantine
- upstream-family evidence independence
- BNO broadcast generation and BNO ↔ broadNo identity checks
- socket BNO ↔ current live BNO binding diagnostics
- dual authenticated JOIN profiles and watchdog fallback
- opcode 127 shape-aware ambiguity preservation
- provider deadlines / partial state / stale freshness
- adaptive reliability / circuit breaker recovery
- occurrence-safe dedup
- protocol drift + RAW fixture replay
- reconnect classification
- metrics, security invariants, rate-limit bounds
- downstream WebSocket gap/replay/resume and connection diagnostics

## Real-network limitations

A green deterministic CI run proves repository/build/regression integrity, not permanent compatibility with an external platform. SOOP can change wire semantics or availability after the release. Real public-stream smoke/soak workflows remain necessary for long-duration verification.

For this reason the core does not claim an impossible "0% error rate". Its accuracy policy is instead:

1. normalize only verified semantics,
2. preserve unknown data rather than guess,
3. expose RAW/diagnostic evidence,
4. convert observed wire behavior into regression fixtures,
5. maintain backward compatibility for existing API consumers.

Evidence `confidence` values are operational scores, not calibrated statistical probabilities.
