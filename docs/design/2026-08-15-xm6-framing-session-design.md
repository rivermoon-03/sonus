# Phase 1.5: XM6 데이터 형식·수신 처리·통신 흐름 교정 설계

## 배경

Phase 1의 데이터 묶음 인코더와 해석기는 XM4/XM5 자료에서 세운 가설이었다.
2026-08-15에
WH-1000XM6 실기기와 RFCOMM 채널 9로 통신한 결과, 연결과 SDP 탐색은
동작했지만 데이터 묶음의 바이트 구성, checksum, 특수 바이트 처리와 수신
단위에 관한 가정이 실제
프로토콜과 달랐다.

실측된 프로토콜 정보 요청과 응답은 다음과 같다.

- 요청: `3e0c000000000200000e3c`
- ACK: `3e010100000000023c`
- 응답: `3e0c010000000801000300303200007b3c`

또한 하나의 데이터 묶음이 여러 `recv()`로 나뉘고, 여러 묶음이 한 `recv()`에
합쳐지며, 요청 처리 중 비동기 알림이 끼어드는 것을 확인했다.

## 목표

- 실측된 XM6 통신 데이터 형식에 맞게 순수 인코더와 해석기를 교정한다.
- 나뉘거나 합쳐져 들어오는 RFCOMM 데이터에서 각 묶음의 경계를 복원한다.
- ACK, 요청 응답과 비동기 알림을 구분하는 동기 세션 계층을 만든다.
- 테스트 CLI의 `probe`와 `send`가 교정된 세션을 사용하도록 연결한다.
- 실제 캡처를 회귀 테스트로 사용해 하드웨어 없이 동작을 검증한다.

## 범위 밖

- 명령별 payload dataclass와 registry
- 전체 capability 협상과 device 상태 캐시
- asyncio API
- PyQt6 GUI
- ANC, EQ 등 설정 명령 구현

이 항목들은 교정된 세션 위에서 Phase 2로 구현한다.

## 데이터 묶음 인코더와 해석기

`src/sonus/protocol/framing.py`는 소켓을 알지 않는 순수 바이트 변환 계층으로
유지한다.

### 데이터 모델

```python
@dataclass(frozen=True)
class Frame:
    data_type: int
    seq: int
    payload: bytes
```

`msg_type`이라는 기존 이름은 실제로 명령 ID가 아니라 전송 data type을
나타내므로 `data_type`으로 교체한다.

### 통신 데이터 형식

```text
START(0x3E)
  data_type(1)
  seq(1)
  payload_length(4, unsigned big-endian)
  payload(N)
  checksum(1)
END(0x3C)
```

- checksum은 `data_type`부터 payload 끝까지의 바이트 합을 modulo 256으로
  계산한다.
- START와 END 사이에서 `0x3C`, `0x3D`, `0x3E`는 각각 `0x3D 0x2C`,
  `0x3D 0x2D`, `0x3D 0x2E`로 escape한다.
- 해석기는 시작·끝 표시, 특수 바이트, 최소 길이, 선언 길이, 불필요한 뒤쪽
  바이트와 checksum을
  엄격히 검증한다.
- `data_type`, `seq`, payload 길이 범위를 encode 전에 검증하고 모든 데이터 형식
  오류를 `FrameFormatError` 또는 `FrameChecksumError`로 통일한다.

## 조각난 수신 데이터 재조립

`FrameStreamDecoder`는 `framing.py`에 두어 데이터 묶음 형식에 관한 지식을 한곳에
모은다.

```python
class FrameStreamDecoder:
    def feed(self, data: bytes) -> list[Frame]: ...
    def reset(self) -> None: ...
```

- 덜 들어온 데이터 묶음은 내부 저장 공간에 보존한다.
- 한 수신 조각에 여러 데이터 묶음이 있으면 순서대로 모두 반환한다.
- START 이전의 잡음은 버린다.
- 완성된 데이터 묶음이 형식 또는 checksum 검증에 실패하면 그 묶음까지만
  소비하고 예외를 발생시킨다. 다음 `feed()`에서 이후 바이트를 계속 처리할 수
  있어야 한다.
- 완성된 END 없이 내부 저장 데이터가 4096바이트를 넘으면 이를 비우고
  `FrameFormatError`를 발생시킨다.

## 세션 계층

`ProtocolSession`은 blocking transport와 `FrameStreamDecoder` 사이에서 송수신
상태를 관리한다. transport 인터페이스는 기존 `send(bytes)`와
`recv(bufsize, timeout)`을 유지한다.

### 공개 인터페이스

```python
class ProtocolSession:
    def request(
        self,
        data_type: int,
        payload: bytes = b"",
        *,
        response_matcher: Callable[[Frame], bool] | None = None,
    ) -> Frame: ...

    def pop_notifications(self) -> list[Frame]: ...
```

