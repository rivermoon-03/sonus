# Sonus 전체 설정 쓰기와 데스크톱 GUI 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** XM6에서 가역성이 입증된 설정을 모두 쓰기 가능하게 만들고, 최초 Disclaimer 동의 뒤에 이를 조작하는 컴팩트 PyQt6 데스크톱 GUI를 완성한다.

**Architecture:** 명령 코덱과 안전 등급은 `messages`, 왕복 검증과 직렬 실행은 `device`, Qt 스레드와 권한 검사는 `gui`, 표현과 입력은 로컬 WebEngine 자산이 담당한다. 후보 쓰기는 항목별 하드웨어 테스트에서 변경·재조회·원복·원복 재조회를 모두 통과한 경우에만 `REVERSIBLE`로 남긴다.

**Tech Stack:** Python 3.11+, PyQt6 6.7+, Qt WebEngine/WebChannel, HTML/CSS/JavaScript, Lucide SVG, pytest, Node test runner, BlueZ RFCOMM

## Global Constraints

- Linux와 BlueZ만 지원한다.
- `gui -> device -> messages -> protocol -> transport` 의존 방향을 지킨다.
- GUI는 원시 payload나 소켓을 직접 다루지 않는다.
- 전원 끄기, 초기화, 페어링 관리, 펌웨어, identity resolving key 명령은 구현하거나 시험하지 않는다.
- 실측 쓰기는 원값 조회, 시험값 쓰기, 재조회, 원복, 원복 재조회를 모두 수행한다.
- 복원을 증명하지 못한 항목은 읽기 전용으로 남긴다.
- raw exception을 사용자에게 표시하지 않는다.
- 원격 저장소에는 push하지 않는다.

---

### Task 1: 설정 코덱과 선언적 쓰기 명령

**Files:**
- Modify: `src/sonus/messages/codec.py`
- Modify: `src/sonus/messages/registry.py`
- Modify: `tests/unit/test_messages.py`

**Interfaces:**
- Consumes: `FeatureSpec`, `Safety`, 기존 XM6 실측 읽기 payload
- Produces: `encode_noise_control(value)`, `encode_equalizer(value)`, `encode_connection_mode(value)`, `encode_system_toggle(type_id, value)`, `encode_speak_to_chat(value)`, `encode_auto_power_off(value)`, `encode_voice_guidance(value)`, `encode_voice_guidance_volume(value)`, `encode_safe_listening(value)`, `encode_safe_volume(value)`

- [ ] **Step 1: 복합 응답의 손실 없는 디코딩 테스트를 작성한다**

`tests/unit/test_messages.py`에 다음 계약을 추가한다.

```python
def test_noise_control_preserves_every_wire_field():
    assert decode_noise_control(bytes.fromhex("671901000000100000")) == {
        "enabled": False,
        "mode": "noise_cancelling",
        "focus_voice": False,
        "ambient_level": 16,
        "auto_ambient": False,
        "adaptive_sensitivity": 0,
    }

def test_auto_power_off_preserves_last_selected_value():
    assert decode_auto_power_off(bytes.fromhex("27051100")) == {
        "mode": "disabled",
        "last_mode": "5_minutes",
    }

def test_speak_to_chat_preserves_preview_mode():
    assert decode_speak_to_chat(bytes.fromhex("f70c0101")) == {
        "enabled": False,
        "preview": False,
    }
```

- [ ] **Step 2: 위 테스트가 기존 단순 반환값 때문에 실패하는지 확인한다**

Run: `uv run pytest tests/unit/test_messages.py -q`

Expected: FAIL on the three exact nested values.

- [ ] **Step 3: 읽기 코덱을 손실 없는 값 객체로 바꾼다**

`decode_noise_control()`은 value-change byte를 제외한 여섯 설정 필드를 해석하고,
`decode_auto_power_off()`는 현재/마지막 선택을 모두 보존하며,
`decode_speak_to_chat()`은 on/off와 preview 바이트를 모두 보존한다. Sony의
`EnableDisable` 값은 `0=enabled`, `1=disabled` 규칙을 사용한다.

