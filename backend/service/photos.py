"""Bounded photo snapshots, local previews and selected-file delivery."""

import hashlib
import re
import shutil
import ssl
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPSHandler, Request, build_opener

import yt_dlp
from PIL import Image, ImageOps

from . import media, sources
from .errors import ServiceError, extractor_error

MAX_ITEMS = 40
MAX_PHOTO_BYTES = 16 * 1024**2


def is_photo_url(url):
    return sources.platform_for(url) == "TikTok" and "/photo/" in urlsplit(url).path


def check_media_url(url, platform="TikTok"):
    try:
        if not isinstance(url, str):
            raise ValueError
        p = urlsplit(url)
        host = p.hostname or ""
        if (
            len(url) > 8192
            or re.search(r"[\x00-\x20\x7f\\]", url)
            or p.scheme != "https"
            or p.username
            or p.password
            or p.port not in {None, 443}
            or not any(
                host.endswith("." + domain)
                for domain in sources.THUMBNAIL_DOMAINS.get(platform, ())
            )
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise ServiceError(
            "photo_source_unavailable", "This photo source is not supported."
        ) from None
    return url


def analyze(url, config):
    post_id = urlsplit(url).path.rstrip("/").split("/")[-1]
    try:
        with yt_dlp.YoutubeDL(sources.options(config)) as ydl:
            extractor = ydl.get_info_extractor("TikTok")
            extractor.initialize()
            # TikTok exposes imagePost metadata on the video-detail route too.
            # This small adapter is tested against the locked yt-dlp interface.
            post, status = extractor._extract_web_data_and_status(
                url.replace("/photo/", "/video/"), post_id
            )
    except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as error:
        raise extractor_error(error) from None
    if status in {10216, 10222}:
        raise ServiceError("access_required", "The owner needs access to this TikTok post.")
    if status == 10204:
        raise ServiceError("network_blocked", "TikTok blocked access from this server's network.")
    if status != 0 or not isinstance(post, dict) or str(post.get("id")) != post_id:
        raise ServiceError("source_unavailable", "This TikTok photo post is unavailable.")
    images = (post.get("imagePost") or {}).get("images")
    if not isinstance(images, list) or not images:
        raise ServiceError("not_photo_post", "This link does not contain a supported photo post.")
    if len(images) > MAX_ITEMS:
        raise ServiceError("photo_limit", f"This build supports up to {MAX_ITEMS} photos per post.")
    private = []
    for image in images:
        if not isinstance(image, dict):
            raise ServiceError("photo_source_unavailable", "Photo metadata is unavailable.")
        if image.get("hasWatermark") or image.get("watermarked"):
            raise ServiceError("photo_source_unavailable", "A photo is reported as watermarked.")
        width, height = image.get("imageWidth"), image.get("imageHeight")
        if any(type(value) is not int or value <= 0 for value in (width, height)):
            raise ServiceError("photo_source_unavailable", "Photo dimensions are unavailable.")
        if width * height > Image.MAX_IMAGE_PIXELS:
            raise ServiceError("image_limit", "A photo exceeds the 24 megapixel limit.")
        image_url = image.get("imageURL")
        urls = image_url.get("urlList") if isinstance(image_url, dict) else None
        if not isinstance(urls, list) or not urls:
            raise ServiceError(
                "photo_source_unavailable", "An original photo source is unavailable."
            )
        private.append(
            {"urls": [check_media_url(u) for u in urls[:5]], "width": width, "height": height}
        )
    return {
        "platform": "TikTok",
        "kind": "photos",
        "url": url,
        "source_id": post_id,
        "title": str(post.get("desc") or f"TikTok photos #{post_id}")[:500],
        "author": post["author"].get("uniqueId") if isinstance(post.get("author"), dict) else None,
        "thumbnail": None,
        "duration": None,
        "choices": [],
        "item_count": len(images),
        "_images": private,
    }


def fetch_image(urls, target, limit, platform="TikTok"):
    def check(url):
        return check_media_url(url) if platform == "TikTok" else check_media_url(url, platform)

    opener = build_opener(sources.NoRedirects(), HTTPSHandler(context=ssl.create_default_context()))
    for original in urls:
        url = original
        try:
            for _ in range(5):
                check(url)
                request = Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://www.instagram.com/"
                        if platform == "Instagram"
                        else "https://www.tiktok.com/",
                        "Accept-Encoding": "identity",
                    },
                )
                try:
                    response = opener.open(request, timeout=20)
                except HTTPError as error:
                    response = error
                with response:
                    if response.code in {301, 302, 303, 307, 308}:
                        url = check(urljoin(url, response.headers.get("Location", "")))
                        continue
                    if response.code != 200:
                        break
                    declared = response.headers.get("Content-Length")
                    if declared and int(declared) > limit:
                        raise ServiceError(
                            "file_limit", "A photo exceeds the configured size limit."
                        )
                    size = 0
                    with target.open("wb") as output:
                        while chunk := response.read(64 * 1024):
                            size += len(chunk)
                            if size > limit:
                                raise ServiceError(
                                    "file_limit", "A photo exceeds the configured size limit."
                                )
                            output.write(chunk)
                    if not size:
                        break
                    return
        except ServiceError:
            target.unlink(missing_ok=True)
            raise
        except (OSError, URLError, ValueError):
            pass
        target.unlink(missing_ok=True)
    raise ServiceError(
        "photo_download_failed",
        "A photo could not be downloaded. Check source access and analyze again.",
    )


