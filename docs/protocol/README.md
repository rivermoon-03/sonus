<!-- docs/protocol/README.md -->
# 프로토콜 기록

이 디렉터리는 사용자가 소유한 WH-1000XM6에 데이터를 보내고 응답을
확인해 얻은 RFCOMM 제어 프로토콜 관찰 결과를 기록한다. 목적은 기기와의
호환성 확보이다. Sony의 소스 코드, 펌웨어 이미지, 분해한 바이너리는
포함하지 않으며 앞으로도 추가하지 않는다. 여기에는 관찰한 통신 데이터
형식(데이터 묶음의 바이트 구성, 명령 ID, 데이터 모양)만 기술한다. 이는
상호 운용을 위한 리버스 엔지니어링에 해당한다(EU Software Directive
Art. 6, DMCA §1201(f), 대한민국 저작권법 제101조의4 참조).

## 데이터 묶음 구조(XM6 실측, 구현 완료 및 검증)

`src/sonus/protocol/framing.py`는 WH-1000XM6에서 관찰한 데이터 묶음 형식을
구현한다. 처음 구현한 XM4/XM5 기반 가설은 2026-08-15에 WH-1000XM6으로
시험한 결과 실제 형식과 달랐다. 아래에서 확인한 구성은 독립적으로 개발된
[SonyHeadphonesClient MDR 패킷 구현](https://github.com/mos9527/SonyHeadphonesClient/blob/v1-compat/libmdr/src/Command.cpp)과
일치한다.

| 항목 | 크기 | 설명 |
|---|---|---|
| START | 1바이트 | `0x3E` |
| data_type | 1바이트 | `0x01` ACK, `0x0C` DATA_MDR, `0x0E` DATA_MDR_NO2 |
| seq | 1바이트 | 번갈아 쓰는 순서 번호(관찰값 `0` 또는 `1`) |
| length | 4바이트 | payload 길이, 부호 없는 빅 엔디언 |
| payload | N바이트 | 명령별 데이터 |
| checksum | 1바이트 | data_type+seq+length+payload의 바이트 합을 256으로 나눈 나머지 |
| END | 1바이트 | `0x3C` |

특수 바이트 처리: START와 END 사이에 `0x3E`/`0x3C`/`0x3D`가 나오면
`0x3D`와 `(해당 바이트 - 0x10)`으로 바꿔 보낸다.

RFCOMM은 연속된 바이트를 전달한다. 한 번의 `recv()`에 여러 데이터
묶음이 함께 들어올 수도 있고, 하나가 여러 번에 나뉘어 들어올 수도 있다.
따라서 해석기는 `recv()` 결과 하나를 완성된 데이터 하나로 가정하지 않고,
조각난 데이터를 내부에 모아 이어 붙여야 한다.

## 기기 검증 기록

### 2026-08-15 — 교정 구현 회귀 검증

- `sonus probe --mac 58:18:62:1F:C9:CB`가 RFCOMM channel 9를 탐색했다.
- 요청 `3e0c000000000200000e3c`에 ACK와 protocol-info 응답을 수신했다.
- 응답 payload는 `0100030030320000`이며 checksum 검증을 통과했다.
- ACK와 응답의 병합 수신, 큰 알림의 분할 수신을 단위 테스트로 고정했다.

### 2026-08-15 — WH-1000XM6 프로토콜 정보 테스트

- 기기: 저장소에 테스트 MAC 주소로 설정한 사용자 소유 WH-1000XM6.
- SDP 제조사 서비스에서 RFCOMM 채널 9를 확인했다. 실제 응답은 16비트
  DES 길이(`0x36`)와 바깥쪽 서비스 레코드 묶음을 사용했다. 이 동작은
  `test_parse_rfcomm_channel_accepts_real_xm6_two_byte_des_lengths`로 검사한다.
- 연결만 한 상태에서는 12초 동안 수신된 데이터가 없었다.
- 기존 가설인 `sonus send --type 0x01 --payload ""`은 모든 재시도에서
  응답 시간을 초과했다.
- 올바른 프로토콜 정보 요청:
  `3e0c000000000200000e3c` (`DATA_MDR`, seq 0, payload `0000`).
- 기기 ACK: `3e010100000000023c`.
- 기기 응답: `3e0c010000000801000300303200007b3c`. 해석 결과 data type
  `0x0C`, seq 1, payload `0100030030320000`이며 checksum이 올바르다.
- 응답에 ACK를 보낸 뒤 기기가 유효한 `0x0C` 데이터를 추가로 보내,
  통신 중 비동기 알림이 도착할 수 있음을 확인했다.
- 민감 정보를 제거한 원본 데이터는 다음 경로에 저장한다.
  `tests/fixtures/captures/2026-08-15-xm6-protocol-info.jsonl`.
