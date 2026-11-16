import json
import re
import shutil
import subprocess
import warnings
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError, features

from .errors import ServiceError

Image.MAX_IMAGE_PIXELS = 24_000_000
VIDEO = {
    "mp4": (
        "libx264",
        [
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "25",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
        ],
    ),
    "mkv": ("libx264", ["-c:v", "libx264", "-preset", "fast", "-crf", "25", "-c:a", "aac"]),
    "mov": ("libx264", ["-c:v", "libx264", "-preset", "fast", "-crf", "25", "-c:a", "aac"]),
    "webm": ("libvpx-vp9", ["-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "0", "-c:a", "libopus"]),
}
AUDIO = {"mp3": "libmp3lame", "m4a": "aac", "wav": "pcm_s16le", "flac": "flac", "ogg": "libvorbis"}


def run(args, timeout=120):
    try:
        return subprocess.run(
            args, check=True, capture_output=True, text=True, timeout=timeout
        ).stdout
    except (subprocess.SubprocessError, OSError):
        raise ServiceError(
            "media_tool_error",
            "The media tool could not process this file. Check that it is complete and supported.",
        ) from None


@lru_cache(maxsize=1)
def encoders():
    if not shutil.which("ffmpeg"):
        return set()
    text = run(["ffmpeg", "-hide_banner", "-encoders"], 10)
    return {m.group(1) for m in re.finditer(r"^\s*[VAS][A-Z.]{5}\s+(\S+)", text, re.M)}


def probe(path: Path):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                    raise ServiceError("image_unsupported", "Use JPEG, PNG, WebP or GIF images.")
                frames = getattr(image, "n_frames", 1)
                if image.width * image.height > Image.MAX_IMAGE_PIXELS or frames > 500:
                    raise ServiceError(
                        "image_limit", "The image exceeds the 24 megapixel or 500 frame limit."
                    )
                metadata = {
                    "kind": "animation" if frames > 1 else "image",
                    "format": image.format.lower(),
                    "width": image.width,
                    "height": image.height,
                    "frames": frames,
                    "has_audio": False,
                    "transparent": "A" in image.getbands() or "transparency" in image.info,
                }
                if frames == 1:
                    image.verify()
                return metadata
    except (UnidentifiedImageError, OSError):
        pass
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ServiceError("image_limit", "This image exceeds the pixel limit.") from None
    data = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            20,
        )
    )
    streams = data.get("streams", [])
    video = next(
        (
            s
            for s in streams
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video and not audio:
        raise ServiceError("unsupported_file", "No supported video, audio or image was found.")
    duration = float(data.get("format", {}).get("duration") or 0)
    if duration > 7200 or (video and video.get("width", 0) * video.get("height", 0) > 24_000_000):
        raise ServiceError("media_limit", "The file exceeds the two hour or 24 megapixel limit.")
    return {
        "kind": "video" if video else "audio",
        "format": data.get("format", {}).get("format_name"),
        "duration": duration or None,
        "width": video.get("width") if video else None,
        "height": video.get("height") if video else None,
        "video_codec": video.get("codec_name") if video else None,
        "pixel_format": video.get("pix_fmt") if video else None,
        "video_profile": video.get("profile") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_profile": audio.get("profile") if audio else None,
        "audio_channels": audio.get("channels") if audio else None,
        "has_audio": audio is not None,
    }


def capabilities(metadata):
    available, result, kind = encoders(), [], metadata["kind"]
    if kind == "image":
        for fmt in ("png", "jpg", "webp"):
            if fmt != "webp" or features.check("webp"):
                result.append(
                    {"id": fmt, "label": "Convert image to " + fmt.upper(), "transcoding": True}
                )
    if kind in {"video", "animation"}:
        for fmt, (codec, _) in VIDEO.items():
            if codec in available and (
                not metadata["has_audio"] or ("libopus" if fmt == "webm" else "aac") in available
            ):
                result.append(
                    {"id": fmt, "label": "Encode video as " + fmt.upper(), "transcoding": True}
                )
        if "gif" in available:
            result.append({"id": "gif", "label": "Create a short GIF clip", "transcoding": True})
    if metadata["has_audio"]:
        for fmt, codec in AUDIO.items():
            if codec in available:
                result.append(
                    {
                        "id": fmt,
                        "label": ("Extract" if kind == "video" else "Convert")
                        + " audio to "
                        + fmt.upper(),
                        "transcoding": True,
                    }
                )
    return result


def validate_conversion(metadata, parameters):
    if parameters["output"] not in {p["id"] for p in capabilities(metadata)}:
        raise ServiceError(
            "incompatible_conversion",
            "This operation is not supported for this file or the installed codecs.",
        )
    if (
        parameters["output"] == "gif"
        and metadata.get("duration")
        and parameters["start"] >= metadata["duration"]
    ):
        raise ServiceError("invalid_clip", "The GIF start must be inside the source duration.")


def convert(source: Path, metadata, parameters, directory: Path):
    validate_conversion(metadata, parameters)
    fmt = parameters["output"]
    target = directory / ("result." + fmt)
    if metadata["kind"] == "image":
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            if fmt == "jpg":
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            elif fmt == "webp":
                image = image.convert("RGBA")
            image.save(target, format={"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[fmt])
    else:
        args = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-protocol_whitelist",
            "file,pipe",
            "-threads",
            "2",
            "-i",
            str(source),
        ]
        if fmt == "gif":
            width = min(parameters["width"], metadata.get("width") or parameters["width"])
            graph = f"fps={parameters['fps']},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
            args += [
                "-ss",
                str(parameters["start"]),
                "-t",
                str(parameters["duration"]),
                "-filter_complex",
                graph,
                "-an",
                "-loop",
                "0",
            ]
        elif fmt in AUDIO:
            args += ["-map", "0:a:0", "-vn", "-c:a", AUDIO[fmt]]
            if fmt in {"mp3", "m4a"}:
                args += ["-b:a", str(parameters["bitrate"]) + "k"]
        else:
            args += [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-pix_fmt",
                "yuv420p",
                *VIDEO[fmt][1],
            ]
        args += ["-map_metadata", "-1", "-threads", "2", str(target)]
        run(args, 1700)
    result = verify(target)
    if fmt in AUDIO and not result["has_audio"]:
        raise ServiceError("invalid_result", "The result has no audio stream.")
    return target, result


def compatible_video(source: Path, metadata, directory: Path):
    """Deliver an MP4 that does not require an HEVC/10-bit decoder on the client."""
    if metadata["kind"] != "video" or not metadata["has_audio"]:
        raise ServiceError(
            "no_audio", "A compatible video result requires both video and clip audio."
        )
    if not {"libx264", "aac"}.issubset(encoders()):
        raise ServiceError(
            "missing_encoder",
            "Compatible MP4 delivery requires H.264 and AAC encoders. Check server diagnostics.",
        )
    target = directory / "compatible.mp4"
    copy = (
        metadata["video_codec"] == "h264"
        and metadata.get("pixel_format") == "yuv420p"
        and metadata.get("video_profile") in {"High", "Main", "Baseline", "Constrained Baseline"}
        and metadata["audio_codec"] == "aac"
        and metadata.get("audio_profile") == "LC"
        and (metadata.get("audio_channels") or 99) <= 2
    )
    encoding = (
        ["-c", "copy"]
        if copy
        else [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-profile:a",
            "aac_low",
            "-b:a",
            "192k",
            "-ac",
            "2",
        ]
    )
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-xerror",
            "-nostdin",
            "-y",
            "-protocol_whitelist",
            "file,pipe",
            "-threads",
            "2",
            "-noautorotate",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            *encoding,
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-movflags",
            "+faststart",
            "-threads",
            "2",
            str(target),
        ],
        1700,
    )
    result = verify(target)
    if (
        result["kind"] != "video"
        or not result["has_audio"]
        or result["video_codec"] != "h264"
        or result["audio_codec"] != "aac"
        or result.get("pixel_format") != "yuv420p"
        or any(result.get(key) != metadata.get(key) for key in ("width", "height"))
    ):
        raise ServiceError(
            "invalid_result",
            "The compatible result does not match the required video, audio or selected dimensions.",
        )
    return target, result


def verify(path):
    metadata = probe(path)
    if metadata["kind"] != "image":
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-xerror",
                "-nostdin",
                "-protocol_whitelist",
                "file,pipe",
                "-threads",
                "2",
                "-i",
                str(path),
                "-map",
                "0:v:0?",
                "-map",
                "0:a:0?",
                "-f",
                "null",
                "-",
            ],
            1700,
        )
    return metadata


def safe_name(title, extension, descriptor=""):
    suffix = " - " + descriptor if descriptor else ""
    stem = (
        re.sub(r"[^\w .()-]", "_", title, flags=re.UNICODE).strip(" .")[: 100 - len(suffix)]
        or "media"
    )
    return stem + suffix + extension
