import importlib.metadata
import shutil
import subprocess
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import media, photos
from .config import Settings, settings
from .diagnostics import runtime_status
from .errors import ServiceError
from .sources import THUMBNAIL_DOMAINS, platform_for, tiktok_watermarked, validate_url
from .store import Store
from .worker import disk_usage

ID = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]


class ControlledRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyzeRequest(ControlledRequest):
    url: str = Field(min_length=1, max_length=2048)


class DownloadRequest(ControlledRequest):
    analysis_id: ID
    choice_id: str = Field(pattern=r"^option_[0-9]{1,4}$")
    profile: Literal["original", "compatible", "mp3"] = "original"
    bitrate: Literal[128, 192, 320] = 192


class PhotoDownloadRequest(ControlledRequest):
    analysis_id: ID
    item_ids: list[Annotated[str, Field(pattern=r"^photo_[1-9][0-9]?$", strict=True)]] = Field(
        min_length=1, max_length=photos.MAX_ITEMS
    )


class PostSelection(ControlledRequest):
    item_id: str = Field(pattern=r"^media_[1-9][0-9]?$")
    choice_id: str | None = Field(default=None, pattern=r"^option_[0-9]{1,4}$")
    profile: Literal["original", "compatible", "mp3"] = "original"
    bitrate: Literal[128, 192, 320] = 192


class PostDownloadRequest(ControlledRequest):
    analysis_id: ID
    selections: list[PostSelection] = Field(min_length=1, max_length=photos.MAX_ITEMS)


def validate_download_profile(choice, profile, platform):
    if platform == "TikTok":
        if tiktok_watermarked(choice) or not choice["has_audio"]:
            raise ServiceError(
                "tiktok_source_unavailable",
                "Analyze again to choose a source without a reported watermark and with clip audio.",
            )
        if profile == "original":
            profile = "compatible"
    if profile in {"mp3", "compatible"} and not choice["has_audio"]:
        raise ServiceError("no_audio", "Choose a format with an audio stream.")
    if profile == "compatible" and (
        choice.get("kind") != "video" or not {"libx264", "aac"}.issubset(media.encoders())
    ):
        raise ServiceError(
            "incompatible_conversion",
            "Compatible MP4 delivery requires a video source and H.264/AAC encoders.",
        )
    if (profile in {"mp3", "compatible"} or choice["operation"] == "merge") and not shutil.which(
        "ffmpeg"
    ):
        raise ServiceError("missing_ffmpeg", "FFmpeg is required. Check server diagnostics.")
    return profile


class Parameters(ControlledRequest):
    output: Literal[
        "mp4", "webm", "mkv", "mov", "mp3", "m4a", "wav", "flac", "ogg", "gif", "jpg", "png", "webp"
    ]
    bitrate: Literal[128, 192, 320] = 192
    start: float = Field(default=0, ge=0, le=7200, allow_inf_nan=False)
    duration: float = Field(default=5, ge=0.1, le=15, allow_inf_nan=False)
    fps: int = Field(default=12, ge=1, le=24)
    width: int = Field(default=480, ge=64, le=720)


class ConversionRequest(ControlledRequest):
    asset_id: ID
    parameters: Parameters


def public_task(task):
    return {k: v for k, v in task.items() if k not in {"payload", "cancel_requested"}} | {
        "expired": bool(task["expires_at"] and task["expires_at"] < time.time())
    }


def public_asset(asset):
    return {k: v for k, v in asset.items() if k != "path"} | {
        "operations": media.capabilities(asset["metadata"]) if asset["metadata"] else []
    }