- [ ] **Step 4: 정확한 후보 쓰기 payload 테스트를 작성한다**

다음 입력과 payload를 literal assertion으로 고정한다.

```python
assert encode_noise_control({
    "enabled": True, "mode": "ambient_sound", "focus_voice": False,
    "ambient_level": 15, "auto_ambient": False, "adaptive_sensitivity": 0,
}) == bytes.fromhex("6819010101000f0000")
assert encode_equalizer({"preset": 0xA1, "bands": [8,9,7,5,7,7,7,6,10,11]}) \
    == bytes.fromhex("5804a10a08090705070707060a0b")
assert encode_connection_mode("stable_connection") == bytes.fromhex("e80001")
assert encode_system_toggle(0x01, False) == bytes.fromhex("f80101")
assert encode_speak_to_chat({"enabled": True, "preview": False}) == bytes.fromhex("f80c0001")
assert encode_auto_power_off({"mode": "180_minutes", "last_mode": "180_minutes"}) \
    == bytes.fromhex("28050303")
assert encode_voice_guidance({"enabled": False, "language": "japanese"}) \
    == bytes.fromhex("4801010b")
assert encode_voice_guidance_volume(-1) == bytes.fromhex("4820ff01")
assert encode_safe_listening({"enabled": False, "preview": False}) \
    == bytes.fromhex("58020101")
assert encode_safe_volume({"limited": False, "enabled": False}) \
    == bytes.fromhex("58040101")
```

- [ ] **Step 5: 입력 범위를 엄격히 검사하는 인코더를 구현한다**

ANC 주변음은 1..20, EQ는 정확히 10밴드와 각 0..20, 음성 안내 음량은 -2..2만
받는다. 자동 전원 끄기는 `5_minutes`, `15_minutes`, `30_minutes`,
`60_minutes`, `180_minutes`, `when_removed`, `disabled`만 받는다. 복합 설정은
원래 값의 나머지 필드를 빠뜨린 부분 입력을 거부한다.

- [ ] **Step 6: 후보 FeatureSpec을 쓰기 응답과 함께 선언한다**

명령별 응답은 `68->69`, `58->59`, `E8->E9`, `F8->F9`, `28->29`,
`48->49`, Table 2의 `58->59`를 사용한다. 이 단계에서는 하드웨어 시험 대상만
임시 `Safety.REVERSIBLE`로 선언하며 실패한 항목은 Task 3에서 즉시 되돌린다.

- [ ] **Step 7: 메시지 단위 테스트를 통과시킨다**

Run: `uv run pytest tests/unit/test_messages.py -q`

Expected: PASS.

### Task 2: 재조회와 복원을 강제하는 디바이스 API

**Files:**
- Modify: `src/sonus/device/xm6.py`
- Modify: `tests/unit/test_device.py`

**Interfaces:**
- Consumes: `FeatureSpec.encoder`, `FeatureSpec.matches_write_payload()`
- Produces: `SonyXm6Device.set_verified(key: str, value: Any) -> FeatureResult`, `RestoreFailedError`

- [ ] **Step 1: 설정 응답만 맞고 재조회가 다르면 실패하는 테스트를 작성한다**

가짜 세션에 원값 GET, SET 응답, 불일치 GET을 넣고 `set_verified()`가
`WriteVerificationError`를 발생시키는지 검사한다.

- [ ] **Step 2: 복원 첫 시도가 실패하면 한 번 재시도하는 테스트를 작성한다**

`temporary_setting()`의 세션 응답을 원값 GET, 시험 SET, 시험 GET, 실패한 복원 SET,
성공한 복원 SET, 원복 GET 순서로 넣고 마지막 값이 원값인지 검사한다.

- [ ] **Step 3: 새 실패 테스트를 실행한다**

Run: `uv run pytest tests/unit/test_device.py -q`

Expected: FAIL because `set_verified` and restore retry do not exist.

- [ ] **Step 4: 검증 쓰기와 복원 오류를 구현한다**