### 요청 흐름

1. 현재 sequence로 요청 데이터 묶음을 보낸다.
2. `1 - request_seq` sequence의 ACK를 기다린다.
3. ACK 대기 중 들어온 data frame에는 즉시 `1 - incoming_seq` ACK를 보내고,
   matcher가 선택한 데이터 묶음은 응답 후보로 보존한다. matcher가 없으면 요청을
   보낸 뒤 도착한 첫 data 묶음을 응답 후보로 삼는다. 나머지는 notification
   queue에 넣는다.
4. ACK가 timeout되면 동일한 요청 데이터 묶음을 설정 횟수만큼 재전송한다.
5. ACK를 받은 뒤에는 요청을 재전송하지 않고 응답만 기다린다. 상태 변경 명령의
   중복 실행을 막기 위해서다.
6. ACK와 응답 후보를 모두 확보하면 응답을 반환한다. ACK가 먼저 왔다면 별도의
   응답 timeout 동안 후보를 기다리고, 후보가 먼저 왔다면 ACK가 올 때까지
   보존한다.
7. 성공한 왕복 뒤 sequence를 `0`과 `1` 사이에서 전환한다.

ACK 데이터 묶음의 data type은 `0x01`이며 payload는 비어 있다. 초기 명령과 일반 MDR
명령은 `0x0C`, 두 번째 명령군은 `0x0E`를 사용한다. 상수는 protocol 계층에
이름으로 선언하되, 아직 의미가 확인되지 않은 data type을 막지는 않는다.

### 오류 처리

- ACK 또는 응답 timeout은 단계가 드러나는 `ProtocolTimeoutError`로 변환한다.
- checksum/format 오류는 숨기지 않고 protocol 오류로 전달한다.
- transport 연결 종료는 transport 예외를 보존한다.
- notification queue는 세션 수명 동안 순서를 유지한다.
- `pop_notifications()`는 현재 queue의 복사본을 순서대로 반환하고 queue를
  비운다.

## CLI 변경

- `sonus probe`는 SDP와 RFCOMM 연결 성공 후 `DATA_MDR(0x0C)` payload `0000`을
  보내 프로토콜 정보를 조회한다. 출력에는 channel과 응답 payload hex를 넣는다.
- `sonus send --type`은 명령 ID가 아니라 데이터 묶음의 `data_type`임을 도움말에 명시한다.
  payload는 기존처럼 raw hex를 받는다.
- `sonus sniff`는 상호운용성 분석을 위해 가공하지 않은 수신 조각을 기록한다.
  데이터 재조립은 session/decoder의 책임이며 원본 캡처를 변형하지 않는다.
- CLI 진입점은 예상 가능한 timeout, SDP와 데이터 형식 오류를 짧은 사용자 메시지와
  비정상 종료 코드로 변환하고 raw traceback을 기본 출력하지 않는다.

## 테스트 전략

### 데이터 묶음 단위 테스트

- 실측 protocol-info 요청/ACK/응답 encode·decode
- 4바이트 길이와 modulo-sum checksum
- 세 특수 바이트 escape/unescape
- 범위 오류, 잘린 escape, 길이 불일치, trailing byte와 checksum 오류

### 수신 데이터 재조립 테스트

- 데이터 묶음을 가능한 모든 경계에서 둘로 나눈 입력
- 한 수신 조각에 ACK와 응답이 합쳐진 입력
- 여러 수신 조각으로 나뉜 큰 데이터 묶음
- START 전 잡음, 잘못된 묶음 이후 다시 맞추는 동작과 최대 저장 크기 제한

### 세션 단위 테스트

- 요청 → ACK → 응답 정상 흐름
- ACK와 응답이 한 recv에 합쳐진 흐름
- 응답 전 비동기 알림 수신, 알림 ACK와 queue 보존
- ACK timeout 재시도
- ACK 이후 응답 timeout 시 요청을 재전송하지 않음
- sequence 전환과 수신 데이터 묶음의 ACK sequence

### 통합 확인

- 기본 `pytest`는 하드웨어 없이 항상 통과한다.
- 실기기에서는 `sonus probe`가 channel 9를 찾고 protocol-info 응답 payload
  `0100030030320000`을 출력하는지 확인한다.

## 완료 기준

- 기존 가설 코덱이 실측 형식으로 완전히 교체된다.
- 분할·병합 수신과 비동기 알림이 데이터 손실 없이 처리된다.
- `probe`가 WH-1000XM6에서 protocol-info 왕복에 성공한다.
- 모든 단위 테스트와 실기기 probe가 통과한다.
- `transport/`와 `protocol/`은 PyQt6를 import하지 않는다.
