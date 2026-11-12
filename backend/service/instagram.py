"""Individual Instagram publications, bounded images and selected mixed-carousel delivery."""

from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
from urllib.parse import urlsplit

import yt_dlp
from PIL import Image
from yt_dlp.extractor.instagram import InstagramIE

from . import media, photos, sources
from .errors import ServiceError, extractor_error


class CapturedPublication(Exception):
    def __init__(self, product, video_id):
        self.product, self.video_id = product, video_id
        super().__init__("Instagram publication metadata captured")


class PublicationIE(InstagramIE):
    def _extract_product(self, product_info, video_id=None, get_comments=True):
        # Stop before the video-only extractor discards photos or expands a carousel.
        # This private adapter is tested against the locked yt-dlp version.
        raise CapturedPublication(product_info, video_id)


def best_image(product, required=True):
    candidates = (product.get("image_versions2") or {}).get("candidates")
    if not isinstance(candidates, list) or not candidates:
        if not required:
            return None
        raise ServiceError(
            "photo_source_unavailable", "An original Instagram photo is unavailable."
        )
    usable = [
        c
        for c in candidates
        if isinstance(c, dict)
        and isinstance(c.get("url"), str)
        and all(type(c.get(k)) is int and c[k] > 0 for k in ("width", "height"))
    ]
    if not usable:
        # Logged-out responses can expose ordered image URLs without dimensions.
        # Use the first offered source, without guessing interchangeable mirrors;
        # decoding supplies its actual dimensions and still enforces pixel limits.
        first = candidates[0]
        if not isinstance(first, dict) or not isinstance(first.get("url"), str):
            raise ServiceError("photo_source_unavailable", "Instagram photo data is unavailable.")
        dimensions = {k: first.get(k) for k in ("width", "height")}
        if any(v is not None and (type(v) is not int or v <= 0) for v in dimensions.values()):
            raise ServiceError(
                "photo_source_unavailable", "Instagram photo dimensions are invalid."
            )
        return dimensions | {"urls": [photos.check_media_url(first["url"], "Instagram")]}
    best = max(usable, key=lambda c: c["width"] * c["height"])
    if best["width"] * best["height"] > Image.MAX_IMAGE_PIXELS:
        raise ServiceError("image_limit", "A photo exceeds the 24 megapixel limit.")
    mirrors = [c for c in usable if (c["width"], c["height"]) == (best["width"], best["height"])]
    return {
        "width": best["width"],
        "height": best["height"],
        "urls": [photos.check_media_url(c["url"], "Instagram") for c in mirrors[:5]],
    }


