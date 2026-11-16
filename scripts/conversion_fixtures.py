"""Small owned media fixtures and the reproducible stage-6a compatibility matrix."""

import array
import hashlib
import json
import struct
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

VIDEO_OUTPUTS = ("mp4", "mov", "mkv", "webm")
AUDIO_OUTPUTS = ("mp3", "m4a", "wav", "flac", "ogg")
IMAGE_OUTPUTS = ("jpg", "png", "webp")
MATRIX = (
    [
        (f"video.{fmt}", out)
        for fmt in VIDEO_OUTPUTS
        for out in (*VIDEO_OUTPUTS, *AUDIO_OUTPUTS, "gif")
    ]
    + [(f"audio.{fmt}", out) for fmt in AUDIO_OUTPUTS for out in AUDIO_OUTPUTS]
    + [(f"image.{fmt}", out) for fmt in (*IMAGE_OUTPUTS, "gif") for out in IMAGE_OUTPUTS]
    + [("animated.gif", out) for out in (*VIDEO_OUTPUTS, "gif")]
    + [("oriented.jpg", out) for out in IMAGE_OUTPUTS]
    + [("cmyk.jpg", out) for out in IMAGE_OUTPUTS]
    + [("rotated.mov", out) for out in (*VIDEO_OUTPUTS, "gif")]
    + [(name, out) for name in ("portrait.mp4", "odd.mkv") for out in ("mp4", "webm", "gif")]
    + [("silent.mp4", out) for out in (*VIDEO_OUTPUTS, "gif")]
)


def ffmpeg(*args):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-threads",
            "2",
            "-filter_threads",
            "1",
            *map(str, args),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )


def build_fixtures(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / "video.mp4"
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=160x90:rate=12",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=44100",
        "-t",
        "1.2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        base,
    )
    ffmpeg("-i", base, "-c", "copy", directory / "video.mov")
    ffmpeg("-i", base, "-c:v", "ffv1", "-c:a", "flac", directory / "video.mkv")
    ffmpeg(
        "-i",
        base,
        "-c:v",
        "libvpx-vp9",
        "-threads",
        "2",
        "-c:a",
        "libopus",
        directory / "video.webm",
    )
    # Set the video track's ISO BMFF display matrix directly: legacy rotate
    # metadata behaves differently across the supported FFmpeg versions.
    rotated = bytearray((directory / "video.mov").read_bytes())
    track = rotated.index(b"tkhd")
    matrix = track + 4 + (52 if rotated[track + 4] == 1 else 40)
    struct.pack_into(">9i", rotated, matrix, 0, -65536, 0, 65536, 0, 0, 0, 0, 1073741824)
    (directory / "rotated.mov").write_bytes(rotated)
    ffmpeg("-i", base, "-an", "-c:v", "copy", directory / "silent.mp4")
    for name, pattern, codec in (
        ("portrait.mp4", "testsrc2=size=96x160:rate=12", "libx264"),
        ("odd.mkv", "testsrc=size=161x91:rate=12", "ffv1"),
    ):
        ffmpeg("-f", "lavfi", "-i", pattern, "-t", "1.2", "-c:v", codec, directory / name)
    for fmt, codec in zip(
        AUDIO_OUTPUTS, ("libmp3lame", "aac", "pcm_s16le", "flac", "libvorbis"), strict=True
    ):
        ffmpeg("-i", base, "-vn", "-c:a", codec, directory / ("audio." + fmt))

    rgb = Image.new("RGB", (64, 48), "orange")
    ImageDraw.Draw(rgb).rectangle((32, 0, 63, 47), fill="navy")
    rgb.save(directory / "image.jpg", quality=95)
    rgb.convert("CMYK").save(directory / "cmyk.jpg", quality=95)
    rgb.save(directory / "image.gif")
    rgba = rgb.convert("RGBA")
    ImageDraw.Draw(rgba).rectangle((0, 0, 15, 47), fill=(255, 0, 0, 0))
    ImageDraw.Draw(rgba).rectangle((16, 0, 31, 47), fill=(255, 0, 0, 100))
    rgba.save(directory / "image.png")
    rgba.save(directory / "image.webp", lossless=True)
    exif = rgb.getexif()
    exif[274] = 6
    rgb.save(directory / "oriented.jpg", exif=exif, quality=95)
    frames = [Image.new("RGB", (64, 48), color) for color in ("orange", "navy", "yellow")]
    frames[0].save(
        directory / "animated.gif", save_all=True, append_images=frames[1:], duration=120, loop=0
    )
    frames[0].save(
        directory / "animated.webp", save_all=True, append_images=frames[1:], duration=120, loop=0
    )
    return directory