def verify_photo(path, expected):
    metadata = media.verify(path)
    if metadata["kind"] != "image" or metadata["format"] not in {"jpeg", "png", "webp"}:
        raise ServiceError(
            "invalid_photo", "The photo source did not return a supported still image."
        )
    if any(
        expected.get(key) is not None and metadata[key] != expected[key]
        for key in ("width", "height")
    ):
        raise ServiceError(
            "quality_mismatch", "A photo does not match its reported dimensions. Analyze again."
        )
    try:
        with Image.open(path) as image:
            image.load()
    except (OSError, ValueError):
        raise ServiceError("invalid_photo", "This photo could not be fully decoded.") from None
    return metadata


def preview(source, target):
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGBA")
        image.thumbnail((320, 320), Image.Resampling.LANCZOS)
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        background.save(target, format="JPEG", quality=80)
    return media.probe(target)


def cache_image(image, store, task_id, directory, position, title, platform="TikTok", report=None):
    path = directory / f"source-{position:02}"
    limit = min(MAX_PHOTO_BYTES, store.config.max_file_bytes)
    if platform == "TikTok":
        fetch_image(image["urls"], path, limit)
    else:
        fetch_image(image["urls"], path, limit, platform)
    if report:
        report("verifying")
    metadata = verify_photo(path, image)
    extension = ".jpg" if metadata["format"] == "jpeg" else "." + metadata["format"]
    original = path.with_suffix(extension)
    path.rename(original)
    name = media.safe_name(title, extension, f"photo {position:02}")
    source_id = store.add_asset(original, name, metadata, task_id)
    small = directory / f"preview-{position:02}.jpg"
    small_id = store.add_asset(
        small, f"Photo {position} preview.jpg", preview(original, small), task_id
    )
    with original.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "id": f"photo_{position}",
        "position": position,
        "width": metadata["width"],
        "height": metadata["height"],
        "format": metadata["format"],
        "size": original.stat().st_size,
        "sha256": digest,
        "source_asset_id": source_id,
        "preview_asset_id": small_id,
    }


def prepare_analysis(result, store, task_id, directory, report):
    images = result.pop("_images")
    items, total = [], 0
    for index, image in enumerate(images, 1):
        report("downloading", 100 * (index - 1) / len(images))
        item = cache_image(
            image, store, task_id, directory, index, result["title"], result["platform"], report
        )
        total += item["size"]
        if total > store.config.max_file_bytes:
            raise ServiceError(
                "file_limit", "The photo post exceeds the configured combined file limit."
            )
        items.append(item)
    result["items"] = items
    return result


def copy_snapshot(item, store, directory):
    source = store.asset(item["source_asset_id"], allow_expired=True)
    target = directory / (f"photo-{item['position']:02}" + Path(source["name"]).suffix)
    shutil.copyfile(source["path"], target)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != item["sha256"]:
        raise ServiceError(
            "photo_snapshot_changed", "A retained photo changed. Analyze this post again."
        )
    return target, source["name"], verify_photo(target, item)


def make_archive(paths, store, task_id, directory, title, descriptor):
    if len(paths) < 2:
        return None
    total = sum(path.stat().st_size for path, name in paths)
    if total + len(paths) * 1024 > store.config.max_file_bytes:
        raise ServiceError("file_limit", "The selected ZIP would exceed the configured file limit.")
    archive = directory / "selected.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
        for path, name in paths:
            output.write(path, arcname=name)
    with zipfile.ZipFile(archive) as check:
        if check.testzip() is not None or len(check.infolist()) != len(paths):
            raise ServiceError("invalid_result", "The archive could not be verified.")
    if archive.stat().st_size > store.config.max_file_bytes:
        raise ServiceError("file_limit", "The archive exceeds the configured file limit.")
    return store.add_asset(
        archive,
        media.safe_name(title, ".zip", descriptor),
        {"kind": "archive", "format": "zip", "item_count": len(paths), "has_audio": False},
        task_id,
    )


def deliver(analysis, selected, store, task_id, directory, report):
    items = [item for item in analysis["items"] if item["id"] in selected]
    files, paths, total = [], [], 0
    for index, item in enumerate(items, 1):
        report("preparing", 100 * (index - 1) / len(items))
        target, name, metadata = copy_snapshot(item, store, directory)
        total += target.stat().st_size
        if total > store.config.max_file_bytes:
            raise ServiceError(
                "file_limit", "The selected photos exceed the configured combined limit."
            )
        asset_id = store.add_asset(target, name, metadata, task_id)
        small = directory / f"preview-{item['position']:02}.jpg"
        small_id = store.add_asset(small, "Photo preview.jpg", preview(target, small), task_id)
        files.append(
            {
                "item_id": item["id"],
                "position": item["position"],
                "asset_id": asset_id,
                "preview_asset_id": small_id,
                "name": name,
                "width": metadata["width"],
                "height": metadata["height"],
                "format": metadata["format"],
                "size": target.stat().st_size,
            }
        )
        paths.append((target, name))
    result = {"files": files, "item_count": len(files)}
    archive_id = make_archive(
        paths, store, task_id, directory, analysis["title"], f"{len(files)} photos"
    )
    if archive_id:
        result["archive_asset_id"] = archive_id
    return result
