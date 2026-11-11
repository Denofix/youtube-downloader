import array
import json
import subprocess

import pytest
import yt_dlp
from conftest import work
from service import media, sources
from service.errors import ServiceError
from yt_dlp.extractor.common import InfoExtractor

URL = "https://www.tiktok.com/@test.creator/video/7100000000000000001"


@pytest.fixture
def hevc_source(files, media_server, monkeypatch):
    source = files / "portrait-hevc.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=96x160:r=12",
            "-t",
            "1.2",
            "-an",
            "-c:v",
            "libx265",
            "-pix_fmt",
            "yuv420p10le",
            "-x265-params",
            "pools=1:frame-threads=1:log-level=error",
            "-tag:v",
            "hvc1",
            "-threads",
            "2",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-i",
            str(files / "sample.mp4"),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c",
            "copy",
            str(files / "portrait-muxed.mp4"),
        ],
        check=True,
        capture_output=True,
    )
    original = yt_dlp.YoutubeDL

    class OwnedTikTokIE(InfoExtractor):
        _VALID_URL = r"https://www\.tiktok\.com/@test\.creator/video/(?P<id>7100000000000000001)"
        mark_after_analysis = False
        renumber_mirror = False
        change_quality = False
        format_name = "hevc"
        reported_audio = False
        embedded_audio = False
        extraction_count = 0

        def _real_extract(self, url):
            type(self).extraction_count += 1
            return {
                "id": "7100000000000000001",
                "title": "Owned portrait clip",
                "duration": 1.2,
                "formats": [
                    {
                        "format_id": "hevc-1" if self.renumber_mirror else self.format_name,
                        "ext": "mp4",
                        "url": media_server
                        + ("/portrait-muxed.mp4" if self.embedded_audio else "/portrait-hevc.mp4"),
                        "width": 84 if self.change_quality else 96,
                        "height": 160,
                        "vcodec": "h265",
                        "acodec": "aac" if self.reported_audio else "none",
                        "format_note": "watermarked" if self.mark_after_analysis else None,
                    },
                    {
                        "format_id": "play",
                        "ext": "mp4",
                        "url": media_server + "/sample.mp4",
                        "width": 160,
                        "height": 90,
                        "vcodec": "h264",
                        "acodec": "aac",
                    },
                    {
                        "format_id": "download",
                        "ext": "mp4",
                        "url": media_server + "/sample.mp4",
                        "vcodec": "h264",
                        "acodec": "aac",
                        "format_note": "watermarked",
                    },
                    {
                        "format_id": "music",
                        "ext": "m4a",
                        "url": media_server + "/audio.m4a",
                        "vcodec": "none",
                        "acodec": "aac",
                    },
                ],
            }

    def factory(options):
        ydl = original(options, auto_init=False)
        ydl.add_info_extractor(OwnedTikTokIE())
        return ydl

    monkeypatch.setattr(sources.yt_dlp, "YoutubeDL", factory)
    return OwnedTikTokIE


@pytest.mark.parametrize("profile", ["original", "compatible", "mp3"])
def test_highest_hevc_keeps_picture_dimensions_and_clip_audio(client, store, hevc_source, profile):
    client.post("/api/analyze", json={"url": URL})
    analysis = work(store)
    assert analysis["state"] == "completed", analysis
    choice = next(c for c in analysis["result"]["choices"] if c["source_format_ids"][0] == "hevc")
    assert choice["source_format_ids"] == ["hevc", "play"]
    assert choice["quality_height"] == 96 and choice["audio_source_kind"] == "video"
    response = client.post(
        "/api/downloads",
        json={"analysis_id": analysis["id"], "choice_id": choice["id"], "profile": profile},
    )
    assert response.status_code == 202
    task = work(store)
    assert task["state"] == "completed", task
    timings = task["result"]["timings"]
    assert timings["total_seconds"] > 0
    assert timings["stages"]["downloading"] > 0
    asset = store.asset(task["result"]["asset_id"])
    result = asset["metadata"]
    assert result["has_audio"]
    assert 1.0 < result["duration"] < 1.6
    if profile != "mp3":
        assert result["video_codec"] == "h264" and result["pixel_format"] == "yuv420p"
        assert result["audio_codec"] == "aac" and result["audio_profile"] == "LC"
        assert (result["width"], result["height"]) == (96, 160)
        frame = subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(asset["path"]),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "-",
            ]
        )
        assert max(frame) - min(frame) > 40 and sum(frame) / len(frame) > 20
        assert not (asset["path"].parent / "source.mkv").exists()
        assert not (asset["path"].parent / "clip-audio").exists()
    else:
        assert result["kind"] == "audio" and result["audio_codec"] == "mp3"
    pcm = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(asset["path"]),
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "s16le",
            "-",
        ]
    )
    values = array.array("h", pcm)
    assert max(values) > 500
    assert client.get(f"/api/assets/{asset['id']}/file").status_code == 200


