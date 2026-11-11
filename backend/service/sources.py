import re
import shutil
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yt_dlp

from . import media
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
SOUNDCLOUD_HOSTS = {"soundcloud.com", "www.soundcloud.com", "m.soundcloud.com", "on.soundcloud.com"}
TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}
PLANNED_HOSTS = {"instagram.com", "pinterest.com", "pin.it"}
THUMBNAIL_DOMAINS = {
    "YouTube": ("ytimg.com",),
    "SoundCloud": ("sndcdn.com",),
    "TikTok": (
        "tiktokcdn.com",
        "tiktokcdn-us.com",
        "tiktokcdn-eu.com",
        "byteoversea.com",
        "ibytedtos.com",
        "ibyteimg.com",
    ),
}


def platform_for(url: str) -> str:
    host = urlsplit(url).hostname
    if host in YOUTUBE_HOSTS:
        return "YouTube"
    if host in SOUNDCLOUD_HOSTS:
        return "SoundCloud"
    if host in TIKTOK_HOSTS:
        return "TikTok"
    raise ServiceError("invalid_url", "Use a YouTube, SoundCloud or TikTok link.")


def validate_url(value: str) -> str:
    try:
        value = value.strip()
        if len(value) > 2048 or re.search(r"[\x00-\x20\x7f\\]", value):
            raise ValueError
        url = urlsplit(value)
        if (
            url.scheme not in {"https", "http"}
            or url.username
            or url.password
            or url.port not in {None, 80, 443}
        ):
            raise ValueError
        host = (url.hostname or "").lower()
        if host in SOUNDCLOUD_HOSTS:
            if host == "on.soundcloud.com" and re.fullmatch(r"/[A-Za-z0-9_-]{1,128}/?", url.path):
                return "https://on.soundcloud.com" + url.path.rstrip("/")
            match = re.fullmatch(r"/([A-Za-z0-9_-]{1,200})/([A-Za-z0-9_-]{1,200})/?", url.path)
            if host == "on.soundcloud.com" or not match:
                raise ServiceError(
                    "collection_planned",
                    "Use one public SoundCloud track permalink. Profiles and playlists are planned for later.",
                )
            artist, track = match.groups()
            if artist.lower() in {
                "discover",
                "stations",
                "search",
                "charts",
                "you",
                "tags",
                "settings",
            } or track.lower() in {
                "tracks",
                "albums",
                "sets",
                "reposts",
                "likes",
                "spotlight",
                "comments",
            }:
                raise ServiceError(
                    "collection_planned",
                    "Use one public SoundCloud track permalink. Profiles and playlists are planned for later.",
                )
            if "secret_token" in parse_qs(url.query):
                raise ServiceError(
                    "access_required", "Use a public SoundCloud track permalink in this build."
                )
            return f"https://soundcloud.com/{artist}/{track}"
        if host in TIKTOK_HOSTS:
            if host in {"vm.tiktok.com", "vt.tiktok.com"}:
                if re.fullmatch(r"/[A-Za-z0-9_-]{1,128}/?", url.path):
                    return f"https://{host}" + url.path.rstrip("/") + "/"
                raise ValueError
            if re.fullmatch(r"/t/[A-Za-z0-9_-]{1,128}/?", url.path):
                return "https://www.tiktok.com" + url.path.rstrip("/") + "/"
            match = re.fullmatch(r"/@([A-Za-z0-9_.]{1,64})/(video|photo)/([0-9]{1,30})/?", url.path)
            if match:
                return f"https://www.tiktok.com/@{match[1]}/{match[2]}/{match[3]}"
            if url.path.rstrip("/").endswith("/live"):
                raise ServiceError(
                    "live_unsupported",
                    "Use a finished TikTok video. Live streams are not supported.",
                )
            raise ServiceError(
                "collection_planned",
                "Use one TikTok video permalink. Profiles, sounds and collections are planned for later.",
            )
        if host not in YOUTUBE_HOSTS:
            if any(host == h or host.endswith("." + h) for h in PLANNED_HOSTS):
                raise ServiceError(
                    "platform_planned",
                    "This platform is planned for a later stage. Use YouTube, SoundCloud or a TikTok video in this build.",
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
            "invalid_url", "Enter a YouTube video, public SoundCloud track or TikTok video URL."
        ) from None


def is_short_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.hostname in {"on.soundcloud.com", "vm.tiktok.com", "vt.tiktok.com"} or (
        parts.hostname == "www.tiktok.com" and parts.path.startswith("/t/")
    )


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def resolve_url(value: str) -> str:
    """Resolve share links only in the worker, checking each hop before requesting it."""
    url = validate_url(value)
    platform = platform_for(url)
    opener = build_opener(NoRedirects())
    seen = set()
    for _ in range(5):
        if not is_short_url(url):
            return url
        if url in seen:
            break
        seen.add(url)
        try:
            request = Request(url, method="HEAD", headers={"User-Agent": "facebookexternalhit/1.1"})
            try:
                response = opener.open(request, timeout=15)
            except HTTPError as error:
                response = error
            with response:
                if response.code not in {301, 302, 303, 307, 308} or not response.headers.get(
                    "Location"
                ):
                    break
                candidate = validate_url(urljoin(url, response.headers["Location"]))
                if platform_for(candidate) != platform:
                    break
                url = candidate
        except (OSError, URLError, ValueError, ServiceError):
            break
    if not is_short_url(url):
        return url
    raise ServiceError(
        "short_link_error",
        "This share link could not be resolved to one supported item. Open it in your browser and paste the full track or video permalink.",
    )


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
        "allowed_extractors": ["youtube$", "soundcloud$", "tiktok$"],
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


