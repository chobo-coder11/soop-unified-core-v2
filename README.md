# SOOP Unified Core v2.5.0 Accuracy Ultimate

SOOP(구 아프리카TV)를 위한 **비공식 통합 API / 실시간 프로토콜 코어**입니다. 특정 BJ에 고정되지 않고 유효한 SOOP 스트리머 ID를 동적으로 조회·구독할 수 있습니다.

핵심 목표는 단일 비공식 라이브러리를 감싸는 것이 아니라, **TypeScript Native Core가 SOOP HTTP/WebSocket 프로토콜을 직접 처리**하면서 독립 구현들을 fallback/검증 provider로 사용하고, 장애·불일치·프로토콜 변화까지 관측하는 것입니다.

## 참조 / 보조 provider

- `reindeer002/soop` (`soop-extension`) — Node/TypeScript live/channel/chat
- `getCurrentThread/soopapi` v0.14.0 — Java 25, 광범위 이벤트 디코딩·연결 lifecycle·RAW fixture test
- `zzik2/soop4j` 0.0.3 — Java live/channel/chat/viewer 조회
- `taejeong1126/soop.js` — 브라우저 fallback, archived이므로 기본 OFF

## v2.5.0 Accuracy Ultimate 핵심 고도화

### 정확성 우선 판정

- **Strict SOOP wire parser**: `"0"`/`"1"`, 빈 문자열, null, 숫자 문자열을 JS truthiness에 맡기지 않고 필드 의미대로 정규화합니다.
- Native/reindeer/Java/browser fallback 결과는 consensus 전에 동일 canonicalizer를 통과합니다.
- `online=true`인데 BNO가 없거나 음수 viewer/비정상 chat port 같은 모순 snapshot은 **quarantine**되어 투표에서 제외됩니다.
- `BNO`를 방송 identity로 사용하고 generation을 추적합니다. 방송이 재시작되어 BNO가 바뀌면 이전 channel cache를 폐기합니다.
- `/state`는 `live.BNO`와 `station.broadNo`가 다르면 cache를 우회해 한 번 즉시 재검증하고, 계속 다를 때만 `accuracy.broadcastIdentity.status=mismatch`로 판정합니다.
- 실시간 socket이 붙은 BNO와 현재 live BNO도 `accuracy.realtimeBinding`에서 비교합니다.

### Evidence consensus v2

- provider 개수 자체를 독립 증거로 세지 않습니다. Native/reindeer/soopapi/soop4j처럼 같은 `soop-official-http` upstream family를 공유하면 **family당 한 표 수준으로 cap**합니다.
- 모든 live 핵심 필드(`online`, `BNO`, `CHATNO`, viewer, title, category, password, chat endpoint 등)를 필드별로 합의합니다.
- 각 필드는 `agreement`, `confidence`, `upstreamFamilies`, `temporalSkewMs`, `importance`, conflicting providers를 제공합니다.
- provider 요청 시작/응답 시각을 기록하여 서로 다른 시점의 값을 완전히 같은 샘플처럼 취급하지 않습니다.
- confidence는 통계적 확률이 아니라 독립성·합의·시간차·source 수를 반영한 **evidence score**입니다.

### SOOP WebSocket 정확성

- 기존 validated JOIN profile(`pver=1`, ticket auth)을 기본으로 유지합니다.
- JOIN watchdog timeout 시 reindeer 최신 develop에서 관측한 browser-compatible profile(`pver=2`, `auth_info=NULL`)로 자동 fallback하고 성공 profile을 계속 사용합니다.
- `VIEWPRESET`의 실제 `view_bps`를 JOIN metadata에 반영합니다.
- socket reconnect 시 BNO 변화도 generation change로 추적합니다.
- opcode `127`은 특정 의미를 강제하지 않고 payload shape를 검사해 viewer-presence candidate 또는 unclassified로 보존하여 잘못된 subscriber-status 단정을 제거했습니다.

### 운영 / 검증

- Studio v2.5에서 BNO↔broadNo, socket BNO, generation, handshake profile, 필드별 evidence score를 방송별로 확인합니다.
- 기존 deadline/partial-state/stale 표시/WS gap+resume/hot-path 최적화/flight recorder 기능은 그대로 유지합니다.
- 로컬 compiled regression: **66 pass / 0 fail / 2 WS runtime tests skipped when `ws` runtime is unavailable**. 실제 clean dependency build와 WS integration은 GitHub CI gate에서 검증합니다.