def test_actual_embedded_audio_avoids_a_second_source_request(client, store, hevc_source):
    hevc_source.embedded_audio = True
    # Extractor metadata still says video-only; the actual streams decide whether
    # fetching the same post again for another clip-audio rendition is necessary.
    client.post("/api/analyze", json={"url": URL})
    analysis = work(store)
    assert hevc_source.extraction_count == 1
    choice = next(c for c in analysis["result"]["choices"] if c["source_format_ids"][0] == "hevc")
    assert choice["source_format_ids"] == ["hevc", "play"]
    client.post("/api/downloads", json={"analysis_id": analysis["id"], "choice_id": choice["id"]})
    task = work(store)
    assert task["state"] == "completed", task
    assert hevc_source.extraction_count == 2
    assert task["result"]["source_format_ids"] == ["hevc"]
    asset = store.asset(task["result"]["asset_id"])
    assert asset["metadata"]["video_codec"] == "h264" and asset["metadata"]["has_audio"]
    assert (asset["metadata"]["width"], asset["metadata"]["height"]) == (96, 160)
    assert not (asset["path"].parent / "video").exists()
    assert not (asset["path"].parent / "clip-audio").exists()


def test_corrupted_hevc_input_is_not_delivered(client, store, hevc_source, files):
    hevc_source.embedded_audio = True
    source = files / "portrait-muxed.mp4"
    packets = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "packet=pos",
                "-of",
                "json",
                str(source),
            ]
        )
    )["packets"]
    data = bytearray(source.read_bytes())
    offset = int(packets[1]["pos"])
    # Invalid video NAL length; MP4 headers remain readable.
    data[offset : offset + 4] = b"\xff" * 4
    source.write_bytes(data)
    assert media.probe(source)["has_audio"]
    with pytest.raises(ServiceError):
        media.verify(source)
    client.post("/api/analyze", json={"url": URL})
    analysis = work(store)
    choice = next(c for c in analysis["result"]["choices"] if c["source_format_ids"][0] == "hevc")
    client.post("/api/downloads", json={"analysis_id": analysis["id"], "choice_id": choice["id"]})
    task = work(store)
    assert task["state"] == "failed", task
    assert task["result"] is None
    assert task["error"]["code"] == "media_tool_error"
    assert not list((store.config.data_dir / "files" / task["id"]).rglob("*.mp4"))


def test_watermark_change_is_never_delivered(client, store, hevc_source):
    client.post("/api/analyze", json={"url": URL})
    analysis = work(store)
    choice = next(c for c in analysis["result"]["choices"] if c["source_format_ids"][0] == "hevc")
    hevc_source.mark_after_analysis = True
    client.post("/api/downloads", json={"analysis_id": analysis["id"], "choice_id": choice["id"]})
    task = work(store)
    assert task["state"] == "failed" and task["error"]["code"] == "tiktok_source_unavailable"
    assert task["result"] is None


