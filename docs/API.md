# SOOP Unified Core v2.6.0 API

Base URL: `http://localhost:8080`

`SOOP_API_KEY`가 설정된 경우 `X-API-Key` 또는 `Authorization: Bearer`가 필요합니다. 키 비교는 constant-time 방식으로 처리됩니다.

## Health / Studio / provider / metrics

- `GET /livez` — 인증 없이 프로세스 liveness
- `GET /readyz` — 인증 없이 readiness
- `GET /studio` — 내부 운영 UI

- `GET /v1/health`
- `GET /v1/providers`
- `GET /v1/metrics`
- `GET /metrics` — Prometheus text
- `GET /v1/catalog/events`

`/v1/providers`는 circuit state와 signal별 adaptive reliability(`dynamicWeight`, success rate, verified error rate, latency)를 함께 제공합니다.

## Live / channel

- `GET /v1/live/{streamerId}`
- `GET /v1/channel/{streamerId}`
- `GET /v1/viewers/{streamerId}`
- `GET /v1/state/{streamerId}`

옵션:

```text
?debug=1    provider RAW observation 포함
?refresh=1  short TTL cache 우회
```

### Bulk

최대 500 ID:

- `GET /v1/live?ids=id1,id2,id3`
- `GET /v1/channel?ids=id1,id2,id3`
- `GET /v1/viewers?ids=id1,id2,id3`
- `GET /v1/state?ids=id1,id2,id3`

동일 ID 동시 요청은 single-flight로 합쳐지고, `SOOP_BATCH_CONCURRENCY`로 upstream 동시성을 제한합니다.

## Consensus metadata

Live/viewer 응답에는 다음 metadata가 포함됩니다.

- `status`: `confirmed` | `uncertain` | `single-source`
- `onlineState`: `online` | `offline` | `uncertain`
- `agreement`, `totalWeight`, `winningWeight`
- `sourceCount`, `implementationGroups`, `upstreamFamilies`
- `outlierProviders`
- `fields` — 필드별 value/agreement/sources/conflictingProviders
- `freshness` — `fresh|stale`, `ageMs`, `staleReason`

provider 표가 충분히 갈리면 true/false를 강제로 만들지 않고 `uncertain`으로 반환합니다.

## Realtime WebSocket

Endpoint: `ws://host:8080/v1/ws`

서버 hello protocol은 `4`입니다. downstream WS에는 client cap, max payload, idle heartbeat, subscription cap, backpressure 보호가 적용됩니다.

Subscribe:

```json
{"action":"subscribe","streamers":["id1","id2"],"events":["CHAT_MESSAGE","donation",121]}
```

Unsubscribe:

```json
{"action":"unsubscribe","streamers":["id1"]}
```

Replay/resume:

```json
{"action":"resume","fromSeq":184291}
```

이벤트의 `seq`는 서버 전체 global sequence입니다. 다른 방송/필터된 이벤트 때문에 숫자가 건너뛸 수 있으므로 **숫자 점프 자체를 누락으로 판단하면 안 됩니다.** 실제 downstream drop은 서버가 `type: "gap"` 메시지로 명시합니다. `resume`은 최근 `SOOP_WS_REPLAY_EVENTS` 범위에서 현재 subscription/filter에 맞는 이벤트를 재전송합니다.

Other actions: `list`, `ping`.

동일 스트리머를 여러 API client가 구독해도 내부 Native SOOP WebSocket은 connection pool에서 공유됩니다. subscribe/unsubscribe 변경은 client별 queue로 직렬화됩니다.

### Mission events — v2.6

Opcode `121`은 단순한 "도전미션 코드"로 고정하지 않고 **mission envelope**로 처리합니다. 실제 관측된 JSON `type`에 따라 다음처럼 canonical event로 정규화됩니다.

```text
121 + type=CHALLENGE_GIFT -> type=CHALLENGE_MISSION_GIFTED
                              category=donation
                              donation.kind=challenge_mission

121 + type=GIFT           -> type=BATTLE_MISSION_GIFTED
                              category=donation
                              donation.kind=battle_mission
```

후원자와 수량이 payload에 존재하면 `user.id`, `user.nickname`, `donation.amount`로 정규화합니다. `user_id/userId`, `user_nick/userNickname`, `gift_count/count` 변형을 허용하며 `chno`, `key`, `title`, relay/status/uuid와 파싱된 원본 mission object는 `payload`에 보존합니다.