def read_publication(url, config, engine=None):
    """Return private native entries in memory only; never persist signed media URLs."""
    try:
        with (
            yt_dlp.YoutubeDL(sources.options(config))
            if engine is None
            else nullcontext(engine) as ydl
        ):
            adapter = PublicationIE(ydl)
            try:
                raw = adapter.extract(url)
            except CapturedPublication as captured:
                product = captured.product
                if isinstance(product, list) and len(product) == 1:
                    product = product[0]
                if not isinstance(product, dict):
                    raise ServiceError(
                        "source_page_unreadable", "Instagram returned incomplete post metadata."
                    )
                children = product.get("carousel_media")
                if children is not None:
                    if not isinstance(children, list) or not children:
                        raise ServiceError(
                            "source_page_unreadable", "Instagram returned an incomplete carousel."
                        )
                    if len(children) > photos.MAX_ITEMS:
                        raise ServiceError(
                            "photo_limit",
                            f"This build supports up to {photos.MAX_ITEMS} items per post.",
                        )
                    count = product.get("carousel_media_count")
                    if count is not None and count != len(children):
                        raise ServiceError(
                            "source_page_unreadable",
                            "Instagram did not return every carousel item.",
                        )
                else:
                    children = [product]
                if any(
                    not isinstance(c, dict) or c.get("media_type") not in {1, 2} for c in children
                ):
                    raise ServiceError(
                        "source_page_unreadable", "Instagram returned an unsupported post item."
                    )
                native = InstagramIE._extract_product(
                    adapter,
                    product,
                    video_id=captured.video_id or urlsplit(url).path.rstrip("/").split("/")[-1],
                    get_comments=False,
                )
                entries = native.get("entries") if native.get("_type") == "playlist" else [native]
                if not isinstance(entries, list) or len(entries) != len(children):
                    raise ServiceError(
                        "source_page_unreadable", "Instagram did not return every carousel item."
                    )
                ids = [entry.get("id") for entry in entries]
                if not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
                    raise ServiceError(
                        "source_page_unreadable", "Instagram returned invalid item identities."
                    )
                for child, entry in zip(children, entries):
                    if child.get("media_type") == 2 and child.get("has_audio") is True:
                        progressive = {
                            v.get("url")
                            for v in child.get("video_versions", [])
                            if isinstance(v, dict)
                        }
                        for fmt in entry.get("formats", []):
                            if fmt.get("url") in progressive and fmt.get("acodec") is None:
                                # The post declares audio but gives no progressive codec.
                                # Keep that distinction; final decoding must confirm audio.
                                fmt["acodec"] = "unknown"
                return native, [
                    {
                        "raw": entry,
                        "kind": "image" if c["media_type"] == 1 else "video",
                        "image": best_image(c, required=c["media_type"] == 1),
                    }
                    for c, entry in zip(children, entries)
                ]
            # Compatibility with a direct native video result; no generic collection expansion.
            sources.require_single_instagram_video(raw)
            return raw, [{"raw": raw, "kind": "video", "image": None}]
    except (yt_dlp.utils.ExtractorError, yt_dlp.utils.DownloadError) as error:
        raise extractor_error(error) from None


def analyze(url, config):
    root, entries = read_publication(url, config)
    with yt_dlp.YoutubeDL(sources.options(config)) as ydl:
        if len(entries) == 1 and entries[0]["kind"] == "video" and root.get("_type") != "playlist":
            return sources.normalize(ydl.process_ie_result(entries[0]["raw"], download=False), url)
        result = {
            "url": url,
            "source_id": root["id"],
            "platform": "Instagram",
            "title": str(root.get("description") or root.get("title") or "Instagram post")[:500],
            "author": root.get("uploader") or root.get("channel"),
            "thumbnail": None,
            "duration": None,
            "choices": [],
            "item_count": len(entries),
        }
        if all(entry["kind"] == "image" for entry in entries):
            return result | {"kind": "photos", "_images": [e["image"] for e in entries]}
        private = []
        for entry in entries:
            item = {"kind": entry["kind"], "source_id": entry["raw"]["id"], "image": entry["image"]}
            if item["kind"] == "video":
                normalized = sources.normalize(
                    ydl.process_ie_result(entry["raw"], download=False), url
                )
                if normalized["kind"] != "video":
                    raise ServiceError(
                        "no_formats",
                        "A carousel video has no usable video source. Analyze again after checking source access.",
                    )
                item.update({"choices": normalized["choices"], "duration": normalized["duration"]})
            private.append(item)
        return result | {"kind": "gallery", "_entries": private}


def prepare_analysis(result, store, task_id, directory, report):
    private = result.pop("_entries")
    items, total = [], 0
    for position, entry in enumerate(private, 1):
        item = {k: v for k, v in entry.items() if k != "image"}
        item.update({"id": f"media_{position}", "position": position})
        if entry["image"]:
            report("downloading", 100 * (position - 1) / len(private))
            snapshot = photos.cache_image(
                entry["image"],
                store,
                task_id,
                directory,
                position,
                result["title"],
                "Instagram",
                report,
            )
            total += snapshot["size"]
            if total > store.config.max_file_bytes:
                raise ServiceError(
                    "file_limit", "The post images exceed the configured combined limit."
                )
            if item["kind"] == "image":
                item.update({k: v for k, v in snapshot.items() if k not in {"id", "position"}})
            else:
                item["poster"] = snapshot
                item["preview_asset_id"] = snapshot["preview_asset_id"]
        items.append(item)
    result["items"] = items
    return result