`set_verified()`는 `set()` 뒤 `get()`을 호출하고 값이 다르면
`WriteVerificationError(key, requested, observed)`를 발생시킨다.
`temporary_setting()`은 시험값 재조회와 원복 재조회를 수행하며 원복 SET 실패 시
한 번 재시도한다. 최종 원복을 증명하지 못하면 `RestoreFailedError`를 발생시킨다.

- [ ] **Step 5: 디바이스 단위 테스트를 통과시킨다**

Run: `uv run pytest tests/unit/test_device.py -q`

Expected: PASS.

### Task 3: XM6 항목별 하드웨어 쓰기 검증

**Files:**
- Modify: `tests/hardware/test_protocol_probe.py`
- Create: `tests/fixtures/captures/2026-08-16-xm6-writes.json`
- Modify: `docs/protocol/README.md`
- Modify: `src/sonus/messages/registry.py`

**Interfaces:**
- Consumes: `SonyXm6Device.temporary_setting()` and candidate registry entries
- Produces: verified `Safety.REVERSIBLE` entries and anonymized evidence

- [ ] **Step 1: 읽기 전용 사전 점검을 실행한다**

Run: `.venv/bin/sonus settings --mac 58:18:62:1F:C9:CB --channel 9 --json`

Expected: model WH-1000XM6, firmware 3.1.5, every candidate original value captured.

- [ ] **Step 2: 항목별 하드웨어 테스트를 파라미터화한다**

시험값은 ANC의 주변음 단계만 1 감소, EQ의 첫 밴드만 1 증감, boolean은 반전,
연결 모드는 반대 모드, 자동 전원 끄기는 `180_minutes`, 음성 음량은 0에서 1 또는
현재값에서 안쪽 방향 1단계로 정한다. 복합 값의 나머지 필드는 원본을 그대로 복사한다.

- [ ] **Step 3: DSEE와 ANC를 각각 단독 실행한다**

Run: `uv run pytest -m hardware tests/hardware/test_protocol_probe.py -k 'write_dsee or write_noise_control' -vv`

Expected: both PASS and restored GET equals original.

- [ ] **Step 4: EQ, 자동 일시정지, Speak-to-Chat을 각각 단독 실행한다**

Run: `uv run pytest -m hardware tests/hardware/test_protocol_probe.py -k 'write_equalizer or write_auto_pause or write_speak_to_chat' -vv`

Expected: every promoted item PASS and restored GET equals original.

- [ ] **Step 5: 연결 모드와 자동 전원 끄기를 각각 단독 실행한다**

Run: `uv run pytest -m hardware tests/hardware/test_protocol_probe.py -k 'write_connection_mode or write_auto_power_off' -vv`

Expected: restored value equals original; connection mode also succeeds after a fresh reconnect.

- [ ] **Step 6: 음성 안내와 음량을 각각 단독 실행한다**

언어는 바꾸지 않고 enabled만 반전한다. 음량 SET의 feedback byte는 `1`을 사용한다.

Run: `uv run pytest -m hardware tests/hardware/test_protocol_probe.py -k 'write_voice_guidance or write_voice_guidance_volume' -vv`

Expected: every promoted item PASS and restored GET equals original.

- [ ] **Step 7: 안전 청취와 안전 음량의 원값 가시성을 먼저 판정한다**

`57 02`와 `57 04` 응답이 설정값이 아니라 availability 하나만 반환하므로, 원래 두
필드 값을 읽거나 알림으로 확정할 수 없는 경우 SET을 보내지 않는다. 이 경우 두 항목의
표시를 `지원됨`으로 고치되 읽기 전용으로 남기고 문서에 “복원 불가로 미승격”을 기록한다.
원값 두 필드를 독립적으로 확보한 경우에만 단독 변경·재조회·원복 시험을 실행한다.

- [ ] **Step 8: 성공한 항목만 정식 쓰기로 남긴다**

실패하거나 원복을 증명하지 못한 FeatureSpec에서 encoder와 쓰기 응답 필드를 제거하고
`Safety.READ_ONLY`로 되돌린다. 캡처 JSON에는 기능 키, 원값, 시험값, 설정 응답,
변경 재조회, 원복 응답, 원복 재조회만 기록하고 MAC 주소는 넣지 않는다.

