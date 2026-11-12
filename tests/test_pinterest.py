"""Pinterest native API shapes, bounded share hops and actual owned file delivery."""

import hashlib
import io
import json
from copy import deepcopy
from urllib.error import HTTPError

import pytest
from conftest import work
from PIL import Image
from service import photos, sources
from service.errors import ServiceError
from service.store import Store
from yt_dlp.extractor.pinterest import PinterestIE
from yt_dlp.utils import ExtractorError

URL = "https://www.pinterest.com/pin/123456789/"


@pytest.fixture
def pin(monkeypatch, media_server):
    state = {
        "calls": 0,
        "error": None,
        "data": {
            "id": "123456789",
            "privacy": "public",
            "title": "Owned Pinterest / .. pin",
            "pinner": {"full_name": "Owned creator"},
            "images": {
                "orig": {
                    "url": media_server + "/sample.jpg?SECRET=private",
                    "width": 50,
                    "height": 30,
                }
            },
        },
    }

    def call(self, resource, video_id, options):
        assert resource == "Pin" and video_id == "123456789"
        state["calls"] += 1
        if state["error"]:
            raise ExtractorError(state["error"], expected=True)
        return {"status": "success", "data": deepcopy(state["data"])}

    monkeypatch.setattr(PinterestIE, "_real_initialize", lambda self: None)
    monkeypatch.setattr(PinterestIE, "_call_api", call)
    real = photos.check_media_url
    monkeypatch.setattr(
        photos,
        "check_media_url",
        lambda url, platform="TikTok": (
            url
            if isinstance(url, str) and url.startswith(media_server + "/")
            else real(url, platform)
        ),
    )
    return state


def video(pin, media_server, silent=False):
    pin["data"]["videos"] = {
        "video_list": {
            "V_720P": {
                "url": media_server + ("/video.mp4" if silent else "/sample.mp4") + "?SECRET=video",
                "width": 160,
                "height": 90,
                "duration": 1200,
            }
        }
    }


def analyze(client, store):
    assert client.post("/api/analyze", json={"url": URL + "?tracking=discarded"}).status_code == 202
    task = work(store)
    assert task["state"] == "completed", task
    encoded = json.dumps(client.get("/api/tasks/" + task["id"]).json())
    assert "SECRET" not in encoded and "127.0.0.1" not in encoded and "_images" not in encoded
    return task


@pytest.mark.parametrize(
    "url",
    [
        "https://pinterest.com/pin/123456789",
        "http://www.pinterest.ca/pin/123456789/?x=1",
        "https://ru.pinterest.com/pin/pretty-title--123456789/",
        "https://pinterest.co.uk/pin/123456789/sent/?sender=private",
        "https://jp.pinterest.com/pin/123456789/#private",
        "https://www.pinterest.com/pin/123456789/",
    ],
)
def test_pin_permalink_canonicalization(url):
    assert sources.validate_url(url) == URL
    assert sources.platform_for(url) == "Pinterest"


@pytest.mark.parametrize(
    "url",
    [
        "https://pinterest.com/creator/board/",
        "https://pinterest.com/creator/",
        "https://pinterest.com/search/pins/",
        "https://www.pinterest.com/pin/abc/",
        "https://pinterest.com/pin/123456789/extra",
        "https://pinterest.com.evil.example/pin/123/",
        "https://evil.pinterest.com/pin/123/",
        "https://pinterest.com@127.0.0.1/pin/123/",
        "https://pinterest.com:444/pin/123/",
        "https://api.pinterest.com/url_shortener/Owned/redirect/",
        "https://pin.it/a/b",
        "https://www.pin.it/Owned",
        "https://pin.it/Owned\\private",
        "https://pin.it:444/Owned",
    ],
)
def test_only_one_approved_pin_or_share_link(url):
    with pytest.raises(ServiceError):
        sources.validate_url(url)


def test_short_link_checks_native_api_hop_and_final_pin_before_request(monkeypatch):
    first, middle = (
        "https://pin.it/Owned",
        "https://api.pinterest.com/url_shortener/Owned/redirect/",
    )
    hops = {first: middle, middle: URL.rstrip("/") + "/sent/?sender=SECRET"}
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            raise HTTPError(
                request.full_url, 302, "Found", {"Location": hops[request.full_url]}, io.BytesIO()
            )

    monkeypatch.setattr(sources, "build_opener", lambda *args: Opener())
    assert sources.resolve_url(first + "?tracking=discarded") == URL
    assert calls == [first, middle]