def tiktok_watermarked(item):
    ids = item.get("source_format_ids") or [item.get("format_id", "")]
    return (
        "watermarked" in str(item.get("format_note") or "").lower()
        or item.get("has_watermark") is True
        or any(re.fullmatch(r"download(?:_addr)?(?:-\d+)?", str(value)) for value in ids)
    )


def quality_height(item):
    dimensions = [item.get(key) for key in ("width", "height") if item.get(key)]
    return min(dimensions) if dimensions else None


def format_identity(item, role="video"):
    family = re.sub(r"-\d+$", "", str(item["format_id"]))
    # The last number can include muxed audio bitrate; the same video may later
    # arrive without audio under a different ID. Geometry/FPS/video codec stay bound.
    family = re.sub(r"^((?:h264|h265|bytevc1)_\d+p)_\d+$", r"\1", family)
    return {
        key: item.get(key)
        for key in ("ext", "width", "height", "fps", "vcodec", "acodec", "tbr", "abr")
    } | {
        "family": family,
        "format_id": item["format_id"],
        "stream_role": role,
    }


def same_representation(item, identity):
    current = format_identity(item)
    if any(
        current[key] != identity[key]
        for key in ("family", "ext", "width", "height", "fps", "vcodec")
    ):
        return False
    return identity.get("stream_role") != "clip_audio" or (
        current["acodec"] not in {None, "none"} and current["acodec"] == identity["acodec"]
    )


def normalize(info: dict, url: str):
    platform = platform_for(url)
    if (info.get("duration") or 0) > 7200:
        raise ServiceError("media_limit", "This media exceeds the two hour limit.")
    if info.get("_type") in {"playlist", "multi_video"} or info.get("entries") is not None:
        raise ServiceError(
            "collection_planned",
            "Collections are planned for a later stage. Use one track or video URL.",
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
        and f.get("vcodec") != "bytevc2"
        and not (platform == "SoundCloud" and "preview" in str(f.get("format_id", "")).lower())
        # TikTok's separate music URL can be a different/longer soundtrack than the clip.
        and not (platform == "TikTok" and f.get("vcodec") == "none")
        and not (platform == "TikTok" and tiktok_watermarked(f))
    ]
    if platform == "TikTok":
        # yt-dlp suffixes identical CDN mirrors with -0/-1; these are not extra quality options.
        unique = {}
        for item in formats:
            identity = format_identity(item)
            key = tuple(
                identity[name] for name in ("family", "ext", "width", "height", "fps", "vcodec")
            )
            previous = unique.get(key)
            if previous is None or (item.get("acodec") != "none", item.get("tbr") or 0) > (
                previous.get("acodec") != "none",
                previous.get("tbr") or 0,
            ):
                unique[key] = item
        formats = list(unique.values())
    audio = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec", "none") != "none"]
    clip_audio = [
        f
        for f in formats
        if f.get("vcodec", "none") != "none" and f.get("acodec", "none") != "none"
    ]
    choices = []
    for f in formats:
        video = f.get("vcodec", "none") != "none"
        sound = f.get("acodec", "none") != "none"
        if not video and not sound:
            continue
        parts = [f]
        if platform == "TikTok" and video and (not sound or f.get("vcodec") in {"h265", "hevc"}):
            if not clip_audio:
                continue
            # Use the same clip's embedded audio, never its separate music/soundtrack URL.
            audio_source = min(
                clip_audio,
                key=lambda a: (
                    a.get("vcodec") not in {"h264", "avc1"},
                    -(a.get("abr") or 0),
                    a.get("filesize") or float("inf"),
                    a.get("height") or float("inf"),
                ),
            )
            if audio_source["format_id"] != f["format_id"]:
                parts.append(audio_source)
        elif video and not sound and audio:
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
                if f["ext"] == "mp4" and (parts[1]["ext"] == "m4a" or platform == "TikTok")
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
                "source_formats": [
                    format_identity(p, "video" if index == 0 and len(parts) == 2 else "clip_audio")
                    for index, p in enumerate(parts)
                ]
                if platform == "TikTok"
                else None,
                "kind": "video" if video else "audio",
                "container": container,
                "height": f.get("height"),
                "width": f.get("width"),
                "quality_height": quality_height(f),
                "audio_source_kind": "video"
                if len(parts) == 2 and parts[1].get("vcodec", "none") != "none"
                else None,
                "fps": f.get("fps"),
                "audio_bitrate": next((p.get("abr") for p in parts if p.get("abr")), None),
                "format_note": f.get("format_note"),
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
        if platform == "TikTok":
            raise ServiceError(
                "tiktok_source_unavailable",
                "No usable TikTok video source without a reported watermark and with clip audio is available. Choose another post.",
            )
        if platform == "SoundCloud" and any(
            "preview" in str(f.get("format_id", "")).lower() for f in info.get("formats", [])
        ):
            raise ServiceError(
                "preview_only",
                "SoundCloud returned only a preview. A full track is not available with the current access. Choose another public track or check owner access.",
            )
        raise ServiceError(
            "no_formats",
            "No supported formats were returned. Check access and tool versions, then analyze again.",
        )
    thumbnail = info.get("thumbnail")
    if thumbnail:
        parsed = urlsplit(thumbnail)
        if (
            parsed.scheme != "https"
            or not any(
                (parsed.hostname or "").endswith("." + domain)
                for domain in THUMBNAIL_DOMAINS[platform]
            )
            or parsed.username
            or parsed.password
            or parsed.netloc != parsed.hostname
        ):
            thumbnail = None
    return {
        "url": url,
        "source_id": info.get("id"),
        "title": info.get("title") or platform + " media",
        "platform": platform,
        "author": info.get("uploader"),
        "thumbnail": thumbnail,
        "duration": info.get("duration"),
        "kind": "video" if any(c["kind"] == "video" for c in choices) else "audio",
        "choices": choices,
    }


