"""New source contracts plus real yt-dlp/media delivery using owned local fixtures."""

import io
from copy import deepcopy
from urllib.error import HTTPError

import pytest
import yt_dlp
from conftest import work
from service import sources
from service.errors import ServiceError
from yt_dlp.extractor.common import InfoExtractor

TRACK = "https://soundcloud.com/test-artist/owned-track"
VIDEO = "https://www.tiktok.com/@test.creator/video/7100000000000000001"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://m.soundcloud.com/test-artist/owned-track/?si=tracking", TRACK),
        ("https://www.soundcloud.com/test-artist/owned-track#t=0:10", TRACK),
        ("http://tiktok.com/@test.creator/video/7100000000000000001?is_from_webapp=1", VIDEO),
        (VIDEO + "/?share_app_id=123", VIDEO),
        ("https://vm.tiktok.com/ZTest/?tracking=1", "https://vm.tiktok.com/ZTest/"),
        ("https://vt.tiktok.com/ZTest", "https://vt.tiktok.com/ZTest/"),
        ("https://tiktok.com/t/ZTest?x=1", "https://www.tiktok.com/t/ZTest/"),
        ("https://on.soundcloud.com/Share123/?si=tracking", "https://on.soundcloud.com/Share123"),
    ],
)
def test_source_canonicalization(url, expected):
    assert sources.validate_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://soundcloud.com.evil.example/artist/track",
        "https://evil.soundcloud.com/artist/track",
        "https://soundcloud.com@127.0.0.1/artist/track",
        "https://soundcloud.com:444/artist/track",
        "https://soundcloud.com/artist/%2e%2e",
        "https://soundcloud.com/artist/track/s-secret",
        "https://soundcloud.com/artist/track?secret_token=secret",
        "https://soundcloud.com/artist/sets/album",
        "https://soundcloud.com/artist/sets",
        "https://soundcloud.com/artist/tracks",
        "https://soundcloud.com/stations/track",
        "https://soundcloud.com/discover/sets",
        "https://soundcloud.com/artist",
        "https://on.soundcloud.com/one/two",
        "https://tiktok.com.evil.example/@test/video/1",
        "https://evil.tiktok.com/@test/video/1",
        "https://user:secret@tiktok.com/@test/video/1",
        "https://tiktok.com/@test/video/1/extra",
        "https://tiktok.com/@test/video/1%2fextra",
        "https://tiktok.com/@test/video/\n1",
        "https://www.tiktok.com/@test/collection/album-1",
        "https://www.tiktok.com/music/song-1",
    ],
)
def test_new_sources_reject_unsafe_and_collection_urls(url):
    with pytest.raises(ServiceError):
        sources.validate_url(url)


def test_live_has_specific_next_steps():
    for path, code in (("live", "live_unsupported"),):
        with pytest.raises(ServiceError) as failure:
            sources.validate_url("https://www.tiktok.com/@test/" + path)
        assert failure.value.code == code


def test_source_network_block_is_actionable_and_private():
    error = sources.extractor_error(
        Exception(
            "Your IP address is blocked from accessing this post https://private.example?token=secret"
        )
    )
    assert error.code == "network_blocked"
    assert "secret" not in error.message and "private.example" not in error.message


class Redirects:
    def __init__(self, hops):
        self.hops, self.calls = hops, []

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        assert request.method == "HEAD" and timeout <= 15
        location = self.hops[request.full_url]
        raise HTTPError(request.full_url, 302, "Found", {"Location": location}, io.BytesIO())


def test_short_links_are_bounded_and_stop_before_the_final_item(monkeypatch):
    first, second = "https://vm.tiktok.com/First/", "https://www.tiktok.com/t/Second/"
    redirects = Redirects({first: second, second: VIDEO + "?tracking=1"})
    monkeypatch.setattr(sources, "build_opener", lambda *args: redirects)
    assert sources.resolve_url(first) == VIDEO
    assert redirects.calls == [first, second]


@pytest.mark.parametrize(
    "target",
    [
        "http://127.0.0.1/private",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "https://evil.tiktok.com/@test/video/1",
        "https://www.tiktok.com/@test/live",
        TRACK,
        "https://vm.tiktok.com/Loop/",
    ],
)
def test_short_links_never_follow_unapproved_redirects(monkeypatch, target):
    first = "https://vm.tiktok.com/Loop/"
    redirects = Redirects({first: target})
    monkeypatch.setattr(sources, "build_opener", lambda *args: redirects)
    with pytest.raises(ServiceError) as failure:
        sources.resolve_url(first)
    assert failure.value.code == "short_link_error"
    assert redirects.calls == [first]


