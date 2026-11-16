"""Opt-in Instagram carousel check through the normal API and production worker."""

import argparse
import hashlib
import io
import json
import time
import zipfile
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import httpx
from local_instance import running_instance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--base", default="http://127.0.0.1:8080")
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
        httpx.Client(base_url=base, timeout=30, trust_env=False) as client,
    ):

        def wait(task):
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                r = client.get("/api/tasks/" + task["id"])
                r.raise_for_status()
                task = r.json()
                if task["state"] not in {"queued", "running"}:
                    return task
                time.sleep(0.3)
            raise TimeoutError("Carousel check timed out")

        def post(path, body):
            r = client.post("/api" + path, json=body)
            r.raise_for_status()
            return wait(r.json())

        def record(scenario, task):
            report["checks"].append(
                {
                    "scenario": scenario,
                    "state": task["state"],
                    "error": task["error"],
                    "timings": (task["result"] or {}).get("timings"),
                }
            )

        analysis = post("/analyze", {"url": args.url})
        record("carousel analysis", analysis)
        if analysis["state"] == "completed":
            result = analysis["result"]
            assert result["kind"] == "gallery", "Use verify_photos.py for an all-photo post"
            assert "_entries" not in result
            items = result["items"]
            report.update(
                {
                    "item_count": len(items),
                    "item_kinds": [i["kind"] for i in items],
                    "canonical_source": result["url"],
                }
            )
            selected = [items[0], items[-1]] if len(items) > 1 else items
            if not any(i["kind"] == "video" for i in selected):
                selected.insert(1, next(i for i in items if i["kind"] == "video"))
            selections, first_audio = [], None
            for item in selected:
                s = {"item_id": item["id"]}
                if item["kind"] == "video":
                    options = sorted(
                        (c for c in item["choices"] if c["kind"] == "video"),
                        key=lambda c: (
                            c.get("quality_height") or c.get("height") or 0,
                            c.get("width") or 0,
                        ),
                        reverse=True,
                    )
                    choice = next((c for c in options if c["has_audio"]), options[0])
                    s["choice_id"] = choice["id"]
                    if first_audio is None and choice["has_audio"]:
                        first_audio = s | {"profile": "mp3", "bitrate": 192}
                selections.append(s)
            delivered = post(
                "/post-downloads",
                {"analysis_id": analysis["id"], "selections": list(reversed(selections))},
            )
            record("selected carousel files", delivered)
            if delivered["state"] == "completed":
                files = delivered["result"]["files"]
                assert [f["position"] for f in files] == sorted(i["position"] for i in selected)
                expected = {i["id"]: i for i in selected}
                payloads, facts = {}, []
                for item in files:
                    response = client.get("/api/assets/" + item["asset_id"] + "/file")
                    response.raise_for_status()
                    metadata = client.get("/api/assets/" + item["asset_id"]).json()["metadata"]
                    digest = hashlib.sha256(response.content).hexdigest()
                    if item["kind"] == "image":
                        assert digest == expected[item["item_id"]]["sha256"]
                    facts.append(
                        {
                            "position": item["position"],
                            "metadata": metadata,
                            "bytes": len(response.content),
                            "sha256": digest,
                            "http_status": response.status_code,
                        }
                    )
                    payloads[item["name"]] = response.content
                report["files"] = facts
                if len(files) > 1:
                    response = client.get(
                        "/api/assets/" + delivered["result"]["archive_asset_id"] + "/file"
                    )
                    response.raise_for_status()
                    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                        assert z.testzip() is None and z.namelist() == list(payloads)
                        assert all(z.read(name) == value for name, value in payloads.items())
                    report["checks"].append(
                        {
                            "scenario": "ZIP bytes and source order",
                            "state": "completed",
                            "bytes": len(response.content),
                        }
                    )
            if first_audio:
                audio = post(
                    "/post-downloads", {"analysis_id": analysis["id"], "selections": [first_audio]}
                )
                record("MP3 from selected carousel video", audio)
                if audio["state"] == "completed":
                    item = audio["result"]["files"][0]
                    asset = client.get("/api/assets/" + item["asset_id"]).json()
                    response = client.get("/api/assets/" + item["asset_id"] + "/file")
                    response.raise_for_status()
                    assert asset["metadata"]["audio_codec"] == "mp3"
                    report["mp3"] = {
                        "metadata": asset["metadata"],
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