def analyze(url, config):
    url = resolve_url(url)
    if platform_for(url) == "TikTok" and "/photo/" in urlsplit(url).path:
        from . import photos

        return photos.analyze(url, config)
    try:
        with yt_dlp.YoutubeDL(options(config)) as ydl:
            return normalize(ydl.extract_info(url, download=False), url)
    except yt_dlp.utils.DownloadError as error:
        raise extractor_error(error) from None


def download(analysis, choice, profile, bitrate, directory: Path, config, report):
    if analysis.get("platform") == "TikTok" and tiktok_watermarked(choice):
        raise ServiceError(
            "tiktok_source_unavailable",
            "Analyze again to select a source without a reported watermark.",
        )
    if choice.get("audio_source_kind") == "video" and profile != "mp3":
        parts = []
        for index, format_id in enumerate(choice["source_format_ids"]):
            part_directory = directory / ("video" if index == 0 else "clip-audio")
            part_directory.mkdir()
            part_choice = choice | {
                "selector": format_id,
                "source_format_ids": [format_id],
                "audio_source_kind": None,
            }
            parts.append(
                _download_one(
                    analysis, part_choice, "original", bitrate, part_directory, config, report
                )
            )
            if index == 0:
                choice["resolved_source_format_ids"] = []
            choice["resolved_source_format_ids"].extend(
                part_choice.get("resolved_source_format_ids", [format_id])
            )
            # A refreshed HEVC URL may already include this clip's audio. Inspect
            # the actual file before making another extraction/download request.
            if index == 0 and media.probe(parts[0])["has_audio"]:
                target = directory / ("source" + parts[0].suffix)
                parts[0].replace(target)
                shutil.rmtree(part_directory)
                return target
        report("merging")
        target = directory / "source.mkv"
        media.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(parts[0]),
                "-i",
                str(parts[1]),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c",
                "copy",
                "-map_metadata",
                "-1",
                str(target),
            ],
            1700,
        )
        for path in parts:
            shutil.rmtree(path.parent)
        return target
    return _download_one(analysis, choice, profile, bitrate, directory, config, report)


def _download_one(analysis, choice, profile, bitrate, directory: Path, config, report):
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
    if analysis.get("platform") == "TikTok" and choice.get("source_formats"):
        desired_id = (
            choice["source_format_ids"][-1] if profile == "mp3" else choice["source_format_ids"][0]
        )
        identity = next(
            item for item in choice["source_formats"] if item["format_id"] == desired_id
        )

        def exact_representation(context):
            candidates = [
                item for item in context["formats"] if same_representation(item, identity)
            ]
            clean = [item for item in candidates if not tiktok_watermarked(item)]
            if not clean:
                if candidates:
                    raise ServiceError(
                        "tiktok_source_unavailable",
                        "The source now reports a watermark. Analyze again to choose another source.",
                    )
                raise ServiceError(
                    "format_unavailable",
                    "This exact quality/codec is no longer available. Analyze the link again.",
                )
            yield next((item for item in clean if item["format_id"] == desired_id), clean[0])

        opts["format"] = exact_representation
    report("analyzing")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(validate_url(analysis["url"]), download=True)
        if not info or info.get("id") != analysis["source_id"]:
            raise ServiceError("source_changed", "The source changed. Analyze the link again.")
        if analysis.get("platform") == "TikTok" and any(
            tiktok_watermarked(item)
            for item in [
                info,
                *(info.get("requested_formats") or []),
                *(info.get("requested_downloads") or []),
            ]
        ):
            raise ServiceError(
                "tiktok_source_unavailable",
                "The source now reports a watermark for this option. Analyze again and choose another source.",
            )
        choice["resolved_source_format_ids"] = [
            item["format_id"] for item in (info.get("requested_formats") or [info])
        ]
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
