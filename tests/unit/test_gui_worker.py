from __future__ import annotations

import json
from contextlib import contextmanager

from sonus.device.xm6 import FeatureResult
from sonus.gui.worker import DeviceReadWorker, DeviceWriteWorker


class FakeDevice:
    def __init__(self):
        self.requested = []

    def get(self, key):
        self.requested.append(key)
        if key == "codec":
            raise TimeoutError("no response")
        return FeatureResult(key, key.title(), {"level": 67} if key == "battery" else True)


def test_worker_emits_progressive_results_and_isolates_feature_failure():
    device = FakeDevice()

    @contextmanager
    def opener(mac, channel):
        assert (mac, channel) == ("AA", 9)
        yield device

    worker = DeviceReadWorker("AA", 9, keys=("battery", "codec", "dsee"), opener=opener)
    events = []
    worker.connecting.connect(lambda: events.append("connecting"))
    worker.connected.connect(lambda: events.append("connected"))
    worker.featureReady.connect(lambda payload: events.append(json.loads(payload)))
    worker.finished.connect(lambda: events.append("finished"))

    worker.run()

    assert events[0:2] == ["connecting", "connected"]
    assert [event["key"] for event in events[2:5]] == ["battery", "codec", "dsee"]
    assert events[3]["supported"] is False
    assert events[3]["error"] == "timeout"
    assert events[-1] == "finished"
    assert device.requested == ["battery", "codec", "dsee"]


def test_worker_reports_connection_failure_and_finishes():
    @contextmanager
    def opener(mac, channel):
        raise OSError("socket detail")
        yield

    worker = DeviceReadWorker("AA", None, opener=opener)
    failures = []
    finished = []
    worker.failed.connect(failures.append)
    worker.finished.connect(lambda: finished.append(True))

    worker.run()

    assert failures == ["Bluetooth 연결에 실패했습니다."]
    assert finished == [True]


def test_write_worker_uses_verified_write_and_emits_refreshed_feature():
    device = FakeDevice()
    written = []

    def set_verified(key, value):
        written.append((key, value))
        return FeatureResult(key, "DSEE Extreme", value, writable=True)

    device.set_verified = set_verified

    @contextmanager
    def opener(mac, channel):
        yield device

    worker = DeviceWriteWorker("AA", 9, "dsee", False, opener=opener)
    features = []
    worker.featureReady.connect(lambda payload: features.append(json.loads(payload)))

    worker.run()

    assert written == [("dsee", False)]
    assert features[0]["value"] is False
    assert features[0]["writable"] is True


def test_write_worker_hides_internal_failure_details():
    @contextmanager
    def opener(mac, channel):
        raise OSError("private socket detail")
        yield

    worker = DeviceWriteWorker("AA", 9, "dsee", False, opener=opener)
    failures = []
    worker.failed.connect(failures.append)

    worker.run()

    assert failures == ["설정을 적용하지 못했습니다. 원래 상태를 확인해 주세요."]
