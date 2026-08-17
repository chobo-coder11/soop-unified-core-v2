# soopapi / reindeer benchmark notes — Unified Core v2.3

Benchmark reference:

- `getCurrentThread/soopapi` v0.14.x source line
- `reindeer002/soop` current TypeScript chat implementation reviewed during v2.3 hardening

목표는 코드를 복사하는 것이 아니라 장기 실행 integration core에 유용한 **검증 가능한 설계 패턴**을 흡수하는 것이었습니다.

## soopapi에서 벤치마킹한 부분

- 명시적인 connection lifecycle / reconnect 상태 관리
- 중복 reconnect future를 공유하여 동시 재접속 경쟁을 줄이는 사고방식
- exponential retry + ping lifecycle
- anonymous read / authenticated write 분리
- CONNECT / JOIN / CHAT / WHISPER / ENTER_INFO packet builder 분리
- UTF-8 byte length 기반 6자리 packet length 테스트
- multi-stream connection 관리
- broad event decoder + RAW binary fixture replay test 철학
- auth cookie를 사용하는 authenticated live-detail 흐름

## v2.3에서 더 강화한 부분

1. Node Native Core를 primary implementation으로 유지하고 Java를 hard dependency로 만들지 않았습니다.
2. retry는 단순 횟수가 아니라 offline/blocked/auth/protocol/transient 원인별 정책을 적용합니다.
3. provider별 성공률·latency·불일치를 future weight에 반영합니다.
4. consensus가 애매하면 강제 true/false 대신 `uncertain`을 반환합니다.
5. RAW fixture replay를 TypeScript protocol regression test에도 추가했습니다.
6. Java sidecar 내부 soopapi/soop4j는 병렬 관측하며 Node 요청 budget보다 먼저 끝나도록 timeout을 전달합니다.
7. unknown/malformed burst는 drift detector와 flight recorder로 연결됩니다.
8. cross-provider realtime dedup은 occurrence를 1:1로 소비하여 실제 반복 채팅을 보존합니다.
9. TLS insecure mode는 기본값이 아니라 명시적 debug opt-in입니다.

## Chat port 교차검증

`reindeer002/soop`은 raw `CHANNEL.CHPT + 1`로 WebSocket URL을 구성합니다. 최신 검토한 `soopapi`도 HTTP 응답의 raw `CHPT`를 LiveDetail로 변환할 때 `+1`한 값을 chat port로 저장한 뒤 WebSocketManager가 그 값을 사용합니다. 따라서 Native Core의 raw `CHPT + 1` 방식은 두 독립 구현과 일치합니다.

## 의도적으로 복사하지 않은 부분

- 특정 provider 구현 내부에 강결합되는 구조
- 일반 사용자 권한에서 검증되지 않은 관리 이벤트 의미
- 일시 장애 후 영구적으로 서비스를 멈추게 하는 단순 retry 정책
- TLS 인증서 검증 비활성화를 production 기본값으로 두는 방식

Java sidecar는 계속 optional입니다. sidecar 장애가 Node Native/reindeer/soop.js observation을 막아서는 안 됩니다.
