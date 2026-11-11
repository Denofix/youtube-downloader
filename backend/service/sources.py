import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import yt_dlp

from .config import Settings
from .errors import ServiceError, extractor_error

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
PLANNED_HOSTS = {"tiktok.com", "soundcloud.com", "instagram.com", "pinterest.com", "pin.it"}


def validate_url(value: str) -> str:
    try:
        url = urlsplit(value.strip())
        if (
            url.scheme not in {"https", "http"}
            or url.username
            or url.password
            or url.port not in {None, 80, 443}
        ):
            raise ValueError
        host = (url.hostname or "").lower()
        if host not in YOUTUBE_HOSTS:
            if any(host == h or host.endswith("." + h) for h in PLANNED_HOSTS):
                raise ServiceError(
                    "platform_planned",
                    "This platform is planned for the next stage. Use an individual YouTube video in this build.",
                )
            raise ValueError
        if host.endswith("youtu.be"):
            video_id = url.path.strip("/")
        elif url.path == "/watch":
            video_id = parse_qs(url.query).get("v", [""])[0]
        elif re.fullmatch(r"/(shorts|embed|live)/[^/]+/?", url.path):
            video_id = url.path.rstrip("/").split("/")[-1]
        else:
            raise ValueError
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError
        return "https://www.youtube.com/watch?v=" + video_id
    except (ValueError, TypeError):
        raise ServiceError(
            "invalid_url", "Enter an individual YouTube video or Shorts URL."
        ) from None


class QuietLogger:
    def debug(self, message):
        pass

    info = warning = error = debug


def options(config: Settings):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": QuietLogger(),
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "cachedir": False,
        "restrictfilenames": True,
        "js_runtimes": {"node": {}},
        "remote_components": set(),
        "max_filesize": config.max_file_bytes,
    }
    if config.cookie_file:
        opts["cookiefile"] = config.cookie_file
    if config.use_system_ca:
        opts["compat_opts"] = {"no-certifi"}
    return opts


def normalize(info: dict, url: str):
    if (info.get("duration") or 0) > 7200:
        raise ServiceError("media_limit", "This video exceeds the two hour limit.")
    if info.get("_type") in {"playlist", "multi_video"} or info.get("entries") is not None:
        raise ServiceError(
            "collection_planned", "Collections are planned for a later stage. Use one video URL."
        )
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
        raise ServiceError(
            "live_unsupported",
            "Use a finished video. Live and upcoming streams are not supported yet.",
        )
    formats = [
        f
        for f in info.get("formats", [])
        if re.fullmatch(r"[A-Za-z0-9._-]+", str(f.get("format_id", "")))
        and f.get("ext")
        in {"mp4", "m4a", "webm", "mkv", "mp3", "ogg", "opus", "aac", "wav", "flac"}
        and not f.get("has_drm")
    ]
    audio = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec", "none") != "none"]
    choices = []
    for f in formats:
        video = f.get("vcodec", "none") != "none"
        sound = f.get("acodec", "none") != "none"
        if not video and not sound:
            continue
        parts = [f]
        if video and not sound and audio:
            compatible = [
                a
                for a in audio
                if (f["ext"] == "mp4" and a["ext"] == "m4a")
                or (f["ext"] == "webm" and a["ext"] == "webm")
            ]
            parts.append(max(compatible or audio, key=lambda a: a.get("abr") or a.get("tbr") or 0))
        container = f["ext"]
        if len(parts) == 2:
            container = (
                "mp4"
                if f["ext"] == "mp4" and parts[1]["ext"] == "m4a"
                else "webm"
                if all(p["ext"] == "webm" for p in parts)
                else "mkv"
            )
        exact = all(p.get("filesize") for p in parts)
        sizes = [p.get("filesize") or p.get("filesize_approx") for p in parts]
        size = sum(sizes) if all(sizes) else None
        choices.append(
            {
                "id": "option_" + str(len(choices)),
                "selector": "+".join(p["format_id"] for p in parts),
                "source_format_ids": [p["format_id"] for p in parts],
                "kind": "video" if video else "audio",
                "container": container,
                "height": f.get("height"),
                "width": f.get("width"),
                "fps": f.get("fps"),
                "video_codec": f.get("vcodec") if video else None,
                "audio_codec": next(
                    (p.get("acodec") for p in parts if p.get("acodec", "none") != "none"), None
                ),
                "has_audio": sound or len(parts) == 2,
                "operation": "merge" if len(parts) == 2 else "download",
                "size": size,
                "size_kind": "exact" if exact else "approximate" if size else "unknown",
            }
        )
    if not choices:
        raise ServiceError(
            "no_formats",
            "No supported formats were returned. Check access and tool versions, then analyze again.",
        )
    thumbnail = info.get("thumbnail")
    if thumbnail:
        parsed = urlsplit(thumbnail)
        if (
            parsed.scheme != "https"
            or not (parsed.hostname or "").endswith(".ytimg.com")
            or parsed.username
            or parsed.password
        ):
            thumbnail = None
    return {
        "url": url,
        "source_id": info.get("id"),
        "title": info.get("title") or "YouTube video",
        "platform": "YouTube",
        "author": info.get("uploader"),
        "thumbnail": thumbnail,
        "duration": info.get("duration"),
        "kind": "video",
        "choices": choices,
    }


def analyze(url, config):
    url = validate_url(url)
    try:
        with yt_dlp.YoutubeDL(options(config)) as ydl:
            return normalize(ydl.extract_info(url, download=False), url)
    except yt_dlp.utils.DownloadError as error:
        raise extractor_error(error) from None


def download(analysis, choice, profile, bitrate, directory: Path, config, report):
    def progress(data):
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        value = min(100, 100 * data.get("downloaded_bytes", 0) / total) if total else None
        if data.get("status") == "downloading":
            report("downloading", value, data.get("speed"), data.get("eta"))
        elif data.get("status") == "finished":
            report("preparing")

    def postprocess(data):
        name = data.get("postprocessor", "").lower()
        report("merging" if "merger" in name else "converting" if "audio" in name else "preparing")

    opts = options(config) | {
        "format": choice["selector"],
        "outtmpl": str(directory / "source.%(ext)s"),
        "progress_hooks": [progress],
        "postprocessor_hooks": [postprocess],
        "merge_output_format": choice["container"],
    }
    if profile == "mp3":
        if not choice["has_audio"]:
            raise ServiceError("no_audio", "This option has no audio stream.")
        if len(choice["source_format_ids"]) == 2:
            opts["format"] = choice["source_format_ids"][-1]
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": str(bitrate)}
        ]
    report("analyzing")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(validate_url(analysis["url"]), download=True)
        if not info or info.get("id") != analysis["source_id"]:
            raise ServiceError("source_changed", "The source changed. Analyze the link again.")
    except yt_dlp.utils.DownloadError as error:
        raise extractor_error(error) from None
    files = [
        p
        for p in directory.iterdir()
        if p.is_file()
        and p.suffix.lower()
        in {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".ogg", ".opus", ".aac", ".wav", ".flac"}
    ]
    if len(files) != 1:
        raise ServiceError(
            "invalid_result", "The download did not produce one complete media file. Analyze again."
        )
    return files[0]