def test_share_redirect_limit_and_private_error_redaction(monkeypatch):
    chain = {
        f"https://vt.tiktok.com/Hop{i}/": f"https://vt.tiktok.com/Hop{i + 1}/" for i in range(6)
    }
    redirects = Redirects(chain)
    monkeypatch.setattr(sources, "build_opener", lambda *args: redirects)
    with pytest.raises(ServiceError):
        sources.resolve_url("https://vt.tiktok.com/Hop0/")
    assert len(redirects.calls) == 5
    redirects.hops["https://vt.tiktok.com/Hop4/"] = VIDEO
    redirects.calls.clear()
    assert sources.resolve_url("https://vt.tiktok.com/Hop0/") == VIDEO
    assert len(redirects.calls) == 5

    def unavailable(*args, **kwargs):
        raise OSError("private proxy/password/path")

    monkeypatch.setattr(redirects, "open", unavailable)
    with pytest.raises(ServiceError) as failure:
        sources.resolve_url("https://vt.tiktok.com/Hop0/")
    assert "password" not in failure.value.message


def audio_format(format_id="http_aac_160k", **extra):
    return {
        "format_id": format_id,
        "ext": "m4a",
        "vcodec": "none",
        "acodec": "aac",
        "abr": 160,
        **extra,
    }


def test_soundcloud_audio_metadata_and_preview_gate():
    info = {
        "id": "123",
        "title": "Owned track",
        "thumbnail": "https://i1.sndcdn.com/art.jpg",
        "formats": [audio_format(), audio_format("hls_mp3_128_preview")],
    }
    result = sources.normalize(info, TRACK)
    assert result["platform"] == "SoundCloud" and result["kind"] == "audio"
    assert result["thumbnail"] == info["thumbnail"]
    assert len(result["choices"]) == 1
    assert result["choices"][0]["audio_bitrate"] == 160
    assert result["choices"][0]["height"] is None
    info["formats"] = [audio_format("hls_mp3_128_preview")]
    with pytest.raises(ServiceError) as failure:
        sources.normalize(info, TRACK)
    assert failure.value.code == "preview_only"


def test_tiktok_never_substitutes_music_for_clip_audio():
    result = sources.normalize(
        {
            "formats": [
                {
                    "format_id": "play",
                    "ext": "mp4",
                    "vcodec": "h264",
                    "acodec": "aac",
                    "width": 720,
                    "height": 1280,
                    "format_note": None,
                },
                {"format_id": "silent", "ext": "mp4", "vcodec": "h265", "acodec": "none"},
                {"format_id": "unplayable", "ext": "mp4", "vcodec": "bytevc2", "acodec": "aac"},
                {
                    "format_id": "download",
                    "ext": "mp4",
                    "vcodec": "h264",
                    "acodec": "aac",
                    "format_note": "watermarked",
                },
                audio_format("music"),
            ]
        },
        VIDEO,
    )
    assert [c["selector"] for c in result["choices"]] == ["play", "silent+play"]
    assert result["choices"][0]["format_note"] is None
    assert result["choices"][0]["width"] == 720
    assert result["choices"][1]["has_audio"]
    assert result["choices"][1]["operation"] == "merge"
    assert result["choices"][1]["audio_source_kind"] == "video"


@pytest.mark.parametrize(
    "thumbnail",
    [
        "http://i1.sndcdn.com/x",
        "https://i1.sndcdn.com.evil.example/x",
        "https://user:secret@i1.sndcdn.com/x",
        "https://i1.sndcdn.com:444/x",
        "https://127.0.0.1/x",
        "https://p16.tiktokcdn.com/x",
    ],
)
def test_soundcloud_artwork_is_platform_scoped(thumbnail):
    assert (
        sources.normalize({"thumbnail": thumbnail, "formats": [audio_format()]}, TRACK)["thumbnail"]
        is None
    )


def test_only_individual_source_extractors_are_loaded(config):
    with yt_dlp.YoutubeDL(sources.options(config)) as ydl:
        assert set(ydl._ies) == {"Youtube", "Soundcloud", "TikTok"}