## v2.4.0 P0 핵심 고도화

### 데이터 신뢰도

- **Signal별 Adaptive provider reliability**: live/channel/realtime 성공률·latency를 분리 학습하고, consensus 다수결 자체를 정답으로 학습하지 않음
- **Provider provenance**: implementation / transport / upstream family / independence group 구분
- **Robust consensus**: `confirmed` / `uncertain` / `single-source` 상태 제공
- viewer count는 weighted median + MAD 기반 outlier 제거 후 합의
- provider별 hard deadline + partial success로 하나의 fallback이 멎어도 전체 API가 같이 멎지 않음
- `/state`는 live/channel 부분 장애를 허용하고 `partial/errors`로 원인을 전달
- 짧은 upstream 장애에는 `stale-if-error`로 마지막 정상값을 제한 시간 동안 제공하며 `freshness.state/ageMs/staleReason`을 명시
- 동일 키 동시 요청은 single-flight로 합쳐 upstream fan-out 폭주 방지

### 실시간 연결 / 장애 복구

- Native WebSocket TLS 인증서 검증 **기본 ON** (`SOOP_ALLOW_INSECURE_TLS=false`)
- JOIN watchdog + inbound liveness watchdog
- 실패 원인을 `offline / blocked / auth / protocol / transient`로 분류
- 오프라인은 느린 HTTP 재탐색, 일시 장애는 exponential backoff + jitter
- 인증·프로토콜 오류는 무한 재시도하지 않고 제한 횟수 후 terminal 처리
- 같은 스트리머는 여러 API 사용자가 구독해도 SOOP Native WebSocket을 connection pool에서 공유
- optional `reindeer/soop` realtime mirror와 Native 이벤트를 1:1 occurrence 방식으로 cross-provider dedup
- 같은 provider의 정상 반복 채팅은 보존하며, stable provider event ID 재전송은 중복 제거

### 성능 / Protocol Drift / Flight Recorder

- unknown opcode, parse error, length mismatch, JOIN timeout, liveness timeout을 anomaly로 기록
- 여러 스트림에서 unknown/malformed 비율이 급증하면 Protocol Drift Incident 생성
- drift hot path는 rolling counter/deque 기반으로 변경해 매 이벤트 전체-array scan 제거
- dedup cleanup은 매 이벤트 전체 prune 대신 주기적 cleanup으로 완화
- per-stream RAW는 고정 ring buffer로 유지
- incident 발생 시 관련 스트림의 최근 RAW packet과 anomaly를 **flight recording bundle**로 보존
- RAW/unknown/anomaly/drift 메모리는 모두 상한을 두어 장기 실행 시 무한 증가 방지
- `soopapi`의 RAW fixture 검증 철학을 벤치마킹하여 길이-prefix fixture replay 유틸리티/테스트 추가

### API / 보안

- REST API + WebSocket API + TypeScript SDK
- API key 비교는 constant-time 방식
- IP rate limiter는 unique-client map을 bounded/pruned 상태로 유지
- 요청 body size 제한 및 오류별 HTTP status 매핑
- WebSocket client 수 / subscription 수 / payload / idle / backpressure 제한
- downstream WebSocket heartbeat 및 비응답 client 종료
- WS protocol v4: sequence + explicit `gap` + replay ring + `resume` 지원, subscribe 명령 직렬화로 ref race 방지
- write API는 기본 OFF이며 API key가 함께 설정되어야 활성화
- SOOP 로그인 비밀번호는 저장하지 않음
- write session의 **원본 bearer token은 로그인 응답에서 한 번만 반환**, 서버에는 SHA-256 hash만 저장
- `/v1/auth/sessions`에는 사용할 수 없는 짧은 `sessionRef`만 노출

### Java sidecar

- `soopapi` + `soop4j` 관측을 Virtual Thread에서 병렬 실행
- provider별 실패를 독립 observation으로 반환
- Node가 가진 timeout budget보다 Java 내부 작업이 먼저 끝나도록 budget 전달/상한 적용
- sidecar가 느리거나 죽어도 Node Native Core의 부팅/서비스와 분리

### 운영 / 디버깅