- [ ] **Step 9: 프로토콜 문서와 회귀 테스트를 갱신한다**

`docs/protocol/README.md`의 쓰기 열을 실제 판정으로 바꾸고 펌웨어 3.1.5, 날짜,
요청·응답과 판정 근거를 기록한다.

### Task 4: Disclaimer와 Qt 쓰기 파이프라인

**Files:**
- Modify: `src/sonus/gui/settings.py`
- Modify: `src/sonus/gui/state.py`
- Modify: `src/sonus/gui/bridge.py`
- Rename/Modify: `src/sonus/gui/worker.py`
- Modify: `src/sonus/gui/application.py`
- Create: `src/sonus/gui/devices.py`
- Modify: `tests/unit/test_gui_settings.py`
- Modify: `tests/unit/test_gui_bridge.py`
- Modify: `tests/unit/test_gui_state.py`
- Modify: `tests/unit/test_gui_worker.py`
- Modify: `tests/unit/test_gui_application.py`
- Complete: `tests/unit/test_gui_devices.py`

**Interfaces:**
- Produces: `GuiSettings.disclaimer_accepted`, `GuiBridge.acceptDisclaimer()`, `GuiBridge.setFeature(key_json, value_json)`, `DeviceWorker.writeRequested`, `parse_bluetoothctl_devices(output)`

- [ ] **Step 1: 기존 미완성 기기 선택 테스트를 먼저 실행한다**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/test_gui_devices.py tests/unit/test_gui_settings.py tests/unit/test_gui_bridge.py -q`

Expected: FAIL because saved devices and discovery APIs are not implemented.

- [ ] **Step 2: 저장 기기와 bluetoothctl 파서를 구현한다**

`GuiSettings.saved_devices`는 JSON 배열을 읽되 잘못된 항목을 버린다.
`remember_device(mac, channel, name)`는 MAC 기준 중복 제거 후 최신 항목을 앞에 둔다.
`parse_bluetoothctl_devices()`는 `Device MAC NAME` 행만 받아 대문자 MAC과 기본 채널
9를 반환한다. subprocess 실패는 사용자 문구로 변환한다.

- [ ] **Step 3: Disclaimer 저장과 초기 상태 테스트를 작성한다**

기본값 false, accept 후 재생성해 true, 초기 JSON의 `disclaimerAccepted`와 실제
`writable` 보존을 검사한다. 동의 전 `setFeature()`가 쓰기 신호 대신 사용자 메시지를
내보내는지 확인한다.

- [ ] **Step 4: bridge 입력 검증 테스트를 작성한다**

알 수 없는 키, registry에서 read-only인 키, 잘못된 JSON/값은 거부하고 검증된 키와
값만 `writeRequested(str, object)`로 전달하는지 검사한다.

- [ ] **Step 5: Qt 테스트 실패를 확인한다**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/test_gui_settings.py tests/unit/test_gui_bridge.py tests/unit/test_gui_state.py -q`

Expected: FAIL on disclaimer and write contracts.

- [ ] **Step 6: 설정, 상태 직렬화와 bridge 슬롯을 구현한다**

`serialize_result()`는 `result.writable`을 보존한다. `acceptDisclaimer()`은 QSettings를
저장하고 새 초기 상태를 emit한다. `setFeature()`는 동의, feature, writable, JSON 값을
검사한 뒤 쓰기 신호를 emit한다.

- [ ] **Step 7: 읽기/쓰기 작업을 하나의 직렬 worker로 통합한다**

동일 QThread 안에서 한 번에 한 장치 작업만 수행한다. 쓰기는 `device.set_verified()`를
호출하고 성공한 `FeatureResult`를 emit한다. 처리 중 새 요청은 “작업이 진행 중입니다”로
거부한다. 연결·시간 초과·검증 실패·복원 실패를 서로 다른 한국어 문구로 바꾼다.

