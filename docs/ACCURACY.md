# Accuracy model — v2.5

SOOP Unified Core treats accuracy as an evidence problem, not a provider-count problem.

## 1. Strict wire normalization

SOOP endpoints can represent flags and numerics as strings. Values such as `"0"` are not passed through JavaScript `Boolean()` and blank numeric strings are not converted to zero. Every provider result is canonicalized before consensus.

## 2. Snapshot quarantine

Responses that are syntactically successful but internally impossible are excluded from consensus. Examples include `online=true` without BNO, negative viewer counts, invalid channel ports, and mismatched streamer IDs.

## 3. Broadcast identity

`live.BNO` and `station.broadNo` identify the active broadcast. `/state` compares them. A mismatch triggers one cache-bypassing re-read before the result is marked `mismatch`. BNO changes increment an in-memory broadcast generation and invalidate channel cache for that streamer.

The active Native socket also exposes the BNO it was created from. `/state.accuracy.realtimeBinding` compares that socket BNO with the latest live BNO.

## 4. Independent evidence

Native, reindeer, soopapi and soop4j may all ultimately read the same SOOP HTTP family. v2.5 groups provider observations by `upstreamFamily` before final field voting. Multiple wrappers over one upstream can improve internal consistency but cannot count as four independent votes.

## 5. Field evidence

Important live/channel fields are resolved separately. Field metadata contains:

- selected value
- agreement score
- evidence confidence score
- supporting providers
- conflicting providers
- independent upstream-family count
- temporal skew
- importance (`critical/high/medium/low`)

The confidence value is an operational evidence score, not a calibrated probability of truth.

## 6. Temporal skew

Provider observations record request start and response time. Consensus reduces the effective contribution of older samples and exposes `temporalSkewMs` so rapidly changing viewer counts are not interpreted as if every provider sampled the exact same instant.

## 7. WebSocket handshake evidence

The Native connection keeps the previously validated authenticated JOIN profile as default. If JOIN does not complete before the watchdog, the next reconnect tries a browser-compatible profile observed in the current reindeer develop implementation (`pver=2`, `auth_info=NULL`). `VIEWPRESET` bitrate is preserved separately and used as `view_bps`.

## 8. Ambiguous protocol semantics

Opcode 127 is not hard-coded to a single historical interpretation. The decoder checks the payload shape and labels viewer-presence-like data as a candidate while retaining RAW. Ambiguous shapes remain explicitly unclassified.
