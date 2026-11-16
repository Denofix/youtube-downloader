"""Individual Instagram contracts, real yt-dlp downloads and controlled access errors."""

from copy import deepcopy

import pytest
from conftest import work
from service import sources
from service.errors import ServiceError
from yt_dlp.extractor.instagram import InstagramIE
from yt_dlp.utils import ExtractorError

REEL = "https://www.instagram.com/reel/OwnedIG01/"
POST = "https://www.instagram.com/p/OwnedIG01/"


@pytest.mark.parametrize("route", ["p", "reel", "reels", "tv"])
@pytest.mark.parametrize("host", ["instagram.com", "www.instagram.com", "m.instagram.com"])
def test_instagram_canonicalization(route, host):
    expected_route = "reel" if route == "reels" else route
    url = sources.validate_url(f"http://{host}/{route}/OwnedIG01?igsh=tracking#fragment")
    assert url == f"https://www.instagram.com/{expected_route}/OwnedIG01/"
    assert sources.platform_for(url) == "Instagram"


@pytest.mark.parametrize(
    "url",
    [
        "https://instagram.com.evil.example/reel/OwnedIG01/",
        "https://evil.instagram.com/reel/OwnedIG01/",
        "https://instagram.com@127.0.0.1/reel/OwnedIG01/",
        "https://user:secret@instagram.com/p/OwnedIG01/",
        "https://instagram.com:444/p/OwnedIG01/",
        "https://instagram.com/p/OwnedIG01/extra",
        "https://instagram.com/p/OwnedIG01%2fextra/",
        "https://instagram.com/p/OwnedIG\n01/",
        "https://instagram.com/p/" + "a" * 65,
        "https://instagram.com/creator/",
        "https://instagram.com/creator/reels/",
        "https://instagram.com/stories/creator/123/",
        "https://instagram.com/share/reel/Share123/",
        "https://instagram.com/reels/audio/123/",
        "https://instagram.com/explore/",
    ],
)
def test_instagram_only_accepts_safe_individual_permalinks(url):
    with pytest.raises(ServiceError):
        sources.validate_url(url)


@pytest.fixture
def instagram(monkeypatch, media_server):
    state = {
        "changed_id": False,
        "changed_quality": False,
        "changed_source": False,
        "wrong_dimensions": False,
        "silent": False,
        "split": False,
        "carousel": False,
        "unknown_geometry": False,
        "missing_audio": False,
        "error": None,
    }

    def extract(self, url):
        assert url in {REEL, POST}
        if state["error"]:
            raise ExtractorError(state["error"], expected=True)
        if state["carousel"]:

            def entries():
                raise AssertionError("Carousel children must never be processed")
                yield

            return {"id": "OwnedIG01", "_type": "playlist", "entries": entries()}
        video = {
            "format_id": "changed-id" if state["changed_id"] else "video-0",
            "url": media_server
            + ("/video.mp4" if state["silent"] or state["split"] else "/sample.mp4"),
            "ext": "mp4",
            "vcodec": "h264",
            "acodec": "none" if state["silent"] or state["split"] else "aac",
            "width": 720 if state["wrong_dimensions"] or state["changed_quality"] else 160,
            "height": 90,
            "fps": 12,
        }
        formats = [video]
        if state["unknown_geometry"]:
            video.pop("width")
            video.pop("height")
        if state["split"] and not state["missing_audio"]:
            formats.append(
                {
                    "format_id": "audio-0",
                    "url": media_server + "/audio.m4a",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "aac",
                    "abr": 70,
                }
            )
        return {
            "id": "DifferentPost" if state["changed_source"] else "OwnedIG01",
            "title": "Owned Instagram video (local fixture)",
            "uploader": "Owned creator",
            "duration": 1.2,
            "thumbnail": "https://scontent.cdninstagram.com/owned.jpg?token=example",
            "formats": deepcopy(formats),
        }

    monkeypatch.setattr(InstagramIE, "_real_initialize", lambda self: None)
    monkeypatch.setattr(InstagramIE, "_real_extract", extract)
    return state


def analyze(client, store, url=REEL):
    response = client.post("/api/analyze", json={"url": url + "?igsh=private-tracking"})
    assert response.status_code == 202
    task = work(store)
    assert task["state"] == "completed", task
    return task


def download(client, store, task, profile="original"):
    choice = next(c for c in task["result"]["choices"] if c["kind"] == "video")
    response = client.post(
        "/api/downloads",
        json={"analysis_id": task["id"], "choice_id": choice["id"], "profile": profile},
    )
    assert response.status_code == 202, response.text
    return work(store)


@pytest.mark.parametrize("url", [REEL, POST])
@pytest.mark.parametrize("profile", ["original", "compatible", "mp3"])
def test_instagram_real_queue_to_verified_file(client, store, instagram, url, profile):
    task = analyze(client, store, url)
    analysis = task["result"]
    assert analysis["platform"] == "Instagram" and analysis["kind"] == "video"
    assert analysis["url"] == url
    assert "private-tracking" not in str(analysis)
    assert "127.0.0.1" not in str(analysis)
    finished = download(client, store, task, profile)
    assert finished["state"] == "completed", finished
    asset_id = finished["result"]["asset_id"]
    asset = client.get(f"/api/assets/{asset_id}").json()
    metadata = asset["metadata"]
    assert metadata["has_audio"]
    if profile == "mp3":
        assert metadata["kind"] == "audio" and metadata["audio_codec"] == "mp3"
    else:
        assert (metadata["width"], metadata["height"]) == (160, 90)
        assert metadata["video_codec"] == "h264" and metadata["audio_codec"] == "aac"
    assert client.get(f"/api/assets/{asset_id}/file").status_code == 200


