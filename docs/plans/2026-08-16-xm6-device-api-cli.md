# XM6 상태·설정 API와 CLI 구현 계획

**목표:** XM6에서 확인한 지원 기능과 상태를 타입 안전 API와 통합 CLI로 제공하고,
가역 설정은 자동 복원 가능한 안전 경로로만 변경한다.

**구조:** `messages`에 데이터 종류별 명령 코덱과 기능 레지스트리를 두고,
`device`가 세션·연결 수명과 다중 조회·복원을 담당한다. CLI는 device API만 사용한다.
실기기에서 확인되지 않은 읽기 후보는 별도 discovery 목록에 유지한다.

**기술:** Python 3.11+, 표준 라이브러리, BlueZ RFCOMM/SDP, pytest, argparse

---

## 1. 메시지 코덱과 기능 레지스트리

**파일:**

- 생성: `src/sonus/messages/types.py`
- 생성: `src/sonus/messages/codec.py`
- 생성: `src/sonus/messages/registry.py`
- 생성: `tests/unit/test_messages.py`

1. protocol-info, 지원 기능, 장치 문자열, 배터리와 대표 설정 응답의 성공·길이 오류
   테스트를 먼저 작성한다.
2. `pytest tests/unit/test_messages.py -q`가 모듈 부재로 실패하는지 확인한다.
3. 명령/안전 등급/기능 결과 자료형과 최소 코덱을 구현한다.
4. 파라미터화한 테스트가 통과하는지 확인한다.

## 2. 기기 API와 자동 복원

**파일:**

- 생성: `src/sonus/device/xm6.py`
- 수정: `src/sonus/device/__init__.py`
- 생성: `tests/unit/test_device.py`

1. 가짜 세션으로 단일 조회, 여러 조회의 부분 실패, 미지원 기능, 쓰기 차단,
   임시 설정의 정상·예외 복원 테스트를 작성한다.
2. 테스트 실패를 확인한 뒤 `SonyXm6Device`와 결과/예외를 최소 구현한다.
3. 복원 실패가 원래 예외를 숨기지 않으면서 별도 오류 정보를 보존하는지 검증한다.

## 3. 통합 CLI

**파일:**

- 생성: `src/sonus/cli/device.py`
- 수정: `src/sonus/cli/main.py`
- 통합: `tests/unit/test_cli_*.py` -> `tests/unit/test_cli.py`

1. `status`, `settings`, `get`, `set`, `discover`, `--json`의 파서와 출력 테스트를
   먼저 추가한다.
2. 공통 `--mac`, 선택 `--channel`, SDP 자동 탐색과 연결 종료를 구현한다.
3. 기존 probe/send/sniff 회귀 테스트를 같은 파일로 옮기고 전체 CLI 테스트를
   실행한다.

## 4. 안전한 실기기 탐색과 승격

**파일:**

- 수정: `src/sonus/messages/registry.py`
- 생성/수정: `docs/protocol/README.md`
- 생성: `tests/fixtures/captures/2026-08-16-xm6-state.json`
- 수정: `tests/hardware/test_protocol_probe.py`

1. Table 1/2 지원 기능 목록을 조회해 공식 기능과 대조한다.
2. 지원 목록에 있는 읽기 명령만 한 개씩 실행한다. 응답 없음, 연결 종료, 예상하지
   못한 데이터 종류가 나오면 해당 후보를 중단한다.
3. 응답 형식이 독립 확인된 항목만 정식 레지스트리로 옮기고 fixture 테스트를 만든다.
4. 가역 설정 하나 이상을 원값 저장·변경·재조회·복원·재조회 순서로 검증한다.
5. 초기화, 전원 끄기, 페어링, 펌웨어, 인증 관련 명령은 실행하지 않는다.

## 5. 문서·주석·테스트 구조 정리

**파일:**

- 생성: `src/sonus/**/README.md`
- 수정: `README.md`, `.gitignore`, `CLAUDE.md`
- 수정: `src/sonus/protocol/*.py`, `src/sonus/transport/*.py`
- 통합: `tests/unit/test_framing.py`, `test_stream_decoder.py` -> `test_protocol.py`

1. 각 패키지 책임과 의존 방향을 짧게 문서화한다.
2. 데이터 묶음 경계, 증분 수신, ACK 라우팅, SDP 중첩 자료 구조와 자동 복원에만
   한국어 주석을 추가한다.
3. 기존 테스트의 검증 항목 수를 유지하면서 파라미터화해 파일을 통합한다.
4. `docs/superpowers/`를 ignore하고 기존 안정 문서는 `docs/design`, `docs/plans`로
   이동한다.

## 6. 검증과 커밋

1. `uv run pytest -q`와 선택한 하드웨어 테스트를 실행한다.
2. `uv run sonus status ...`, `settings`, `get`, `discover`를 실제 XM6에서 확인한다.
3. `git diff --check`, `git status --short`로 산출물을 점검한다.
4. 전체 변경을 한국어 Conventional Commit 2~3개로 정리한다.