@pytest.fixture
def new_source_extractor(monkeypatch, media_server):
    original = yt_dlp.YoutubeDL

    class ControlledSourceIE(InfoExtractor):
        IE_NAME = "owned-source-fixture"
        _VALID_URL = r"https://(?:soundcloud\.com/test-artist/(?P<track>owned-track)|www\.tiktok\.com/@test\.creator/video/(?P<id>7100000000000000001))"
        changed = False
        wrong_dimensions = False

        def _real_extract(self, url):
            is_track = url == TRACK
            fmt = (
                audio_format(url=media_server + "/audio.m4a")
                if is_track
                else {
                    "format_id": "h264_90p_500000",
                    "url": media_server + "/sample.mp4",
                    "ext": "mp4",
                    "vcodec": "h264",
                    "acodec": "aac",
                    "width": 720 if self.wrong_dimensions else 160,
                    "height": 90,
                }
            )
            if self.changed:
                fmt["format_id"] = "different_format"
            return {
                "id": "track123" if is_track else "7100000000000000001",
                "title": "Owned fixture",
                "duration": 1.2,
                "formats": [deepcopy(fmt)],
            }

    def factory(opts):
        ydl = original(opts, auto_init=False)
        ydl.add_info_extractor(ControlledSourceIE())
        return ydl

    monkeypatch.setattr(sources.yt_dlp, "YoutubeDL", factory)
    return ControlledSourceIE


@pytest.mark.parametrize("url", [TRACK, VIDEO])
@pytest.mark.parametrize("profile", ["original", "mp3"])
def test_new_sources_queue_to_verified_file(client, store, new_source_extractor, url, profile):
    response = client.post("/api/analyze", json={"url": url + "?tracking=ignored"})
    assert response.status_code == 202
    analysis = work(store)
    assert analysis["state"] == "completed", analysis
    result = analysis["result"]
    assert result["url"] == url
    assert result["platform"] == ("SoundCloud" if url == TRACK else "TikTok")
    assert "http://127.0.0.1" not in str(result)
    response = client.post(
        "/api/downloads",
        json={
            "analysis_id": analysis["id"],
            "choice_id": result["choices"][0]["id"],
            "profile": profile,
        },
    )
    assert response.status_code == 202
    finished = work(store)
    assert finished["state"] == "completed", finished
    asset_id = finished["result"]["asset_id"]
    asset = client.get(f"/api/assets/{asset_id}").json()
    assert asset["metadata"]["has_audio"]
    assert asset["metadata"]["kind"] == ("audio" if url == TRACK or profile == "mp3" else "video")
    if profile == "mp3":
        assert asset["metadata"]["audio_codec"] == "mp3"
    delivery = client.get(f"/api/assets/{asset_id}/file")
    assert delivery.status_code == 200 and len(delivery.content) > 1000


def test_share_resolution_runs_in_worker_not_api(client, store, monkeypatch, new_source_extractor):
    short = "https://on.soundcloud.com/Share123"
    redirects = Redirects({short: TRACK})
    monkeypatch.setattr(sources, "build_opener", lambda *args: redirects)
    task = client.post("/api/analyze", json={"url": short}).json()
    assert task["state"] == "queued" and not redirects.calls
    assert task["title"] == "Analyze SoundCloud link"
    assert work(store)["result"]["url"] == TRACK
    assert redirects.calls == [short]


def test_new_source_exact_format_and_dimensions(client, store, new_source_extractor):
    for changed, wrong_dimensions, error in (
        (True, False, "format_unavailable"),
        (False, True, "quality_mismatch"),
    ):
        new_source_extractor.changed = False
        new_source_extractor.wrong_dimensions = wrong_dimensions
        client.post("/api/analyze", json={"url": VIDEO})
        analysis = work(store)
        new_source_extractor.changed = changed
        client.post("/api/downloads", json={"analysis_id": analysis["id"], "choice_id": "option_0"})
        finished = work(store)
        assert finished["state"] == "failed" and finished["error"]["code"] == error


def test_source_settings_and_csp(client):
    response = client.get("/api/settings")
    platforms = {p["name"]: p["status"] for p in response.json()["platforms"]}
    assert "public unprotected tracks" in platforms["SoundCloud"]
    assert "individual videos" in platforms["TikTok"]
    assert platforms["Instagram"] == "planned"
    csp = response.headers["Content-Security-Policy"]
    assert "https://*.sndcdn.com" in csp and "https://*.tiktokcdn.com" in csp
    assert "https:" not in csp.split("img-src", 1)[1].split(";", 1)[0].split()
