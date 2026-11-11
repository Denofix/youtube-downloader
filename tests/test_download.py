import pytest
import yt_dlp
from service import media, sources
from service.errors import ServiceError
from yt_dlp.extractor.common import InfoExtractor

URL = "https://www.youtube.com/watch?v=BaW_jenozKc"


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1",
        "https://youtube.com.evil.example/watch?v=BaW_jenozKc",
        "https://evil.youtube.com/watch?v=BaW_jenozKc",
        "https://user:secret@youtube.com/watch?v=BaW_jenozKc",
        "https://youtube.com:444/watch?v=BaW_jenozKc",
        "https://youtube.com/playlist?list=x",
        "https://youtu.be/BaW_jenozKc/extra",
        "https://youtu.be/x",
    ],
)
def test_reject_unsafe_or_non_video_urls(url):
    with pytest.raises(ServiceError):
        sources.validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/BaW_jenozKc?si=tracking",
        "https://www.youtube.com/shorts/BaW_jenozKc",
        URL + "&list=ignored&token=secret",
    ],
)
def test_canonical_video_url(url):
    assert sources.validate_url(url) == URL


def test_real_choices_not_invented_quality_or_size():
    info = {
        "id": "x",
        "title": "Test",
        "formats": [
            {
                "format_id": "v",
                "ext": "mp4",
                "height": 90,
                "vcodec": "h264",
                "acodec": "none",
                "filesize": 100,
            },
            {
                "format_id": "a",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "aac",
                "filesize_approx": 50,
            },
            {"format_id": "unknown", "ext": "mp4", "vcodec": "h264", "acodec": "aac"},
        ],
    }
    result = sources.normalize(info, URL)
    assert result["choices"][0]["selector"] == "v+a"
    assert result["choices"][0]["source_format_ids"] == ["v", "a"]
    assert result["choices"][0]["size_kind"] == "approximate"
    assert result["choices"][0]["size"] == 150
    assert result["choices"][-1]["size"] is None
    assert result["choices"][-1]["height"] is None


@pytest.fixture
def controlled_extractor(monkeypatch, media_server):
    original = yt_dlp.YoutubeDL

    class ControlledYoutubeIE(InfoExtractor):
        IE_NAME = "controlled-youtube"
        _VALID_URL = r"https://www\.youtube\.com/watch\?v=(?P<id>[A-Za-z0-9_-]+)"
        omit_video = False

        def _real_extract(self, url):
            formats = [
                {
                    "format_id": "136",
                    "url": media_server + "/video.mp4",
                    "ext": "mp4",
                    "height": 90,
                    "width": 160,
                    "vcodec": "h264",
                    "acodec": "none",
                },
                {
                    "format_id": "140",
                    "url": media_server + "/audio.m4a",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "aac",
                    "abr": 128,
                },
            ]
            return {
                "id": "BaW_jenozKc",
                "title": "Owned test clip",
                "formats": formats[1:] if self.omit_video else formats,
            }

    def factory(opts):
        ydl = original(opts, auto_init=False)
        ydl.add_info_extractor(ControlledYoutubeIE())
        return ydl

    monkeypatch.setattr(sources.yt_dlp, "YoutubeDL", factory)
    return ControlledYoutubeIE


@pytest.mark.parametrize("profile", ["original", "mp3"])
def test_actual_tool_download_merge_and_audio(config, tmp_path, controlled_extractor, profile):
    result = sources.analyze(URL, config)
    choice = next(c for c in result["choices"] if c["kind"] == "video")
    directory = tmp_path / "download"
    directory.mkdir()
    events = []
    path = sources.download(
        result,
        choice,
        profile,
        192,
        directory,
        config,
        lambda operation, *args: events.append(operation),
    )
    metadata = media.verify(path)
    assert metadata["has_audio"]
    assert metadata["kind"] == ("audio" if profile == "mp3" else "video")
    assert path.suffix == (".mp3" if profile == "mp3" else ".mp4")
    if profile == "original":
        assert metadata["height"] == 90
        assert "merging" in events


def test_missing_format_fails_without_fallback(config, tmp_path, controlled_extractor):
    result = sources.analyze(URL, config)
    choice = next(c for c in result["choices"] if c["kind"] == "video")
    controlled_extractor.omit_video = True
    with pytest.raises(ServiceError, match="no longer available"):
        sources.download(result, choice, "original", 192, tmp_path, config, lambda *args: None)


def test_tool_errors_never_reveal_secrets():
    error = sources.extractor_error(Exception("login cookie token=TOP_SECRET /srv/cookies.txt"))
    assert error.code == "access_required"
    assert "TOP_SECRET" not in error.message and "/srv" not in error.message
    assert (
        sources.extractor_error(
            Exception("Postprocessing: Invalid data found when processing input")
        ).code
        == "invalid_source_media"
    )