- [ ] **Step 8: Qt GUI 테스트를 통과시킨다**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/test_gui_settings.py tests/unit/test_gui_bridge.py tests/unit/test_gui_state.py tests/unit/test_gui_worker.py tests/unit/test_gui_application.py tests/unit/test_gui_devices.py -q`

Expected: PASS.

### Task 5: 컴팩트 데스크톱 웹 UI

**Files:**
- Modify: `src/sonus/gui/web/index.html`
- Modify: `src/sonus/gui/web/styles.css`
- Modify: `src/sonus/gui/web/app.js`
- Modify: `src/sonus/gui/web/app.test.mjs`
- Create: `src/sonus/gui/web/assets/lucide.svg`
- Create: `src/sonus/gui/web/assets/LUCIDE-LICENSE.txt`
- Modify: `tests/unit/test_gui_web_assets.py`

**Interfaces:**
- Consumes: `initialState.disclaimerAccepted`, feature `writable`, WebChannel `setFeature()`
- Produces: compact fixed app shell and interactive controls

- [ ] **Step 1: 정적 UI 계약 테스트를 작성한다**

사이드바의 `>01<`..`>05<`, `🔒`, `↻`, `☼`, `☾`가 없고 `lucide.svg`를 사용하며,
HTML에 Disclaimer dialog가 있고 CSS에 `height:100vh`, `overflow:hidden`,
`overflow-y:auto`, `scrollbar-gutter:stable`이 있는지 검사한다.

- [ ] **Step 2: JavaScript 쓰기 상태 테스트를 작성한다**

초기 동의 false, writable feature 수신, 쓰기 시작/성공/실패 reducer 동작과 실패 시
마지막 확인값 복원을 Node 테스트로 고정한다. read-only feature 컨트롤은 계속 disabled여야
한다.

- [ ] **Step 3: 웹 테스트 실패를 확인한다**

Run: `node --test src/sonus/gui/web/app.test.mjs`

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/test_gui_web_assets.py -q`

Expected: FAIL on old numbers, emoji, read-only state, and missing disclaimer/icons.

- [ ] **Step 4: 로컬 Lucide SVG 스프라이트를 추가한다**

`gauge`, `volume-2`, `sliders-horizontal`, `settings-2`, `info`, `refresh-cw`,
`sun`, `moon`, `triangle-alert`, `check`, `x`, `headphones`, `bluetooth`,
`battery-medium` 심벌과 ISC 라이선스를 번들한다.

- [ ] **Step 5: 고정 앱 셸로 레이아웃을 재구성한다**

사이드바 208px, 툴바 52px, 중앙 `.content-scroll`만 스크롤하게 한다. 큰 hero와 kicker를
제거하고 800×620에서는 설정 행이 한 열로 정렬되게 한다. scrollbar gutter를 항상
예약하고 Qt WebEngine 스크롤바의 폭과 색을 라이트/다크에서 동일하게 지정한다.

- [ ] **Step 6: 실제 설정 컨트롤을 연결한다**

ANC는 세그먼트+주변음 슬라이더, DSEE/boolean은 switch, 연결 모드와 자동 전원 끄기는
select, 음성 음량은 -2..2 stepper, EQ는 10개 range 입력으로 만든다. 변경 시 원본 복합
값을 복사한 뒤 한 필드만 바꾸어 `setFeature()`에 전달한다.

- [ ] **Step 7: Disclaimer와 연결 흐름을 구현한다**

동의 정보가 없으면 Disclaimer dialog만 표시하고 거부/닫기는 `quitApplication()`을
호출한다. 동의 뒤 저장 기기 선택/연결 dialog로 넘어간다. 동의 상태는 localStorage가
아니라 Python 초기 상태만 신뢰한다.

- [ ] **Step 8: 웹 테스트를 통과시킨다**