@pytest.mark.parametrize(
    "target",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "https://api.pinterest.com/arbitrary/path",
        "http://api.pinterest.com/url_shortener/X/redirect/",
        "https://api.pinterest.com/url_shortener/X/redirect/?url=https://evil.example",
        "https://api.pinterest.com/url_shortener/%2e%2e/redirect/",
        "https://www.pinterest.com/creator/board/",
        "https://youtu.be/BaW_jenozKc",
        "https://pin.it/Owned",
    ],
)
def test_pin_share_never_requests_unapproved_hops_or_loops(monkeypatch, target):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            raise HTTPError(request.full_url, 302, "Found", {"Location": target}, io.BytesIO())

    monkeypatch.setattr(sources, "build_opener", lambda *args: Opener())
    with pytest.raises(ServiceError) as error:
        sources.resolve_url("https://pin.it/Owned")
    assert error.value.code == "short_link_error" and calls == ["https://pin.it/Owned"]


@pytest.mark.parametrize("animated", [False, True])
def test_original_pin_bytes_preview_retention_restart_and_conversion(
    client, store, pin, files, media_server, animated
):
    filename = "animated.gif" if animated else "sample.jpg"
    if animated:
        pin["data"]["embed"] = {"type": "gif", "src": media_server + "/animated.gif"}
    dims = (64, 48) if animated else (50, 30)
    pin["data"]["images"]["orig"].update(
        url=media_server + "/" + filename, width=dims[0], height=dims[1]
    )
    task = analyze(client, store)
    item = task["result"]["items"][0]
    assert (item["width"], item["height"]) == dims
    assert item["kind"] == ("animation" if animated else "image")
    assert client.get(f"/api/assets/{item['preview_asset_id']}/preview").status_code == 200
    assert (
        client.post(
            "/api/photo-downloads", json={"analysis_id": task["id"], "item_ids": [item["id"]]}
        ).status_code
        == 202
    )
    result = work(Store(store.config))
    assert result["state"] == "completed", result
    asset_id = result["result"]["files"][0]["asset_id"]
    response = client.get(f"/api/assets/{asset_id}/file")
    assert response.content == (files / filename).read_bytes()
    assert hashlib.sha256(response.content).hexdigest() == item["sha256"]
    assert store.asset(asset_id)["metadata"]["kind"] == item["kind"]
    if animated:
        with Image.open(io.BytesIO(response.content)) as image:
            assert image.n_frames == 3
        assert result["result"]["files"][0]["name"].endswith(".gif")
    output = "mp4" if animated else "png"
    assert (
        client.post(
            "/api/conversions", json={"asset_id": asset_id, "parameters": {"output": output}}
        ).status_code
        == 202
    )
    converted = work(store)
    assert converted["state"] == "completed", converted
    assert pin["calls"] == 1


@pytest.mark.parametrize("profile", ["original", "mp3"])
@pytest.mark.parametrize("layout", ["direct", "single-page"])
def test_native_progressive_video_and_audio_unknown_are_delivered_with_real_streams(
    client, store, pin, media_server, profile, layout
):
    video(pin, media_server)
    if layout == "single-page":
        pin["data"]["story_pin_data"] = {
            "page_count": 1,
            "pages": [{"blocks": [{"video": pin["data"].pop("videos")}]}],
        }
    task = analyze(client, store)
    choice = task["result"]["choices"][0]
    assert choice["width"] == 160 and choice["audio_unknown"] is True
    assert choice["audio_codec"] == "unknown"
    assert (
        client.post(
            "/api/downloads",
            json={
                "analysis_id": task["id"],
                "choice_id": choice["id"],
                "profile": profile,
                "bitrate": 128,
            },
        ).status_code
        == 202
    )
    result = work(store)
    assert result["state"] == "completed", result
    asset = store.asset(result["result"]["asset_id"])
    assert asset["metadata"]["has_audio"] is True
    assert asset["metadata"]["kind"] == ("audio" if profile == "mp3" else "video")
    assert client.get(f"/api/assets/{asset['id']}/file").status_code == 200
    assert pin["calls"] == 2