def deliver(analysis, selections, store, task_id, directory, report):
    by_id = {s["item_id"]: s for s in selections}
    selected = [i for i in analysis["items"] if i["id"] in by_id]
    fresh = {}
    if any(item["kind"] == "video" for item in selected):
        report("analyzing")
        root, entries = read_publication(analysis["url"], store.config)
        if root.get("id") != analysis["source_id"] or [e["raw"].get("id") for e in entries] != [
            i["source_id"] for i in analysis["items"]
        ]:
            raise ServiceError("source_changed", "This carousel changed. Analyze the post again.")
        fresh = {e["raw"]["id"]: e for e in entries}
    paths, files, total = [], [], 0
    for item in selected:
        report("preparing")
        position = item["position"]
        target_dir = directory / f"item-{position:02}"
        target_dir.mkdir()
        preview_id = None
        if item["kind"] == "image":
            path, name, metadata = photos.copy_snapshot(item, store, target_dir)
        else:
            entry = fresh[item["source_id"]]
            if entry["kind"] != "video":
                raise ServiceError(
                    "source_changed", "A carousel item changed. Analyze the post again."
                )
            selection = by_id[item["id"]]
            choice = deepcopy(next(c for c in item["choices"] if c["id"] == selection["choice_id"]))
            remaining = store.config.max_file_bytes - total
            if remaining <= 0:
                raise ServiceError(
                    "file_limit", "The selected post exceeds the configured combined limit."
                )
            path = sources._download_one(
                analysis | {"source_id": item["source_id"]},
                choice,
                selection["profile"],
                selection["bitrate"],
                target_dir,
                replace(store.config, max_file_bytes=remaining),
                report,
                raw_info=deepcopy(entry["raw"]),
            )
            path, metadata = media.verify_selected_source(
                path, choice, selection["profile"], target_dir, report
            )
            descriptor = (
                f"item {position:02} MP3 {selection['bitrate']}kbps"
                if selection["profile"] == "mp3"
                else f"video {position:02}"
                + (f" {sources.quality_height(choice)}p" if sources.quality_height(choice) else "")
            )
            name = media.safe_name(analysis["title"], path.suffix, descriptor)
        total += path.stat().st_size
        if total > store.config.max_file_bytes:
            raise ServiceError(
                "file_limit", "The selected post exceeds the configured combined limit."
            )
        asset_id = store.add_asset(path, name, metadata, task_id)
        poster = item if item["kind"] == "image" else item.get("poster")
        if poster:
            if item["kind"] == "image":
                poster_path = path
            else:
                poster_path, _, _ = photos.copy_snapshot(poster, store, target_dir)
            small = target_dir / "preview.jpg"
            preview_id = store.add_asset(
                small, f"Item {position} preview.jpg", photos.preview(poster_path, small), task_id
            )
            if item["kind"] != "image":
                poster_path.unlink()
        files.append(
            {
                "item_id": item["id"],
                "position": position,
                "kind": metadata["kind"],
                "asset_id": asset_id,
                "preview_asset_id": preview_id,
                "name": name,
                "width": metadata.get("width"),
                "height": metadata.get("height"),
                "format": path.suffix.lstrip("."),
                "size": path.stat().st_size,
            }
        )
        paths.append((path, name))
    result = {"kind": "gallery", "files": files, "item_count": len(files)}
    archive = photos.make_archive(
        paths, store, task_id, directory, analysis["title"], f"{len(files)} files"
    )
    if archive:
        result["archive_asset_id"] = archive
    return result
