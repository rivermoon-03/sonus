# 프로토콜

RFCOMM 위의 Sony MDR 데이터 묶음과 요청 세션을 처리한다. `framing.py`는 생성,
해석과 연속 수신 데이터 재조립을, `session.py`는 ACK·재시도·응답·비동기 알림 분리를
담당한다. 명령별 의미는 이 계층이 아니라 `messages`에 둔다.
