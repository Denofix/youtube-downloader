import json

import pytest
from service import diagnostics, sources
from service.errors import ServiceError, extractor_error


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("This video is DRM protected", "drm_protected"),
        ("DRM-protected formats only", "drm_protected"),
        ("Unable to extract client id", "soundcloud_client_id"),
        ("HTTP Error 429: Too Many Requests", "source_rate_limited"),
        ("This item is not available in your country", "source_region"),
        ("Unable to extract universal data for rehydration", "source_page_unreadable"),
        ("Unable to extract challenge data", "source_page_unreadable"),
        ("Unexpected response from webpage request", "source_page_unreadable"),
        ("Unable to extract webpage video data", "source_page_unreadable"),
    ],
)
def test_source_failures_have_specific_private_reasons(message, code):
    error = extractor_error(
        Exception(message + " https://media.example/file?token=SECRET /srv/cookies.txt")
    )
    assert error.code == code
    assert "SECRET" not in error.message and "/srv" not in error.message
    assert "media.example" not in error.message


def test_installed_browser_transport_is_usable():
    runtime = diagnostics.runtime_status()
    assert runtime["browser_impersonation"]
    assert runtime["versions"]["curl-cffi"] != "missing"
    assert any(target.startswith("chrome-") for target in runtime["targets"])


def test_diagnostics_never_echo_unapproved_input(config):
    result = diagnostics.diagnose("http://127.0.0.1/private?token=SECRET", config)
    assert result["state"] == "failed" and result["error"]["code"] == "invalid_url"
    assert "SECRET" not in json.dumps(result) and "127.0.0.1" not in json.dumps(result)


def test_diagnostics_explain_drm_without_attempting_download(config, monkeypatch):
    def protected(*args):
        raise extractor_error(Exception("This video is DRM protected"))

    monkeypatch.setattr(sources, "analyze", protected)
    result = diagnostics.diagnose("https://soundcloud.com/test-artist/owned-track", config)
    assert result["state"] == "failed" and result["error"]["code"] == "drm_protected"
    assert result["source"]["platform"] == "SoundCloud"


def test_drm_reason_survives_api_queue(client, store, monkeypatch):
    from conftest import work

    def protected(*args):
        raise ServiceError("drm_protected", "This item has no unprotected download.")

    monkeypatch.setattr(sources, "analyze", protected)
    response = client.post(
        "/api/analyze", json={"url": "https://soundcloud.com/test-artist/owned-track"}
    )
    assert response.status_code == 202
    task = work(store)
    public = client.get("/api/tasks/" + task["id"]).json()
    assert public["state"] == "failed" and public["error"]["code"] == "drm_protected"
    settings = client.get("/api/settings").json()
    assert settings["source_transport"]["browser_impersonation"]
    assert settings["versions"]["curl-cffi"] != "missing"
