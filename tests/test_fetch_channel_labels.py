from unittest.mock import MagicMock, patch

import pytest

from parselmouth.internals import conda_forge
from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.http_utils import get_global_session


@pytest.fixture(autouse=True)
def _clear_cache():
    conda_forge.fetch_channel_labels.cache_clear()
    yield
    conda_forge.fetch_channel_labels.cache_clear()


def _api_response(labels: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = labels
    response.raise_for_status.return_value = None
    return response


def test_fetch_channel_labels_does_not_use_shared_session_cookies(monkeypatch):
    monkeypatch.setenv("ANACONDA_TOKEN", "ni-test-token")

    # Simulate the cookie that conda.anaconda.org sets on repodata downloads
    # (Domain=anaconda.org), which must never reach api.anaconda.org.
    shared = get_global_session()
    shared.cookies.set("session", "anonymous", domain="anaconda.org", path="/")

    def fail_if_used(*args, **kwargs):
        raise AssertionError("labels fetch must not go through the shared session")

    with (
        patch.object(shared, "get", side_effect=fail_if_used),
        patch.object(
            conda_forge.requests,
            "get",
            return_value=_api_response({"main": {}, "dev": {}}),
        ) as mocked_get,
    ):
        labels = conda_forge.fetch_channel_labels(SupportedChannels.TANGO_CONTROLS)

    assert labels == ["main", "dev"]
    mocked_get.assert_called_once()
    args, kwargs = mocked_get.call_args
    assert args[0] == "https://api.anaconda.org/channels/tango-controls"
    assert kwargs["headers"] == {"Authorization": "token ni-test-token"}
    assert "cookies" not in kwargs

    shared.cookies.clear()


def test_fetch_channel_labels_is_cached_per_channel(monkeypatch):
    monkeypatch.setenv("ANACONDA_TOKEN", "ni-test-token")

    with patch.object(
        conda_forge.requests, "get", return_value=_api_response({"main": {}})
    ) as mocked_get:
        first = conda_forge.fetch_channel_labels(SupportedChannels.TANGO_CONTROLS)
        second = conda_forge.fetch_channel_labels(SupportedChannels.TANGO_CONTROLS)

    assert first == second == ["main"]
    mocked_get.assert_called_once()
