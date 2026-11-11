import resource
import sys

from . import media, sources
from .errors import ServiceError
from .store import Store


def execute(task, store):
    task_id, payload, config = task["id"], task["payload"], store.config
    directory = config.data_dir / "files" / task_id
    directory.mkdir(exist_ok=True)

    def report(operation, progress=None, speed=None, eta=None):
        store.progress(task_id, operation, progress, speed, eta)

    try:
        if task["kind"] == "analyze":
            report("analyzing")
            result = sources.analyze(payload["url"], config)
        elif task["kind"] == "inspect":
            report("inspecting")
            asset = store.asset(payload["asset_id"], allow_expired=True)
            store.update_asset(asset["id"], media.probe(asset["path"]))
            result = {"asset_id": asset["id"]}
        else:
            if task["kind"] == "download":
                analysis = payload["analysis"]
                choice = next(
                    (c for c in analysis["choices"] if c["id"] == payload["choice_id"]), None
                )
                if choice is None:
                    raise ServiceError(
                        "invalid_format", "Analyze again and select a current source format."
                    )
                profile = payload["profile"]
                # Also apply the current policy to tasks/analyses created by older UI versions.
                if analysis.get("platform") == "TikTok" and profile != "mp3":
                    profile = "compatible"
                path = sources.download(
                    analysis,
                    choice,
                    profile,
                    payload["bitrate"],
                    directory,
                    config,
                    report,
                )
                report("verifying")
                metadata = media.verify(path)
                if choice["has_audio"] and not metadata["has_audio"]:
                    raise ServiceError(
                        "invalid_result", "The result is missing its selected audio stream."
                    )
                if profile != "mp3" and any(
                    choice.get(dimension) and metadata.get(dimension) != choice[dimension]
                    for dimension in ("width", "height")
                ):
                    raise ServiceError(
                        "quality_mismatch",
                        "The result does not match the selected resolution. Analyze again.",
                    )
                if profile == "compatible":
                    report("converting")
                    original = path
                    path, metadata = media.compatible_video(original, metadata, directory)
                    original.unlink()
                    report("verifying")
                quality = sources.quality_height(choice)
                descriptor = (
                    f"MP3 {payload['bitrate']}kbps"
                    if profile == "mp3"
                    else (str(quality) + "p" if quality else choice.get("kind", "media"))
                    + (" H264" if profile == "compatible" else "")
                )
                name = media.safe_name(analysis["title"], path.suffix, descriptor)
            elif task["kind"] == "convert":
                asset = store.asset(payload["asset_id"], allow_expired=True)
                report("converting")
                path, metadata = media.convert(
                    asset["path"], media.probe(asset["path"]), payload["parameters"], directory
                )
                name = media.safe_name(asset["name"].rsplit(".", 1)[0], path.suffix, "converted")
            else:
                raise ServiceError("unknown_job", "This task type is not supported.")
            report("preparing")
            if path.stat().st_size > config.max_file_bytes:
                raise ServiceError("file_limit", "The result exceeds the configured file limit.")
            result = {
                "asset_id": store.add_asset(path, name, metadata, task_id),
                "preview": metadata["kind"] in {"image", "animation"},
            }
            if task["kind"] == "download":
                result["source_format_ids"] = choice.get(
                    "resolved_source_format_ids", choice["source_format_ids"]
                )
        if not store.finish(task_id, "completed", result=result):
            store.discard_task_files(task_id)
    except ServiceError as error:
        store.finish(task_id, "failed", error={"code": error.code, "message": error.message})
        store.discard_task_files(task_id)
    except Exception:
        store.finish(
            task_id,
            "failed",
            error={
                "code": "processing_failed",
                "message": "This task could not be processed. Check the source/file and tool diagnostics, then retry.",
            },
        )
        store.discard_task_files(task_id)


def main():
    store = Store()
    resource.setrlimit(
        resource.RLIMIT_FSIZE, (store.config.max_file_bytes, store.config.max_file_bytes)
    )
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    # V8 reserves a large virtual address space; Docker limits actual memory instead of RLIMIT_AS.
    execute(store.get(sys.argv[1]), store)


if __name__ == "__main__":
    main()
