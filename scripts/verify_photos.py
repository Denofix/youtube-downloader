"""Opt-in TikTok/Instagram/Pinterest image or GIF originals, ZIP and conversion."""

import argparse
import hashlib
import io
import json
import subprocess
import tempfile
import time
import zipfile
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import httpx
from local_instance import running_instance
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "url", help="One public TikTok/Instagram photo post or Pinterest image/GIF pin"
    )
    parser.add_argument("--base", default="http://localhost:8080")
    parser.add_argument("--ephemeral", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source": args.url,
        "checks": [],
    }
    with (
        running_instance() if args.ephemeral else nullcontext(args.base) as base,
        httpx.Client(base_url=base, trust_env=False, timeout=30) as client,
    ):

        def post(path, body):
            response = client.post("/api" + path, json=body)
            response.raise_for_status()
            return response.json()

        def wait(task):
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                response = client.get("/api/tasks/" + task["id"])
                response.raise_for_status()
                task = response.json()
                if task["state"] not in {"queued", "running"}:
                    return task
                time.sleep(0.2)
            raise TimeoutError("Photo check timed out")

        analysis = wait(post("/analyze", {"url": args.url}))
        report["checks"].append(
            {"scenario": "photo analysis", "state": analysis["state"], "error": analysis["error"]}
        )
        if analysis["state"] == "completed":
            result = analysis["result"]
            assert result["kind"] == "photos"
            assert "_images" not in result and "urlList" not in json.dumps(result)
            report.update(
                {
                    "canonical_source": result["url"],
                    "item_count": result["item_count"],
                    "analysis_timings": result.get("timings"),
                }
            )
            items = result["items"]
            for item in items:
                response = client.get("/api/assets/" + item["preview_asset_id"] + "/preview")
                response.raise_for_status()
                with Image.open(io.BytesIO(response.content)) as image:
                    image.load()
                    assert max(image.size) <= 320
            report["checks"].append(
                {"scenario": "all local previews", "state": "completed", "count": len(items)}
            )
            selection = [items[0]] if len(items) == 1 else [items[0], items[-1]]
            task = wait(
                post(
                    "/photo-downloads",
                    {
                        "analysis_id": analysis["id"],
                        "item_ids": [i["id"] for i in reversed(selection)],
                    },
                )
            )
            report["checks"].append(
                {
                    "scenario": "selected original photos",
                    "state": task["state"],
                    "error": task["error"],
                }
            )
            if task["state"] == "completed":
                files = task["result"]["files"]
                assert [f["item_id"] for f in files] == [i["id"] for i in selection]
                report["download_timings"] = task["result"].get("timings")
                payloads = {}
                facts = []
                for item, original in zip(files, selection):
                    response = client.get("/api/assets/" + item["asset_id"] + "/file")
                    response.raise_for_status()
                    digest = hashlib.sha256(response.content).hexdigest()
                    assert digest == original["sha256"]
                    with Image.open(io.BytesIO(response.content)) as image:
                        image.load()
                        assert image.size == (item["width"], item["height"])
                        facts.append(
                            {
                                "position": item["position"],
                                "format": image.format,
                                "width": image.width,
                                "height": image.height,
                                "bytes": len(response.content),
                                "sha256": digest,
                                "frames": getattr(image, "n_frames", 1),
                                "http_status": response.status_code,
                            }
                        )
                    payloads[item["name"]] = response.content
                report["files"] = facts
                if len(files) > 1:
                    response = client.get(
                        "/api/assets/" + task["result"]["archive_asset_id"] + "/file"
                    )
                    response.raise_for_status()
                    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                        assert archive.testzip() is None and archive.namelist() == list(payloads)
                        assert all(
                            archive.read(name) == content for name, content in payloads.items()
                        )
                    report["checks"].append(
                        {
                            "scenario": "ZIP preserves selected bytes and source order",
                            "state": "completed",
                            "bytes": len(response.content),
                        }
                    )
                output = "mp4" if selection[0].get("kind") == "animation" else "png"
                converted = wait(
                    post(
                        "/conversions",
                        {"asset_id": files[0]["asset_id"], "parameters": {"output": output}},
                    )
                )
                report["checks"].append(
                    {
                        "scenario": "retained GIF to MP4"
                        if output == "mp4"
                        else "retained photo to PNG",
                        "state": converted["state"],
                        "error": converted["error"],
                    }
                )
                if converted["state"] == "completed":
                    response = client.get(
                        "/api/assets/" + converted["result"]["asset_id"] + "/file"
                    )
                    response.raise_for_status()
                    if output == "png":
                        with Image.open(io.BytesIO(response.content)) as image:
                            image.load()
                            assert image.format == "PNG"
                    else:
                        with tempfile.NamedTemporaryFile(suffix=".mp4") as movie:
                            movie.write(response.content)
                            movie.flush()
                            info = json.loads(
                                subprocess.check_output(
                                    [
                                        "ffprobe",
                                        "-v",
                                        "error",
                                        "-show_streams",
                                        "-show_format",
                                        "-of",
                                        "json",
                                        movie.name,
                                    ]
                                )
                            )
                        assert "mp4" in info["format"]["format_name"]
                        assert any(s.get("codec_type") == "video" for s in info["streams"])
                        report["converted_file"] = {
                            "format": info["format"]["format_name"],
                            "bytes": len(response.content),
                            "http_status": response.status_code,
                        }
        report["versions"] = client.get("/api/settings").json()["versions"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if any(c["state"] != "completed" for c in report["checks"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
