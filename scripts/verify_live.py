"""Opt-in live source test; creates tasks and validates results on a running instance."""

import argparse
import json
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import httpx
from local_instance import running_instance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="One public YouTube/TikTok video or SoundCloud track permalink")
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--ephemeral", action="store_true", help="Use a disposable local API/worker"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--quality", choices=("lowest", "highest", "all"), default="lowest")
    parser.add_argument(
        "--save-results", type=Path, help="Optional directory for local playback inspection"
    )
    args = parser.parse_args()
    checks = []
    with (
        running_instance() if args.ephemeral else nullcontext(args.base) as base,
        httpx.Client(base_url=base, timeout=20, trust_env=False) as client,
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
                current = response.json()
                if current["state"] not in {"queued", "running"}:
                    return current
                time.sleep(0.4)
            raise TimeoutError("Live task did not complete within ten minutes.")

        task = wait(post("/analyze", {"url": args.url}))
        checks.append(
            {"scenario": "metadata analysis", "state": task["state"], "error": task["error"]}
        )
        if task["state"] == "completed":
            choices = [
                c
                for c in task["result"]["choices"]
                if c["kind"] == task["result"]["kind"] and c["has_audio"]
            ]
            ordered = sorted(
                choices,
                key=lambda c: (
                    c.get("quality_height") or c.get("height") or 0,
                    c.get("width") or 0,
                    c["source_format_ids"],
                ),
            )
            selected = (
                ordered
                if args.quality == "all"
                else ordered[-1:]
                if args.quality == "highest"
                else ordered[:1]
            )
            if not selected:
                checks.append(
                    {
                        "scenario": "select a source with audio",
                        "state": "failed",
                        "error": {
                            "code": "no_audio",
                            "message": "No compatible source with audio was returned.",
                        },
                    }
                )
            video_profile = "compatible" if task["result"]["platform"] == "TikTok" else "original"
            for index, choice in enumerate(selected):
                for profile in (video_profile, "mp3") if index == 0 else (video_profile,):
                    result = wait(
                        post(
                            "/downloads",
                            {
                                "analysis_id": task["id"],
                                "choice_id": choice["id"],
                                "profile": profile,
                                "bitrate": 192,
                            },
                        )
                    )
                    check = {
                        "scenario": "download " + profile,
                        "state": result["state"],
                        "source_format_ids": choice["source_format_ids"],
                        "selected_height": choice["height"],
                        "selected_width": choice["width"],
                        "selected_kind": choice["kind"],
                        "error": result["error"],
                    }
                    if result["state"] == "completed":
                        check["resolved_source_format_ids"] = result["result"].get(
                            "source_format_ids"
                        )
                        asset_id = result["result"]["asset_id"]
                        check["metadata"] = client.get("/api/assets/" + asset_id).json()["metadata"]
                        response = client.get("/api/assets/" + asset_id + "/file")
                        check["download_http_status"] = response.status_code
                        check["download_bytes"] = len(response.content)
                        if args.save_results and response.status_code == 200:
                            args.save_results.mkdir(parents=True, exist_ok=True)
                            suffix = (
                                ".mp3"
                                if profile == "mp3"
                                else ".mp4"
                                if check["metadata"]["kind"] == "video"
                                else ".m4a"
                            )
                            (
                                args.save_results / (str(len(checks)) + "-" + profile + suffix)
                            ).write_bytes(response.content)
                    checks.append(check)
        report = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": args.url,
            "quality_selection": args.quality,
            "platform": task["result"].get("platform") if task["result"] else None,
            "publication_type": task["result"].get("kind") if task["result"] else None,
            "versions": client.get("/api/settings").json()["versions"],
            "checks": checks,
        }
    text = json.dumps(report, indent=2) + "\n"
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    if not all(c["state"] == "completed" for c in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