def test_silent_progressive_pin_keeps_original_without_inventing_audio(
    client, store, pin, media_server
):
    video(pin, media_server, True)
    task = analyze(client, store)
    choice = task["result"]["choices"][0]
    assert choice["audio_unknown"]
    assert (
        client.post(
            "/api/downloads", json={"analysis_id": task["id"], "choice_id": choice["id"]}
        ).status_code
        == 202
    )
    result = work(store)
    assert result["state"] == "completed", result
    assert store.asset(result["result"]["asset_id"])["metadata"]["has_audio"] is False


@pytest.mark.parametrize("change", ["identity", "quality", "format", "image"])
def test_refreshed_video_never_falls_back_to_other_pin_or_quality(
    client, store, pin, media_server, change
):
    video(pin, media_server)
    task = analyze(client, store)
    choice = task["result"]["choices"][0]
    if change == "identity":
        pin["data"]["id"] = "999"
    elif change == "quality":
        pin["data"]["videos"]["video_list"]["V_720P"]["width"] = 320
    elif change == "image":
        pin["data"].pop("videos")
    else:
        pin["data"]["videos"]["video_list"]["new-ID"] = pin["data"]["videos"]["video_list"].pop(
            "V_720P"
        )
    assert (
        client.post(
            "/api/downloads", json={"analysis_id": task["id"], "choice_id": choice["id"]}
        ).status_code
        == 202
    )
    result = work(store)
    assert result["state"] == "failed" and result["result"] is None
    assert not list((store.config.data_dir / "files" / result["id"]).glob("*"))


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"privacy": "secret"}, "access_required"),
        ({"embed": {"src": "https://evil.example/player"}}, "pinterest_external_embed"),
        (
            {"story_pin_data": {"page_count": 2, "pages": [{}, {}]}},
            "pinterest_multi_item_unsupported",
        ),
        ({"carousel_data": {"items": [{}, {}]}}, "pinterest_multi_item_unsupported"),
        ({"is_video": True}, "no_formats"),
        ({"story_pin_data": {"pages": [{"blocks": [{"video": {"id": "1"}}]}]}}, "no_formats"),
        ({"images": {"orig": {"url": "http://127.0.0.1/private"}}}, "photo_source_unavailable"),
        (
            {
                "images": {
                    "orig": {
                        "url": "https://i.pinimg.com/image.jpg",
                        "width": 10000,
                        "height": 10000,
                    }
                }
            },
            "image_limit",
        ),
    ],
)
def test_unsupported_pin_contents_have_specific_errors_without_cover_fallback(
    client, store, pin, change, code
):
    pin["data"].update(change)
    assert client.post("/api/analyze", json={"url": URL}).status_code == 202
    task = work(store)
    assert task["state"] == "failed" and task["error"]["code"] == code, task
    assert task["result"] is None


def test_pin_error_diagnostics_do_not_expose_cookie_path_or_source_tokens(client, store, pin):
    pin["error"] = (
        "HTTP Error 429 rate limit at https://private.example?SECRET=token /srv/owner-cookie.txt"
    )
    assert client.post("/api/analyze", json={"url": URL}).status_code == 202
    task = work(store)
    assert task["error"]["code"] == "source_rate_limited"
    public = json.dumps(client.get("/api/tasks/" + task["id"]).json())
    assert "SECRET" not in public and "owner-cookie" not in public


def test_declared_gif_never_saves_a_still_cover(client, store, pin):
    pin["data"]["embed"] = {"type": "gif", "src": "https://i.pinimg.com/animation.gif"}
    assert client.post("/api/analyze", json={"url": URL}).status_code == 202
    task = work(store)
    assert task["state"] == "failed" and task["error"]["code"] == "invalid_photo"


def test_gif_frame_limit_is_enforced_before_publishing(client, store, pin, files, media_server):
    frames = [Image.new("RGB", (8, 8), (i % 256, (i // 256) * 70, 0)) for i in range(501)]
    frames[0].save(files / "too-many.gif", save_all=True, append_images=frames[1:], duration=20)
    pin["data"]["images"]["orig"].update(url=media_server + "/too-many.gif", width=8, height=8)
    assert client.post("/api/analyze", json={"url": URL}).status_code == 202
    task = work(store)
    assert task["state"] == "failed" and task["error"]["code"] == "image_limit"
