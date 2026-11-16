"""Safe source diagnostics runnable inside the production worker container."""

import argparse
import importlib.metadata
import json
from functools import lru_cache

import yt_dlp

from . import sources
from .config import settings
from .errors import ServiceError


@lru_cache(maxsize=1)
def runtime_status():
    versions = {}
    for name in ("yt-dlp", "curl-cffi"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "missing"
    # No extractors, network calls, owner cookies or paths are needed for this check.
    with yt_dlp.YoutubeDL(
        {"quiet": True, "no_warnings": True, "cachedir": False}, auto_init=False
    ) as ydl:
        targets = sorted(
            {str(target) for target, _handler in ydl._get_available_impersonate_targets()}
        )
    return {"versions": versions, "browser_impersonation": bool(targets), "targets": targets}


def diagnose(url=None, config=settings):
    result = {"runtime": runtime_status(), "cookies_configured": bool(config.cookie_file)}
    if url is None:
        return result | {
            "state": "completed" if result["runtime"]["browser_impersonation"] else "failed"
        }
    try:
        canonical = sources.resolve_url(url)
        result["source"] = {"platform": sources.platform_for(canonical), "url": canonical}
        analysis = sources.analyze(canonical, config)
        result.update(
            {
                "state": "completed",
                "format_count": len(analysis["choices"]),
                "kind": analysis["kind"],
            }
        )
    except ServiceError as error:
        result.update({"state": "failed", "error": {"code": error.code, "message": error.message}})
    except Exception:
        result.update(
            {
                "state": "failed",
                "error": {
                    "code": "diagnostic_failed",
                    "message": "The source check failed unexpectedly. Check the runtime and configured source access.",
                },
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="One public supported track or video URL")
    parser.add_argument(
        "--runtime-only",
        action="store_true",
        help="Check the installed browser transport without network requests",
    )
    args = parser.parse_args()
    if args.runtime_only and args.url:
        parser.error("Use either a source URL or --runtime-only.")
    if not args.url and not args.runtime_only:
        parser.error("Pass a source URL or --runtime-only.")
    result = diagnose(args.url)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["state"] == "completed" else 1)


if __name__ == "__main__":
    main()
