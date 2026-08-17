# Sonus

Sony WH-1000XM6를 Linux에서 제어하기 위한 순수 Python 드라이버와 PyQt6
데스크톱 앱 프로젝트다.

## 목적

Sony Sound Connect 앱 없이도 Linux에서 헤드셋 상태를 확인하고 ANC, 앰비언트
사운드, 이퀄라이저와 기기 설정을 제어하는 것이 목표다. 공개 문서가 없는 XM6
제어 프로토콜은 사용자 소유 기기에서 관찰한 결과를 바탕으로 구현한다.

## 기능

현재 구현:

- BlueZ SDP를 통한 Sony vendor RFCOMM 채널 탐색
- RFCOMM 연결과 지수 백오프 재시도
- 통신 테스트용 `probe`, `sniff`, `send` CLI
- XM6 MDR 데이터 묶음 생성·해석과 조각난 수신 데이터 재조립
- ACK, 요청 응답과 비동기 알림 세션 처리
- 모델, 펌웨어, 배터리, 코덱과 주요 XM6 설정 조회
- `status`, `settings`, `get`, `set`, `discover` 통합 CLI
- 안전 등급 기반 쓰기 차단과 DSEE 설정 자동 복원 검증
- 실기기 캡처 테스트 자료와 하드웨어 독립 단위 테스트

확장 예정:

- ANC·앰비언트 사운드·EQ·멀티포인트 쓰기 제어
- 터치 제어, 자동 전원 끄기 등 기기 설정
- PyQt6 GUI와 시스템 트레이

## 언어 및 주요 기술

- Python 3.11+
- 표준 라이브러리 `socket`, `argparse`, `dataclasses` — 통신·CLI·자료형
- BlueZ 및 Python `socket` — Bluetooth SDP/RFCOMM 통신
- `pytest` — 단위 테스트와 하드웨어 테스트
- `uv`, Hatchling — 개발 환경과 패키징

PyQt6 GUI는 다음 단계에서 추가할 예정이며 현재 런타임 의존성은 없다.

## 요구 사항

- Linux와 BlueZ
- Python 3.11 이상
- `uv`
- BlueZ에 페어링되고 신뢰 처리된 WH-1000XM6

## 실행 방법

```bash
git clone <repository-url> sonus
cd sonus
uv sync

# RFCOMM 채널 탐색과 연결 확인
uv run sonus probe --mac <HEADSET_MAC>

# 채널을 알고 있을 때 상태와 모든 확인된 설정 조회
uv run sonus status --mac <HEADSET_MAC> --channel 9
uv run sonus settings --mac <HEADSET_MAC> --channel 9 --json

# 항목 하나 조회 또는 검증된 가역 설정 변경
uv run sonus get --mac <HEADSET_MAC> --channel 9 battery
uv run sonus set --mac <HEADSET_MAC> --channel 9 dsee auto

# 채널 생략 시 Sony 서비스 SDP로 자동 탐색
uv run sonus status --mac <HEADSET_MAC>

# 단위 테스트
uv run pytest

# 실기기 테스트
uv run pytest -m hardware
```

정상 연결 시 RFCOMM channel과 protocol-info payload가 출력된다. 현재 정식 쓰기는
실기기에서 변경과 원상 복원을 확인한 DSEE만 허용한다.

`sniff`와 `send`는 프로토콜 개발용 저수준 도구다. 아직 확인되지 않은 명령을
실기기에 전송하면 설정이 바뀔 수 있으므로 캡처와 명령 의미를 확인한 뒤 사용한다.

## 구조

```text
gui/  ──▶  device/  ──▶  messages/  ──▶  protocol/  ──▶  transport/
cli/  ──▶  device/  (통신 테스트 시 protocol/ 직접 접근 가능)
```

각 계층은 바로 아래 계층만 참조한다. `transport/`부터 `device/`까지의 라이브러리
코드는 PyQt6에 의존하지 않는다. 자세한 설계는
[`docs/design/2026-08-15-sonus-driver-design.md`](docs/design/2026-08-15-sonus-driver-design.md)와
[`XM6 상태·설정 API와 CLI 설계`](docs/design/2026-08-16-xm6-device-api-cli-design.md)를
참조한다.

## Disclaimer

Sonus는 Sony와 제휴하거나 Sony의 승인·지원을 받는 공식 제품이 아니다. Sony와
WH-1000XM은 각 권리자의 상표다. 이 프로젝트는 상호운용성을 위해 사용자 소유
기기에서 관찰한 통신 데이터 형식만 기록하며 Sony의 소스 코드, 펌웨어, 바이너리 또는
독점 문서를 포함하지 않는다.

헤드셋 설정 변경과 실험적 명령 실행에 따른 책임은 사용자에게 있다. 펌웨어 버전에
따라 동작이 달라질 수 있으므로 자신이 소유하거나 제어 권한이 있는 기기에서만
사용한다.

Sonus는 사용자 소유 기기와 직접 통신한 블랙박스 관찰을 상호운용성 목적으로
사용한다. Sony 앱·펌웨어·바이너리를 역컴파일하거나 포함하지 않고 인증·보호 장치를
우회하지 않는다. 전원 끄기, 초기화, 페어링 관리와 펌웨어 명령은 안전 정책상
구현하지 않는다. 이 설명은 법률 자문이 아니며 자세한 범위와 근거 링크는
[`docs/protocol/README.md`](docs/protocol/README.md#관찰-및-법적-경계)에 정리한다.
