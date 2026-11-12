"""One native Pinterest pin, using the locked extractor's Pin API and formats."""

from contextlib import nullcontext
from urllib.parse import urlsplit

import yt_dlp
from PIL import Image

from . import photos, sources
from .errors import ServiceError, extractor_error


def best_image(data):
    images = data.get("images")
    if not isinstance(images, dict):
        raise ServiceError("photo_source_unavailable", "Pinterest did not return an image source.")
    candidates = [item for item in images.values() if isinstance(item, dict) and item.get("url")]
    original = images.get("orig")
    if not isinstance(original, dict) or not original.get("url"):
        known = [
            i
            for i in candidates
            if all(type(i.get(k)) is int and i[k] > 0 for k in ("width", "height"))
        ]
        if not known:
            raise ServiceError(
                "photo_source_unavailable", "Pinterest did not return an original or sized image."
            )
        original = max(known, key=lambda i: i["width"] * i["height"])
    dims = {key: original.get(key) for key in ("width", "height")}
    if any(value is not None and (type(value) is not int or value <= 0) for value in dims.values()):
        raise ServiceError(
            "photo_source_unavailable", "Pinterest returned invalid image dimensions."
        )
    if all(dims.values()) and dims["width"] * dims["height"] > Image.MAX_IMAGE_PIXELS:
        raise ServiceError("image_limit", "This pin exceeds the 24 megapixel image limit.")
    return {
        "urls": [photos.check_media_url(original["url"], "Pinterest")],
        **dims,
        "allow_animation": True,
        **({"required_format": "gif"} if (data.get("embed") or {}).get("type") == "gif" else {}),
    }


def read_pin(url, config, engine=None):
    pin_id = urlsplit(url).path.strip("/").split("/")[-1]
    try:
        with (
            nullcontext(engine)
            if engine is not None
            else yt_dlp.YoutubeDL(sources.options(config)) as ydl
        ):
            ie = ydl.get_info_extractor("Pinterest")
            ie.initialize()
            response = ie._call_api(
                "Pin", pin_id, {"field_set_key": "unauth_react_main_pin", "id": pin_id}
            )
            pin = response.get("data") if isinstance(response, dict) else None
            if not isinstance(pin, dict) or str(pin.get("id")) != pin_id:
                raise ServiceError(
                    "source_unavailable",
                    "This Pinterest pin is unavailable. Check the pin link and access.",
                )
            if pin.get("privacy") not in {None, "public"}:
                raise ServiceError("access_required", "This Pinterest pin requires owner access.")
            story = pin.get("story_pin_data") or {}
            if not isinstance(story, dict):
                raise ServiceError(
                    "source_page_unreadable", "Pinterest returned unreadable pin metadata."
                )
            pages = story.get("pages") or []
            if (
                not isinstance(pages, list)
                or any(not isinstance(p, dict) for p in pages)
                or type(story.get("page_count", 0)) is not int
            ):
                raise ServiceError(
                    "source_page_unreadable", "Pinterest returned unreadable page metadata."
                )
            if pin.get("carousel_data") or len(pages) > 1 or (story.get("page_count") or 0) > 1:
                raise ServiceError(
                    "pinterest_multi_item_unsupported",
                    "This pin contains multiple pages or carousel items. This stage supports single image, GIF or video pins.",
                )
            # Never follow an embedded player to another service or save its cover as the pin.
            embed = pin.get("embed") or {}
            if not isinstance(embed, dict):
                raise ServiceError(
                    "source_page_unreadable", "Pinterest returned unreadable embed metadata."
                )
            if embed.get("src"):
                if embed.get("type") == "gif":
                    photos.check_media_url(embed["src"], "Pinterest")
                else:
                    raise ServiceError(
                        "pinterest_external_embed",
                        "This pin embeds media from another site. Use the original supported source link instead.",
                    )
            videos = pin.get("videos") or {}
            if not isinstance(videos, dict):
                raise ServiceError(
                    "source_page_unreadable", "Pinterest returned unreadable video metadata."
                )
            lists = [videos.get("video_list") or {}]
            declared_video = bool(videos) or pin.get("is_video") is True
            for page in pages:
                blocks = page.get("blocks") or []
                if not isinstance(blocks, list) or any(not isinstance(b, dict) for b in blocks):
                    raise ServiceError(
                        "source_page_unreadable", "Pinterest returned unreadable block metadata."
                    )
                media_blocks = [
                    b for b in blocks if b.get("video") or b.get("image") or b.get("audio")
                ]
                if len(media_blocks) > 1 or any(b.get("audio") for b in media_blocks):
                    raise ServiceError(
                        "pinterest_multi_item_unsupported",
                        "This pin has multiple media blocks or a separate audio layer. Use a single image, GIF or video pin.",
                    )
                lists.extend((b.get("video") or {}).get("video_list") or {} for b in media_blocks)
                declared_video = declared_video or any(b.get("video") is not None for b in blocks)
            if any(not isinstance(v, dict) for v in lists):
                raise ServiceError(
                    "source_page_unreadable", "Pinterest returned unreadable format metadata."
                )
            has_video = any(lists) or declared_video
            if not has_video:
                return pin, None
            # Validate native video/manifests before the upstream parser can request them.
            for video_list in lists:
                for value in video_list.values():
                    if isinstance(value, dict) and value.get("url"):
                        photos.check_media_url(value["url"], "Pinterest")
            raw = ie._extract_video(pin)
            if raw.get("_type") or not raw.get("formats"):
                raise ServiceError(
                    "no_formats", "Pinterest did not return a usable video stream for this pin."
                )
            for item in raw["formats"]:
                # Native progressive MP4 metadata omits codecs and audio presence.
                # Manifest formats retain their explicit codec/audio facts.
                if item.get("width") and item.get("height") and not item.get("vcodec"):
                    item["vcodec"] = "unknown"
                    item["acodec"] = "unknown"
            return pin, raw
    except (yt_dlp.utils.ExtractorError, yt_dlp.utils.DownloadError) as error:
        raise extractor_error(error) from None


def analyze(url, config):
    with yt_dlp.YoutubeDL(sources.options(config)) as ydl:
        pin, raw = read_pin(url, config, ydl)
        if raw is not None:
            try:
                return sources.normalize(ydl.process_ie_result(raw, download=False), url)
            except yt_dlp.utils.DownloadError as error:
                raise extractor_error(error) from None
        author = pin.get("closeup_attribution") or pin.get("pinner") or {}
        return {
            "url": url,
            "source_id": str(pin["id"]),
            "platform": "Pinterest",
            "kind": "photos",
            "title": str(
                pin.get("title")
                or pin.get("grid_title")
                or pin.get("description")
                or f"Pinterest pin #{pin['id']}"
            )[:500],
            "author": author.get("full_name") or author.get("username"),
            "thumbnail": None,
            "duration": None,
            "choices": [],
            "item_count": 1,
            "_images": [best_image(pin)],
        }