@lru_cache(maxsize=1)
def tool_versions():
    versions = {}
    for name in ("yt-dlp", "yt-dlp-ejs", "curl-cffi", "pillow"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "missing"
    for name in ("ffmpeg", "ffprobe", "node"):
        try:
            result = subprocess.run(
                [name, "--version" if name == "node" else "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            versions[name] = result.stdout.splitlines()[0][:150]
        except (OSError, subprocess.SubprocessError):
            versions[name] = "missing"
    return versions


def create_app(config: Settings = settings):
    store = Store(config)
    app = FastAPI(title="Download & Convert", version="0.1.0")
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.allowed_hosts))

    @app.exception_handler(ServiceError)
    async def known_error(request: Request, error: ServiceError):
        return JSONResponse(
            {"detail": {"code": error.code, "message": error.message}}, status_code=error.status
        )

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and origin
            and urlsplit(origin).netloc != request.headers.get("host")
        ):
            return JSONResponse(
                {
                    "detail": {
                        "code": "invalid_origin",
                        "message": "Use the service from its own interface.",
                    }
                },
                status_code=403,
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        thumbnail_origins = " ".join(
            "https://*." + domain for domains in THUMBNAIL_DOMAINS.values() for domain in domains
        )
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; img-src 'self' {thumbnail_origins} data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    @app.get("/api/health")
    def health():
        with store.connect() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "worker_online": store.worker_online()}

    @app.get("/api/settings")
    def server_settings():
        return {
            "versions": tool_versions(),
            "source_transport": runtime_status(),
            "worker_online": store.worker_online(),
            "max_file_bytes": config.max_file_bytes,
            "max_storage_bytes": config.max_storage_bytes,
            "used_bytes": disk_usage(config.data_dir / "files"),
            "ttl_seconds": config.ttl,
            "job_timeout_seconds": config.job_timeout,
            "concurrency": 1,
            "cookies_configured": bool(config.cookie_file),
            "platforms": [
                {"name": "YouTube", "status": "implemented; see live verification report"},
                {
                    "name": "SoundCloud",
                    "status": "public unprotected tracks; see live verification report",
                },
                {
                    "name": "TikTok",
                    "status": "individual videos and photo posts verified by owner; selected files and ZIP available",
                },
                {
                    "name": "Instagram",
                    "status": "individual Reels/video posts, photos, photo-carousel subsets and retained video-to-MP3 verified by owner; see verification reports",
                },
                {
                    "name": "Pinterest",
                    "status": "individual image/GIF/video pins and pin.it links implemented; see verification reports",
                },
            ],
            "presets": [
                {
                    "name": "Original",
                    "description": "Exact source format; merge separate tracks without re-encoding.",
                },
                {
                    "name": "Audio MP3",
                    "description": "MP3 at 128, 192 or 320 kbps. Does not restore lost source detail.",
                },
                {
                    "name": "Smaller Video",
                    "description": "H.264 CRF 25 or VP9 CRF 34; actual size depends on the source.",
                },
                {
                    "name": "GIF Clip",
                    "description": "Up to 15 seconds, 24 FPS and 720 pixels wide.",
                },
            ],
        }

    @app.get("/api/tasks")
    def tasks():
        return [public_task(t) for t in store.list()]

    @app.get("/api/tasks/{task_id}")
    def task(task_id: ID):
        return public_task(store.get(task_id))

    @app.post("/api/analyze", status_code=202)
    def analyze(body: AnalyzeRequest):
        url = validate_url(body.url)
        return public_task(
            store.create("analyze", f"Analyze {platform_for(url)} link", {"url": url})
        )

    @app.post("/api/downloads", status_code=202)
    def download(body: DownloadRequest):
        source = store.get(body.analysis_id)
        if (
            source["kind"] != "analyze"
            or source["state"] != "completed"
            or not source["result"]
            or source["expires_at"] < time.time()
        ):
            raise ServiceError(
                "analysis_expired", "Analyze the link again before choosing a format."
            )
        choice = next((c for c in source["result"]["choices"] if c["id"] == body.choice_id), None)
        if choice is None:
            raise ServiceError("invalid_format", "This format does not belong to that analysis.")
        profile = validate_download_profile(choice, body.profile, source["result"].get("platform"))
        return public_task(
            store.create(
                "download",
                source["result"]["title"],
                {
                    "analysis": source["result"],
                    "choice_id": body.choice_id,
                    "profile": profile,
                    "bitrate": body.bitrate,
                },
            )
        )

    @app.post("/api/photo-downloads", status_code=202)
    def photo_download(body: PhotoDownloadRequest):
        source = store.get(body.analysis_id)
        analysis = source["result"]
        if (
            source["kind"] != "analyze"
            or source["state"] != "completed"
            or not analysis
            or source["expires_at"] < time.time()
        ):
            raise ServiceError(
                "analysis_expired", "Analyze this photo post again before choosing items."
            )
        if analysis.get("kind") != "photos" or analysis.get("platform") not in {
            "TikTok",
            "Instagram",
            "Pinterest",
        }:
            raise ServiceError(
                "invalid_selection", "Choose photos from a completed photo analysis."
            )
        ids = set(body.item_ids)
        selected = [item for item in analysis["items"] if item["id"] in ids]
        if len(ids) != len(body.item_ids) or len(selected) != len(ids):
            raise ServiceError("invalid_selection", "Choose each photo once from this analysis.")
        for item in selected:
            try:
                store.asset(item["source_asset_id"])
            except ServiceError:
                raise ServiceError(
                    "analysis_expired", "A retained photo expired. Analyze this post again."
                ) from None
        return public_task(
            store.create(
                "download",
                analysis["title"],
                {
                    "analysis": analysis,
                    "item_ids": [item["id"] for item in selected],
                    "asset_ids": [item["source_asset_id"] for item in selected],
                },
            )
        )

    @app.post("/api/post-downloads", status_code=202)
    def post_download(body: PostDownloadRequest):
        source = store.get(body.analysis_id)
        analysis = source["result"]
        if (
            source["kind"] != "analyze"
            or source["state"] != "completed"
            or not analysis
            or source["expires_at"] < time.time()
        ):
            raise ServiceError("analysis_expired", "Analyze this post again before choosing items.")
        if analysis.get("kind") != "gallery" or analysis.get("platform") != "Instagram":
            raise ServiceError(
                "invalid_selection", "Choose items from a completed Instagram post analysis."
            )
        ids = [s.item_id for s in body.selections]
        items = {i["id"]: i for i in analysis["items"]}
        if len(set(ids)) != len(ids) or any(i not in items for i in ids):
            raise ServiceError("invalid_selection", "Choose each item once from this analysis.")
        inputs = []
        for selection in body.selections:
            item = items[selection.item_id]
            if item["kind"] == "image":
                if selection.choice_id is not None or selection.profile != "original":
                    raise ServiceError(
                        "invalid_selection", "Photos are delivered as original images."
                    )
                snapshot = item
            else:
                choice = next((c for c in item["choices"] if c["id"] == selection.choice_id), None)
                if choice is None:
                    raise ServiceError(
                        "invalid_format", "Choose a format belonging to this video item."
                    )
                validate_download_profile(choice, selection.profile, "Instagram")
                snapshot = item.get("poster")
            if snapshot:
                inputs.extend([snapshot["source_asset_id"], snapshot["preview_asset_id"]])
        for asset_id in inputs:
            try:
                store.asset(asset_id)
            except ServiceError:
                raise ServiceError(
                    "analysis_expired", "A retained post image expired. Analyze the post again."
                ) from None
        return public_task(
            store.create(
                "download",
                analysis["title"],
                {
                    "analysis": analysis,
                    "selections": [s.model_dump() for s in body.selections],
                    "asset_ids": inputs,
                },
            )
        )

    @app.post("/api/uploads", status_code=202)
    async def upload(request: Request):
        name = media.safe_name(unquote(request.headers.get("x-filename", "upload"))[:200], "")
        directory = config.data_dir / "files" / uuid.uuid4().hex
        directory.mkdir()
        path, size = directory / "input", 0
        try:
            with path.open("wb") as target:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > config.max_file_bytes:
                        raise ServiceError(
                            "file_limit", "This upload exceeds the configured file limit.", 413
                        )
                    if (
                        disk_usage(config.data_dir / "files") + len(chunk)
                        > config.max_storage_bytes
                    ):
                        raise ServiceError(
                            "storage_full", "Storage is full. Wait for old results to expire.", 507
                        )
                    target.write(chunk)
            if not size:
                raise ServiceError("empty_file", "Select a non-empty media file.")
            asset_id = store.add_asset(path, name)
            try:
                result = store.create("inspect", name, {"asset_id": asset_id})
            except Exception:
                with store.connect() as db:
                    db.execute("DELETE FROM assets WHERE id=?", (asset_id,))
                raise
            return public_task(result)
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    @app.get("/api/assets/{asset_id}")
    def asset(asset_id: ID):
        return public_asset(store.asset(asset_id))

    @app.get("/api/assets/{asset_id}/file")
    def file(asset_id: ID):
        source = store.asset(asset_id)
        return FileResponse(
            source["path"], filename=source["name"], media_type="application/octet-stream"
        )

    @app.get("/api/assets/{asset_id}/preview")
    def preview(asset_id: ID):
        source = store.asset(asset_id)
        metadata = source["metadata"] or {}
        if metadata.get("kind") not in {"image", "animation"} or metadata.get("format") not in {
            "jpeg",
            "png",
            "webp",
            "gif",
        }:
            raise ServiceError(
                "preview_unavailable", "An image preview is not available for this file."
            )
        return FileResponse(source["path"], media_type="image/" + metadata["format"])

    @app.post("/api/conversions", status_code=202)
    def conversion(body: ConversionRequest):
        source = store.asset(body.asset_id)
        if not source["metadata"]:
            raise ServiceError("inspection_pending", "Wait for file inspection to finish.")
        media.validate_conversion(source["metadata"], body.parameters.model_dump())
        return public_task(
            store.create(
                "convert",
                source["name"],
                {"asset_id": body.asset_id, "parameters": body.parameters.model_dump()},
            )
        )

    @app.post("/api/tasks/{task_id}/cancel")
    def cancel(task_id: ID):
        return public_task(store.cancel(task_id))

    @app.post("/api/tasks/{task_id}/retry", status_code=202)
    def retry(task_id: ID):
        source = store.get(task_id)
        if source["state"] in {"queued", "running"}:
            raise ServiceError("task_active", "Wait for the task to finish before retrying.")
        if source["kind"] in {"inspect", "convert"}:
            store.asset(source["payload"]["asset_id"])
        if source["kind"] == "download":
            return public_task(
                store.create(
                    "analyze", "Analyze link again", {"url": source["payload"]["analysis"]["url"]}
                )
            )
        return public_task(store.create(source["kind"], source["title"], source["payload"]))

    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