def video_hashes(path):
    decoded = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-threads",
            "2",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-f",
            "framemd5",
            "-",
        ],
        timeout=30,
        text=True,
    )
    return {
        line.rsplit(",", 1)[-1].strip() for line in decoded.splitlines() if not line.startswith("#")
    }


def check_result(source, target, metadata, result, output):
    """Check meaningful contents in addition to the service's full output decoding."""
    assert target.stat().st_size > 0
    assert result["kind"] == (
        "image"
        if output in IMAGE_OUTPUTS
        else "animation"
        if output == "gif"
        else "audio"
        if output in AUDIO_OUTPUTS
        else "video"
    )
    assert result["has_audio"] == (metadata["has_audio"] and output not in (*IMAGE_OUTPUTS, "gif"))
    if result["has_audio"]:
        pcm = subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-threads",
                "2",
                "-i",
                str(target),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "8000",
                "-f",
                "s16le",
                "-",
            ],
            timeout=30,
        )
        samples = array.array("h", pcm)
        assert samples and max(map(abs, samples)) > 100
    if output in IMAGE_OUTPUTS:
        expected = (48, 64) if source.name == "oriented.jpg" else (64, 48)
        with Image.open(target) as image:
            image.load()
            assert image.size == expected
            assert image.format == {"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[output]
            if source.suffix in {".png", ".webp"}:
                if output == "jpg":
                    assert min(image.convert("RGB").getpixel((5, 20))) > 240
                else:
                    assert image.convert("RGBA").getpixel((5, 20))[3] == 0
                    assert abs(image.convert("RGBA").getpixel((20, 20))[3] - 100) <= 2
            if source.name == "oriented.jpg":
                red, _, blue = image.convert("RGB").getpixel((24, 8))
                assert red > 150 and blue < 70
                assert image.getexif().get(274, 1) == 1
    elif output == "gif":
        with Image.open(target) as image:
            assert image.width <= min(160, metadata.get("display_width") or metadata["width"])
            assert image.n_frames > 1
            pixels = set()
            for frame in range(image.n_frames):
                image.seek(frame)
                pixels.add(hashlib.sha256(image.convert("RGB").tobytes()).hexdigest())
            assert len(pixels) > 1
    else:
        # AAC/MP3/Vorbis priming is bounded separately from frame rounding.
        assert abs(result["duration"] - metadata["duration"]) <= 0.2
        if output in VIDEO_OUTPUTS:
            width = metadata.get("display_width") or metadata["width"]
            height = metadata.get("display_height") or metadata["height"]
            assert (result["width"], result["height"]) == (width + width % 2, height + height % 2)
            assert len(video_hashes(target)) > 1
            if metadata.get("fps"):
                assert abs(result["fps"] - metadata["fps"]) < 0.01
            if output != "webm":
                assert result["video_codec"] == "h264" and result["pixel_format"] == "yuv420p"
                assert not result["has_audio"] or result["audio_codec"] == "aac"
    return {
        "input": source.name,
        "output": output,
        "source_bytes": source.stat().st_size,
        "result_bytes": target.stat().st_size,
        "metadata": result,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }


def write_report(path, results, versions):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "stage": "6a",
                "fixture_origin": "Locally generated test patterns, sine waves and Pillow images; no platform/user media.",
                "scope": "Actual full-file conversion; not a claim about every codec in each container.",
                "versions": versions,
                "cases_passed": len(results),
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