Run: `node --test src/sonus/gui/web/app.test.mjs`

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/test_gui_web_assets.py -q`

Expected: PASS.

### Task 6: 문서, 전체 회귀와 실제 GUI 확인

**Files:**
- Modify: `README.md`
- Modify: `src/sonus/gui/README.md`
- Modify: `src/sonus/gui/main.py`
- Modify: `tests/unit/test_cli.py` or relevant CLI tests if nested values change output

**Interfaces:**
- Produces: accurate user documentation and release verification evidence

- [ ] **Step 1: 읽기 전용 문구를 실제 안전 정책으로 갱신한다**

GUI README와 CLI 도움말에서 “완전 읽기 전용”을 제거하고, 실기기에서 가역성이 확인된
기능만 쓸 수 있으며 Disclaimer가 한 번 표시된다는 내용을 적는다.

- [ ] **Step 2: 기본 전체 테스트를 실행한다**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest -q`

Expected: PASS; hardware tests excluded.

- [ ] **Step 3: JavaScript 전체 테스트와 문법을 확인한다**

Run: `node --test design-preview/asset.test.mjs design-preview/app.test.mjs src/sonus/gui/web/app.test.mjs`

Run: `node --check src/sonus/gui/web/app.js`

Expected: PASS and exit 0.

- [ ] **Step 4: 실행·패키징 계약을 확인한다**

Run: `./run.sh --help`

Run: `uv run sonus-gui --help`

Run: `uv build`

Expected: all exit 0 and wheel contains web assets.

- [ ] **Step 5: 오프스크린 스크린샷으로 최소/기본 창을 확인한다**

800×620과 1180×780에서 각 메뉴를 열어 가로 스크롤이 없고, 콘텐츠 gutter가 메뉴마다
움직이지 않으며, Disclaimer가 최초 한 번만 표시되는지 확인한다.

- [ ] **Step 6: 최종 하드웨어 회귀를 실행한다**

Run: `uv run pytest -m hardware tests/hardware/test_protocol_probe.py -vv`

Expected: protocol probe plus every retained writable feature PASS with restored original values.

### Task 7: 한국어 두 커밋으로 재구성하고 main 통합

**Files:**
- Verify all changed paths

**Interfaces:**
- Consumes: fully verified worktree state
- Produces: two Korean commits on `design/gui-design-system-preview`, then local `main`

- [ ] **Step 1: 현재 브랜치 끝점을 복구 가능한 로컬 백업 브랜치로 보존한다**

Run: `git branch backup/gui-design-system-preview-before-squash design/gui-design-system-preview`

Expected: backup branch points to the pre-rewrite tip.

- [ ] **Step 2: 전체 변경을 main 기준 staged 상태로 재구성한다**

Run: `git reset --soft main`

Expected: no working files deleted; all branch changes staged.

- [ ] **Step 3: 프로토콜·디바이스 변경만 첫 커밋으로 만든다**

첫 커밋에는 `src/sonus/{messages,device,protocol,transport,cli}`, 해당 테스트,
캡처와 프로토콜/설계 문서를 담는다.

Commit: `기능: XM6 설정 쓰기 검증과 디바이스 API 확장`

- [ ] **Step 4: GUI와 나머지 사용자 경험 변경을 둘째 커밋으로 만든다**

두 번째 커밋에는 `src/sonus/gui`, 디자인 프리뷰, GUI 테스트, 패키징과 실행 문서를 담는다.

Commit: `기능: 데스크톱 GUI 완성과 사용자 경험 개선`

- [ ] **Step 5: 두 커밋에서 전체 검증을 다시 실행한다**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest -q`

Run: `node --test design-preview/asset.test.mjs design-preview/app.test.mjs src/sonus/gui/web/app.test.mjs`

Run: `uv build`

Expected: all PASS.

- [ ] **Step 6: 로컬 main을 fast-forward한다**

기본 작업 트리에서 `git merge --ff-only design/gui-design-system-preview`를 실행한다.
main의 기존 `.gitignore` 수정은 보존하며 충돌하면 해당 한 파일만 수동 병합한다.

- [ ] **Step 7: 통합 결과와 원격 미변경을 확인한다**

Run: `git log -2 --format='%s'`

Expected: the two Korean commit subjects in order.

Run: `git status --short`

Expected: only the user's pre-existing `.gitignore` change, if still uncommitted.

Do not run `git push`.
