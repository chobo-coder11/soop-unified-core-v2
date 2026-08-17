# Security policy — v2.3

## Data / privilege boundary

SOOP Unified Core는 공개적으로 접근 가능한 방송/채널 데이터와 정상 인증 흐름을 대상으로 합니다. 접근 제한을 우회하거나 방송자/관리자에게만 노출되는 데이터를 일반 사용자 데이터처럼 추정하지 않습니다.

의미가 검증되지 않은 opcode는 `conditional` 또는 `raw-only`로 분류합니다. Code `52`는 블랙리스트 조회 기능으로 노출하지 않고 `UNCLASSIFIED_MODERATION_52` RAW 신호로만 보존합니다.

## Transport

Native SOOP WebSocket TLS 인증서 검증은 기본 ON입니다. `SOOP_ALLOW_INSECURE_TLS=true`는 진단 목적의 명시적 opt-in이며 production 권장 설정이 아닙니다.

Downstream WebSocket은 max client, max subscription, max payload, idle heartbeat, backpressure 제한을 적용합니다.

## API authentication

`SOOP_API_KEY` 비교는 hash + constant-time 비교를 사용합니다. write API는 기본 OFF이며 `SOOP_ENABLE_WRITE_API=true`와 API key가 동시에 있어야 활성화됩니다.

## Credential / session handling

- 로그인 비밀번호는 login 요청 순간에만 사용하고 저장하지 않습니다.
- SOOP cookie는 프로세스 메모리에만 유지됩니다.
- write session bearer token은 cryptographically random하게 생성합니다.
- 서버 내부에는 bearer token 원문 대신 SHA-256 hash만 저장합니다.
- `/v1/auth/sessions`는 usable token 대신 짧은 `sessionRef`만 표시합니다.
- TTL / logout / process shutdown 시 session 연결과 cookie를 제거합니다.

## Resource limits

- HTTP body size 제한
- bounded IP rate-limit state
- bounded RAW / anomaly / unknown signature / drift state
- bulk concurrency 제한
- WebSocket backpressure drop protection

## Logs / issue reporting

비밀키, bearer session token, AuthTicket/UserTicket, 비밀번호, cookie가 포함된 로그나 이슈를 공개 저장소에 게시하지 마세요.
