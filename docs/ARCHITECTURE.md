# SOOP Unified Core v2.4 Architecture

```text
                           SOOP
                  HTTP              WebSocket
                   |                    |
          +--------+--------+     +-----+----------------+
          | Native HTTP Core|     | Native Protocol Core |
          +--------+--------+     +----------+-----------+
                   |                         |
          fallback observations       optional RAW mirror
        +----------+----------+              |
        |          |          |        reindeer/soop
     reindeer   Java sidecar  soop.js        |
                   |   |                     |
              soopapi soop4j                 |
        +----------+----------+--------------+
                   |
           Provider Registry
      breaker + provenance + health
                   |
          Adaptive Reliability
       success / latency / disagreement
                   |
            Robust Consensus
   confirmed / uncertain / single-source
                   |
     Single-flight + stale-if-error cache
                   |
         +---------+----------+
         |                    |
       REST API             WS Hub
                              |
                      Connection Pool
                              |
             occurrence-safe cross-provider dedup
                              |
                    Protocol Drift Detector
                              |
                 RAW / Anomaly Flight Recorder
```

## Failure isolation

- Native HTTP 실패가 다른 provider의 observation 반환을 막지 않습니다.
- provider마다 독립 circuit breaker가 있고 `healthy -> degraded -> open -> half-open` 상태를 가집니다.
- half-open에서는 단 하나의 trial만 허용합니다.
- 반복 reopen은 cooldown을 증가시키고 성공 시 reset합니다.
- Java sidecar가 죽어도 Node Native Core는 독립적으로 부팅/서비스합니다.
- Java sidecar의 soopapi/soop4j는 Virtual Thread에서 병렬 관측하며 Node timeout budget 안에서 종료하도록 제한됩니다.
- SOOP realtime 실패는 `offline / blocked / auth / protocol / transient`로 분류합니다.
- password-protected/blocked 방송은 terminal이며 우회하지 않습니다.
- offline은 WebSocket hammering 대신 느린 live-detail re-probe를 사용합니다.
- auth/protocol 오류는 무한 재시도하지 않습니다.

## Realtime correctness

- raw SOOP `CHPT`는 Native/reindeer/soopapi 구현 대조 결과 chat WebSocket에서 `CHPT + 1`을 사용합니다.
- JOIN 완료 watchdog과 inbound liveness watchdog이 zombie socket을 제거합니다.
- 동일 스트리머의 여러 downstream 구독은 Native connection 하나를 공유합니다.
- optional mirror의 동일 이벤트는 one-to-one occurrence matching으로 제거합니다.
- 같은 provider의 실제 반복 채팅은 텍스트가 같다는 이유만으로 삭제하지 않습니다.
- stable `providerEventId`가 있는 경우 동일 ID 재전송은 확정 중복으로 제거합니다.

## Data reliability

- provider weight는 고정 우선순위만 사용하지 않고 최근 EWMA 상태에 따라 자동 조정됩니다.
- online/offline 표가 근소하면 `uncertain`을 반환합니다.
- usable provider가 하나면 `single-source`로 명시하고 confidence를 제한합니다.
- viewer count는 robust weighted median을 사용하고 극단 outlier를 제거합니다.
- 구현체 수와 upstream family 다양성을 confidence에 반영하여 단순히 “provider 4개”를 4개의 완전 독립 출처로 과장하지 않습니다.

## Protocol drift pipeline

```text
accepted realtime event / protocol anomaly
                 |
         sliding time window
                 |
  unknown ratio + malformed burst + streams
                 |
        ProtocolDriftIncident
                 |
        RAW flight recording
    packets + anomalies + signatures
```

미러 중복은 drift detector에 들어가기 전에 제거되어 duplicate provider 때문에 이상 비율이 부풀지 않습니다. event/anomaly/unknown-signature 저장소는 모두 메모리 상한이 있습니다.

## Downstream API hardening

- API key: hash + `timingSafeEqual`
- rate-limit map: expiration prune + hard cap
- request body max size
- WS max clients / max subscriptions / max payload / idle timeout
- transport ping/pong heartbeat
- WS bufferedAmount backpressure drop
- auth session token hash-only storage
- TLS verification secure-by-default

## Trust boundary

프로토콜 opcode 존재와 일반 사용자의 관리자 데이터 접근 가능성은 별개입니다. Unified Core는 `stable`, `conditional`, `raw-only`로 구분하며 불명확하거나 권한 의존적인 패킷을 고수준 의미로 승격하지 않습니다. Code `52`는 `UNCLASSIFIED_MODERATION_52` RAW 신호로만 유지합니다.