@pytest.mark.parametrize("changed_quality", [False, True])
def test_mirror_ids_can_change_without_quality_fallback(
    client, store, hevc_source, changed_quality
):
    client.post("/api/analyze", json={"url": URL})
    analysis = work(store)
    choice = next(c for c in analysis["result"]["choices"] if c["source_format_ids"][0] == "hevc")
    hevc_source.renumber_mirror = True
    hevc_source.change_quality = changed_quality
    client.post("/api/downloads", json={"analysis_id": analysis["id"], "choice_id": choice["id"]})
    task = work(store)
    if changed_quality:
        assert task["state"] == "failed" and task["error"]["code"] == "format_unavailable"
    else:
        assert task["state"] == "completed", task
        assert task["result"]["source_format_ids"] == ["hevc-1", "play"]


def test_cdn_mirrors_are_one_quality_choice():
    clip = {"ext": "mp4", "vcodec": "h264", "acodec": "aac", "width": 720, "height": 1280}
    result = sources.normalize(
        {"formats": [clip | {"format_id": "play-0"}, clip | {"format_id": "play-1"}]}, URL
    )
    assert len(result["choices"]) == 1
    assert result["choices"][0]["quality_height"] == 720


def test_muxed_audio_variant_can_become_video_only(client, store, hevc_source):
    hevc_source.format_name = "bytevc1_160p_630000-0"
    hevc_source.reported_audio = True
    client.post("/api/analyze", json={"url": URL})
    analysis = work(store)
    choice = next(
        c for c in analysis["result"]["choices"] if c["source_format_ids"][0].startswith("bytevc1")
    )
    assert choice["source_format_ids"] == ["bytevc1_160p_630000-0", "play"]
    hevc_source.format_name = "bytevc1_160p_500000-1"
    hevc_source.reported_audio = False
    client.post("/api/downloads", json={"analysis_id": analysis["id"], "choice_id": choice["id"]})
    task = work(store)
    assert task["state"] == "completed", task
    assert task["result"]["source_format_ids"] == ["bytevc1_160p_500000-1", "play"]
    result = store.asset(task["result"]["asset_id"])["metadata"]
    assert result["has_audio"] and (result["width"], result["height"]) == (96, 160)


@pytest.mark.parametrize(
    "format_id,note", [("download", None), ("download_addr-1", None), ("play", "watermarked")]
)
def test_only_watermarked_source_is_not_offered(format_id, note):
    with pytest.raises(ServiceError) as failure:
        sources.normalize(
            {
                "formats": [
                    {
                        "format_id": format_id,
                        "format_note": note,
                        "ext": "mp4",
                        "vcodec": "h264",
                        "acodec": "aac",
                    }
                ]
            },
            URL,
        )
    assert failure.value.code == "tiktok_source_unavailable"


def test_cached_watermarked_choice_is_rejected(client, store):
    task = store.create("analyze", "Old TikTok analysis", {"url": URL})
    store.claim()
    store.finish(
        task["id"],
        "completed",
        result={
            "platform": "TikTok",
            "title": "Old clip",
            "choices": [
                {
                    "id": "option_0",
                    "source_format_ids": ["download"],
                    "has_audio": True,
                    "operation": "download",
                }
            ],
        },
    )
    response = client.post(
        "/api/downloads", json={"analysis_id": task["id"], "choice_id": "option_0"}
    )
    assert (
        response.status_code == 400
        and response.json()["detail"]["code"] == "tiktok_source_unavailable"
    )


def test_h264_compatible_path_copies_existing_streams(files, tmp_path, monkeypatch):
    calls, actual = [], media.run

    def record(args, timeout=120):
        calls.append(args)
        return actual(args, timeout)

    monkeypatch.setattr(media, "run", record)
    path, result = media.compatible_video(
        files / "sample.mp4", media.probe(files / "sample.mp4"), tmp_path
    )
    command = next(c for c in calls if str(tmp_path / "compatible.mp4") in c)
    assert command[command.index("-c") + 1] == "copy"
    assert result["video_codec"] == "h264" and path.suffix == ".mp4"