- `/studio` 운영 UI: 연결/무결성/provider/런타임/최근 anomaly를 5초 주기로 확인
- 방송별 connection timeline: connect/JOIN/disconnect/reconnect/terminal/packet 상태 추적
- possible upstream gap 구간을 연결별로 기록
- 런타임 CPU/RSS/heap/event-loop lag metric
- Prometheus counter/gauge/histogram + provider/consensus/reconnect/drift 지표
- 최대 500 ID bulk 조회 + upstream concurrency 제한
- graceful shutdown
- Docker Compose / Windows `start.bat` / `stop.bat`
- GitHub Actions: repository integrity, Node 22/24 build+test, Java 25 sidecar compile, Docker build
- 수동 실제 SOOP smoke workflow
- 수동 real-network soak workflow

## 빠른 실행

### Docker 권장

```bat
copy .env.example .env
start.bat
```

- REST: `http://localhost:8080`
- Studio: `http://localhost:8080/studio`
- WS: `ws://localhost:8080/v1/ws`

### Node 단독

```bash
cp .env.example .env
npm install
npm run build
npm start
```

Java 검증 provider가 필요 없으면:

```env
SOOP_ENABLE_JAVA_SIDECAR=false
```

## 주요 API

```text
GET /livez
GET /readyz
GET /v1/health
GET /v1/live/{streamerId}
GET /v1/channel/{streamerId}
GET /v1/viewers/{streamerId}
GET /v1/state/{streamerId}
GET /v1/live?ids=id1,id2,id3
GET /v1/providers
GET /v1/catalog/events
GET /v1/raw/unknown
GET /v1/diagnostics
GET /v1/diagnostics/drift
GET /v1/diagnostics/anomalies
```

WebSocket subscribe (protocol v4):

```json
{"action":"subscribe","streamers":["streamerA","streamerB"],"events":["CHAT_MESSAGE","donation","MISSION"]}
```

## 캐시 / 디버그

```text
?debug=1    provider raw 포함
?refresh=1  TTL cache 우회
```

## 이벤트 신뢰 경계

이벤트 catalogue는 `stable`, `conditional`, `raw-only`로 분류합니다. opcode가 존재한다는 이유만으로 일반 사용자가 관리자 데이터를 조회할 수 있다고 가정하지 않습니다.

특히 code `52`는 블랙리스트 조회 기능으로 노출하지 않으며 `UNCLASSIFIED_MODERATION_52` / `raw-only` 신호로만 보존합니다.

## 검증 상태

이 배포본은 제작 환경에서 다음을 통과했습니다.

- repository integrity check
- TypeScript strict/full compile (`tsc --noEmit`)
- clean TypeScript build
- compiled JavaScript 회귀 테스트 **66 passed / 0 failed (2 WS runtime integration tests skipped locally because the offline validation workspace lacks the installed `ws` runtime package)**
- Java sidecar API-shape compile 검증
- TLS insecure-default / raw session-token exposure / 비밀정보 로그 패턴 source scan
- ZIP 생성 후 archive integrity 및 금지 파일(`node_modules`, `.env`) 검사

단, 제작 컨테이너에는 외부 DNS, Docker daemon, Java 25/Gradle 의존성 환경이 없어 **실제 SOOP 네트워크 smoke, clean registry install, 실제 JDK25 sidecar dependency build, Docker build는 로컬에서 수행할 수 없습니다.** 이를 과장해 “실서비스 완전 검증”이라고 표기하지 않습니다. GitHub CI + smoke + soak workflow를 production gate로 포함했습니다.

자세한 내용은 `VALIDATION.md`와 `VALIDATION_REPORT.txt`를 확인하세요.

## 문서

- `docs/API.md` — REST / WS / write API
- `docs/ARCHITECTURE.md` — 장애 격리와 데이터 경로
- `docs/BENCHMARK_SOOPAPI.md` — soopapi/reindeer 벤치마킹 반영점
- `VALIDATION.md` — 검증 범위와 한계
- `SECURITY.md` — 인증·권한·RAW 데이터 경계
- `THIRD_PARTY_NOTICES.md` — 참조 provider / 라이선스

## 주의

비공식 API이며 SOOP와 제휴·승인된 프로젝트가 아닙니다. 플랫폼 프로토콜·정책 변경에 따라 동작이 달라질 수 있습니다. 공개 데이터와 정상 인증 흐름을 전제로 하며 접근 제한을 우회하도록 설계하지 않았습니다.
