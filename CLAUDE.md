# CLAUDE.md

sonus는 Sony WH-1000XM6용 Linux 전용 Python 드라이버와 제어 앱 프로젝트다.
현재 Python 드라이버와 CLI가 구현되어 있고 PyQt6 GUI는 다음 단계다. 전체 사용법과
현재 기능은 `README.md`, 실측 프로토콜과 지원 범위는 `docs/protocol/README.md`,
기본 설계는 `docs/design/2026-08-15-sonus-driver-design.md`를 본다.

## 현재 명령

- 일반 조회·제어: `probe`, `status`, `settings`, `discover`, `get`, `set`
- 프로토콜 개발용 저수준 도구: `sniff`, `send`
- `status`, `settings`, `discover`, `get`처럼 읽기 전용인 명령을 먼저 사용한다.
- 정식 쓰기는 실기기에서 변경과 원상 복원을 확인한 DSEE만 허용한다. 그 외 항목은
  기기가 지원한다고 광고해도 쓰기 명령과 안전한 복원을 별도로 검증하기 전까지
  읽기 전용으로 둔다.

## 계층 규칙 (위반 금지)

각 계층은 바로 아래 계층만 참조한다. 역방향 import 금지.

```
gui/  ──depends on──▶  device/  ──▶  messages/  ──▶  protocol/  ──▶  transport/
cli/  ──depends on──▶  device/ (필요 시 protocol/ 직접 접근 가능, 통신 테스트 전용)
```

- `transport/`, `protocol/`, `messages/`, `device/`는 **PyQt6를 import하지 않는다.**
  GUI는 언제든 갈아끼울 수 있는 소비자여야 한다.
- `protocol/`은 순수 함수(바이트 in → 바이트 out) 위주로 유지한다. 소켓 I/O를
  섞지 않는다 — 그래야 하드웨어 없이 전량 유닛 테스트가 가능하다.
- 새 기기 명령을 알아내면 `messages/registry.py`에 선언적으로 추가한다.
  GUI/CLI 코드를 고치지 않고 새 명령을 추가할 수 있어야 한다.

## 프로토콜 작업 시 주의

- XM6 고유 명령은 미확정. 커뮤니티 자료(XM4/XM5 기준)는 **가설**로만 쓰고,
  실제 동작은 반드시 실기기(`58:18:62:1F:C9:CB`)에 요청을 보내 관찰·검증한다.
- 관찰한 데이터 묶음/명령 구조는 `docs/protocol/`에 문서화해도 된다(상호운용성
  목적의 관찰 기록은 허용 범위). 단, Sony 코드·펌웨어·바이너리 자체를
  복사하거나 포함하지 않는다.
- 실측 바이트 캡처는 `tests/fixtures/captures/`에 저장하고 회귀 테스트로
  연결한다.
- 실기기 조사 결과는 `docs/protocol/`에 날짜, 펌웨어, 요청·응답과 판정 근거를
  기록한다. MAC 주소 같은 기기 식별자는 캡처에서 제거한다.
- 읽기 조사에서 `set`, 미확인 raw `send`, 장시간 `sniff`를 실행하지 않는다.
  전원 끄기, 초기화, 페어링 관리, 펌웨어 명령과 identity resolving key 조회는
  구현·실험 대상에서 제외한다.

## 테스트

- `tests/unit/`: 하드웨어 불필요. 기본 `pytest`가 여기만 돌며 항상 통과해야 한다.
- `tests/hardware/`: 실기기 필요. `pytest.mark.hardware`로 표시하고
  `pytest -m hardware`로만 실행한다. 기본 실행에는 포함하지 않는다.
- 프로젝트 명령은 `uv run pytest`와 `uv run pytest -m hardware`를 사용한다.
  하드웨어 테스트는 연결된 사용자 소유 기기의 상태나 설정을 바꿀 수 있으므로
  테스트 내용을 먼저 확인한다.

## GUI 스타일

심플·미니멀. 화려한 애니메이션 없음. 다크/라이트 모드 토글 가능, 포인트
컬러는 파랑 계열 하나로 통일. raw exception을 그대로 사용자에게 보여주지
않는다 — 상태바에 사람이 읽을 문구로 변환한다.

## 구현 위임

코드 작성을 서브에이전트에 위임할 때는 모델을 Sonnet 또는 Haiku로 지정한다
(Opus 사용 금지). 판단이 필요한 구현(프로토콜 코덱, 상태 관리)은 Sonnet,
기계적 보일러플레이트·테스트는 Haiku.
