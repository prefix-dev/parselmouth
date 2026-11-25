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


def _json_response(payload) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def _fake_api(url, **kwargs):
    if url == "https://api.anaconda.org/packages/tango-controls":
        return _json_response([{"name": "pytango"}, {"name": "omniorb"}])
    if url == "https://api.anaconda.org/package/tango-controls/pytango":
        return _json_response(
            {"files": [{"labels": ["main"]}, {"labels": ["main", "pytango_dev"]}]}
        )
    if url == "https://api.anaconda.org/package/tango-controls/omniorb":
        return _json_response({"files": [{"labels": ["dev"]}, {}]})
    raise AssertionError(f"unexpected URL {url}")


def test_fetch_channel_labels_from_public_api_without_token(monkeypatch):
    monkeypatch.delenv("ANACONDA_TOKEN", raising=False)

    # Simulate the cookie that conda.anaconda.org sets on repodata downloads
    # (Domain=anaconda.org), which must never reach api.anaconda.org.
    shared = get_global_session()
    shared.cookies.set("session", "anonymous", domain="anaconda.org", path="/")

    def fail_if_used(*args, **kwargs):
        raise AssertionError("labels fetch must not go through the shared session")

    try:
        with (
            patch.object(shared, "get", side_effect=fail_if_used),
            patch.object(
                conda_forge.requests.Session, "get", side_effect=_fake_api
            ) as mocked_get,
        ):
            labels = conda_forge.fetch_channel_labels(SupportedChannels.TANGO_CONTROLS)
    finally:
        shared.cookies.clear()

    assert labels == ["dev", "main", "pytango_dev"]
    assert mocked_get.call_count == 3
    for _, kwargs in mocked_get.call_args_list:
        assert "headers" not in kwargs


def test_fetch_channel_labels_is_cached_per_channel():
    with patch.object(
        conda_forge.requests.Session, "get", side_effect=_fake_api
    ) as mocked_get:
        first = conda_forge.fetch_channel_labels(SupportedChannels.TANGO_CONTROLS)
        second = conda_forge.fetch_channel_labels(SupportedChannels.TANGO_CONTROLS)

    assert first == second == ["dev", "main", "pytango_dev"]
    assert mocked_get.call_count == 3