알 수 없는 121 subtype은 **후원으로 추측하지 않습니다.** 기존 `MISSION` / `notification` 의미를 유지하고 원본 데이터를 보존합니다. JSON 파싱 자체가 실패한 경우 `raw-only`로 낮춰 false-positive를 막습니다.

기존 클라이언트 호환을 위해 specialized mission event도 다음 모든 필터에 매칭됩니다.

```text
MISSION
CHALLENGE_MISSION_GIFTED / BATTLE_MISSION_GIFTED
121
donation
```

Opcode `125` settlement JSON은 보존하지만, 확인되지 않은 discriminator를 만들어 도전/대결 settlement로 추측 분류하지 않습니다.

## Connection pinning

- `POST /v1/streams/{streamerId}` — subscriber가 없어도 연결 유지
- `DELETE /v1/streams/{streamerId}` — pin 해제
- `GET /v1/streams`

## RAW / diagnostics

- `GET /v1/raw/{streamerId}?limit=100`
- `GET /v1/raw/unknown`
- `GET /v1/diagnostics`
- `GET /v1/diagnostics/drift`
- `GET /v1/diagnostics/anomalies?limit=100`

`/v1/diagnostics/drift`에는 drift snapshot, incidents, 최근 `flightRecordings`가 포함됩니다. Flight recording은 incident 당시 관련 스트림의 최근 RAW packet과 anomaly를 묶은 in-memory 진단 자료입니다.

## Authenticated write API — optional / default OFF

다음 두 조건이 모두 필요합니다.

```env
SOOP_ENABLE_WRITE_API=true
SOOP_API_KEY=a-long-random-secret
```

Login:

```http
POST /v1/auth/login
Content-Type: application/json

{"userId":"my_soop_id","password":"..."}
```

응답의 `sessionId`는 bearer secret입니다. **로그인 시 한 번만 반환되며 서버에는 token hash만 저장됩니다.**

Send chat:

```http
POST /v1/chat/{streamerId}/send
{"sessionId":"...","message":"hello"}
```

Send whisper:

```http
POST /v1/chat/{streamerId}/whisper
{"sessionId":"...","targetId":"target_login_id","message":"hello"}
```

Logout:

```http
POST /v1/auth/logout
{"sessionId":"..."}
```

Session diagnostics:

```text
GET /v1/auth/sessions
```

여기에는 실제 bearer token이 아닌 `sessionRef`, userId, expiry, 연결 스트림만 표시됩니다.

## Event support levels

- `stable` — 일반적인 공개/익명 흐름에서도 의미와 필드가 비교적 검증됨
- `conditional` — 인증/권한/방송 상태 또는 관측된 wire subtype 등에 따라 가시성·세부 의미가 달라질 수 있음
- `raw-only` — 의미를 과장하지 않고 연구용 RAW 신호로만 유지

필터:

```text
GET /v1/catalog/events?support=stable
GET /v1/catalog/events?support=conditional
GET /v1/catalog/events?support=raw-only
```

Code `52`는 블랙리스트 조회 API가 아니며 `UNCLASSIFIED_MODERATION_52` / `raw-only`로만 노출합니다.

## v2.5+ accuracy metadata

`GET /v1/live/{id}` and `GET /v1/channel/{id}` expose field evidence under `consensus.fields`.

Each field can include `agreement`, `confidence`, `sources`, `conflictingProviders`, `upstreamFamilies`, `temporalSkewMs`, and `importance`.

`confidence` is an evidence score, not a statistical probability.

`GET /v1/state/{id}` additionally returns:

```json
{
  "accuracy": {
    "broadcastIdentity": {
      "status": "matched",
      "liveBno": "123456",
      "channelBroadNo": "123456",
      "generation": 2,
      "revalidated": false,
      "confidence": 0.97
    },
    "realtimeBinding": {
      "status": "matched",
      "socketBno": "123456",
      "liveBno": "123456"
    }
  }
}
```

A persistent `broadcastIdentity.status=mismatch` means live and station endpoints still identify different broadcasts after one cache-bypassing re-read. Callers should not merge those snapshots as if they belong to the same broadcast.