@pytest.mark.parametrize("profile", ["original", "mp3"])
def test_instagram_split_video_audio_uses_exact_streams(client, store, instagram, profile):
    instagram["split"] = True
    task = analyze(client, store)
    assert (
        next(c for c in task["result"]["choices"] if c["kind"] == "video")["operation"] == "merge"
    )
    finished = download(client, store, task, profile)
    assert finished["state"] == "completed", finished
    metadata = store.asset(finished["result"]["asset_id"])["metadata"]
    assert metadata["has_audio"]
    assert metadata["kind"] == ("audio" if profile == "mp3" else "video")


def test_instagram_format_ids_may_change_without_changing_quality(client, store, instagram):
    task = analyze(client, store)
    instagram["changed_id"] = True
    finished = download(client, store, task)
    assert finished["state"] == "completed", finished
    assert finished["result"]["source_format_ids"] == ["changed-id"]


@pytest.mark.parametrize("changed_id", [False, True])
def test_instagram_unknown_geometry_requires_the_original_format_id(
    client, store, instagram, changed_id
):
    instagram["unknown_geometry"] = True
    task = analyze(client, store)
    instagram["changed_id"] = changed_id
    finished = download(client, store, task)
    if changed_id:
        assert finished["state"] == "failed" and finished["error"]["code"] == "format_unavailable"
    else:
        assert finished["state"] == "completed", finished


def test_instagram_missing_selected_audio_does_not_publish_a_silent_video(client, store, instagram):
    instagram["split"] = True
    task = analyze(client, store)
    instagram["missing_audio"] = True
    finished = download(client, store, task)
    assert finished["state"] == "failed" and finished["error"]["code"] == "format_unavailable"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("changed_quality", "format_unavailable"),
        ("changed_source", "source_changed"),
        ("carousel", "source_changed"),
    ],
)
def test_instagram_refresh_never_switches_quality_post_or_carousel(
    client, store, instagram, change, code
):
    task = analyze(client, store)
    instagram[change] = True
    finished = download(client, store, task)
    assert finished["state"] == "failed" and finished["error"]["code"] == code, finished
    assert not list((store.config.data_dir / "files" / finished["id"]).glob("**/*"))


def test_instagram_verifies_actual_dimensions(client, store, instagram):
    instagram["wrong_dimensions"] = True
    task = analyze(client, store)
    finished = download(client, store, task)
    assert finished["state"] == "failed" and finished["error"]["code"] == "quality_mismatch"


def test_instagram_silent_video_does_not_offer_mp3(client, store, instagram):
    instagram["silent"] = True
    task = analyze(client, store)
    assert not task["result"]["choices"][0]["has_audio"]
    response = client.post(
        "/api/downloads",
        json={"analysis_id": task["id"], "choice_id": "option_0", "profile": "mp3"},
    )
    assert response.status_code == 400 and response.json()["detail"]["code"] == "no_audio"
    assert download(client, store, task)["state"] == "completed"


def test_unexpected_raw_collection_is_not_expanded_without_publication_metadata(
    client, store, instagram
):
    instagram["carousel"] = True
    client.post("/api/analyze", json={"url": POST})
    task = work(store)
    assert task["state"] == "failed" and task["error"]["code"] == "source_changed"


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("There is no video in this post", "instagram_post_unreadable"),
        ("The webpage request was redirected to the login page", "access_required"),
        ("You have exceeded the rate-limit for accessing posts anonymously", "source_rate_limited"),
        ("HTTP Error 429: Too Many Requests", "source_rate_limited"),
        ("This content is not available", "source_unavailable"),
    ],
)
def test_instagram_source_failures_have_private_actionable_errors(
    client, store, instagram, message, code
):
    instagram["error"] = message + " https://opaque.example/?token=secret /srv/owner-session.txt"
    client.post("/api/analyze", json={"url": REEL})
    task = work(store)
    assert task["state"] == "failed" and task["error"]["code"] == code, task
    assert "opaque.example" not in str(task["error"]) and "secret" not in str(task["error"])
    assert "owner-session.txt" not in str(task["error"])


@pytest.mark.parametrize(
    "thumbnail",
    [
        "http://scontent.cdninstagram.com/image.jpg",
        "https://cdninstagram.com.evil.example/i.jpg",
        "https://evil.example/i.jpg",
    ],
)
def test_instagram_artwork_is_host_scoped(client, store, instagram, monkeypatch, thumbnail):
    original = InstagramIE._real_extract

    def extract(self, url):
        return original(self, url) | {"thumbnail": thumbnail}

    monkeypatch.setattr(InstagramIE, "_real_extract", extract)
    assert analyze(client, store)["result"]["thumbnail"] is None
