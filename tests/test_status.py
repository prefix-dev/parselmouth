from datetime import datetime, timezone

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.status import build_status, main

CHANNEL = SupportedChannels.CONDA_FORGE
T1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)


def test_first_run_without_update_has_no_last_updated():
    status = build_status(CHANNEL, updated=False, previous=None, now=T1)
    assert status["last_checked_at"] == "2026-01-01T12:00:00Z"
    assert status["last_updated_at"] is None
    assert status["channel"] == "conda-forge"


def test_heartbeat_keeps_previous_last_updated():
    previous = build_status(CHANNEL, updated=True, previous=None, now=T1)
    status = build_status(CHANNEL, updated=False, previous=previous, now=T2)
    assert status["last_checked_at"] == "2026-01-01T12:30:00Z"
    assert status["last_updated_at"] == "2026-01-01T12:00:00Z"


def test_update_bumps_last_updated():
    previous = build_status(CHANNEL, updated=True, previous=None, now=T1)
    status = build_status(CHANNEL, updated=True, previous=previous, now=T2)
    assert status["last_updated_at"] == "2026-01-01T12:30:00Z"


def test_main_uploads_and_reads_previous():
    class FakeS3:
        def __init__(self):
            self.stored = {"last_updated_at": "2020-01-01T00:00:00Z"}

        def get_status(self, channel):
            return self.stored

        def upload_status(self, status, channel):
            self.stored = status

    fake = FakeS3()
    status = main(CHANNEL, updated=False, upload=True, s3=fake)  # type: ignore[arg-type]
    assert fake.stored == status
    assert status["last_updated_at"] == "2020-01-01T00:00:00Z"


def test_main_without_upload_does_not_touch_s3():
    class ExplodingS3:
        def get_status(self, channel):
            raise AssertionError("should not be called")

        def upload_status(self, status, channel):
            raise AssertionError("should not be called")

    main(CHANNEL, updated=True, upload=False, s3=ExplodingS3())  # type: ignore[arg-type]
