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
- 실기기 캡처 테스트 자료와 하드웨어 독립 단위 테스트

예정 기능:

- 조각나거나 합쳐진 XM6 수신 데이터와 응답 확인 처리
- 배터리, 펌웨어와 연결 상태 조회
- ANC·앰비언트 사운드·EQ·DSEE·멀티포인트 제어
- 터치 제어, 자동 전원 끄기 등 기기 설정
- PyQt6 GUI와 시스템 트레이

## 언어 및 주요 기술

- Python 3.11+
- PyQt6 — 데스크톱 GUI
- BlueZ 및 Python `socket` — Bluetooth SDP/RFCOMM 통신
- `pytest` — 단위 테스트와 하드웨어 테스트
- `uv`, Hatchling — 개발 환경과 패키징

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

# 단위 테스트
uv run pytest

# 실기기 테스트
uv run pytest -m hardware
```

`sniff`와 `send`는 프로토콜 개발용 저수준 도구다. 아직 확인되지 않은 명령을
실기기에 전송하면 설정이 바뀔 수 있으므로 캡처와 명령 의미를 확인한 뒤 사용한다.

## 구조

```text
gui/  ──▶  device/  ──▶  messages/  ──▶  protocol/  ──▶  transport/
cli/  ──▶  device/  (통신 테스트 시 protocol/ 직접 접근 가능)
```

각 계층은 바로 아래 계층만 참조한다. `transport/`부터 `device/`까지의 라이브러리
코드는 PyQt6에 의존하지 않는다. 자세한 설계는
[`docs/superpowers/specs/2026-08-15-sonus-driver-design.md`](docs/superpowers/specs/2026-08-15-sonus-driver-design.md)를
참조한다.

## Disclaimer

Sonus는 Sony와 제휴하거나 Sony의 승인·지원을 받는 공식 제품이 아니다. Sony와
WH-1000XM은 각 권리자의 상표다. 이 프로젝트는 상호운용성을 위해 사용자 소유
기기에서 관찰한 통신 데이터 형식만 기록하며 Sony의 소스 코드, 펌웨어, 바이너리 또는
독점 문서를 포함하지 않는다.

헤드셋 설정 변경과 실험적 명령 실행에 따른 책임은 사용자에게 있다. 펌웨어 버전에
따라 동작이 달라질 수 있으므로 자신이 소유하거나 제어 권한이 있는 기기에서만
사용한다.
