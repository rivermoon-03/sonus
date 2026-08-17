# GUI

PyQt6 데스크톱 셸과 로컬 Qt WebEngine 화면을 제공한다. `device` 공개 API만 사용하고
소켓, 데이터 묶음, 원시 명령에는 직접 의존하지 않는다.

- `application.py`: 창, 시스템 트레이, QWebChannel, 직렬 작업 스레드 수명 관리
- `bridge.py`: 동의와 registry 안전 등급을 검사하는 좁은 API
- `worker.py`: 기능 조회와 검증 쓰기를 UI 스레드 밖에서 실행
- `settings.py`: 동의, 테마, 저장 기기와 창 위치 저장
- `web/`: Pretendard, Lucide와 제품 벡터 이미지를 포함한 로컬 인터페이스

최초 Disclaimer 동의를 `QSettings`에 보존한다. 쓰기 요청은 registry에서 가역성이
확인된 기능만 받아 `set_verified()`로 적용 후 재조회하며 한 번에 하나만 실행한다.
원상 복원을 증명하지 못한 기능은 비활성화 상태로 표시한다. 실행은
`uv run sonus-gui`를 사용한다.
