"""Real browser smoke test using only generated files and a disposable service instance."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from local_instance import running_instance
from PIL import Image
from playwright.sync_api import expect, sync_playwright


def check_source_forms(page, screenshots):
    """Browser-only metadata fixtures; real source delivery is covered by test_sources.py."""
    tasks = []

    def analyze_fixture(route):
        track = "soundcloud.com" in route.request.post_data_json["url"]
        choice = {
            "id": "option_0",
            "kind": "audio" if track else "video",
            "container": "m4a" if track else "mp4",
            "width": None if track else 720,
            "height": None if track else 1280,
            "fps": None if track else 30,
            "video_codec": None if track else "h264",
            "audio_codec": "aac",
            "audio_bitrate": 160 if track else None,
            "has_audio": True,
            "operation": "download",
            "size": None,
            "size_kind": "unknown",
            "format_note": None if track else "watermarked",
            "source_format_ids": ["http_aac_160k" if track else "play"],
        }
        second = choice | {
            "id": "option_1",
            "source_format_ids": ["hls_aac_160k" if track else "download"],
        }
        task = {
            "id": "e" * 32,
            "kind": "analyze",
            "title": "Source form UI fixture",
            "state": "completed",
            "operation": "ready",
            "progress": None,
            "speed": None,
            "eta": None,
            "created_at": 1794394800,
            "expires_at": 4102444800,
            "expired": False,
            "error": None,
            "result": {
                "platform": "SoundCloud" if track else "TikTok",
                "kind": choice["kind"],
                "title": "Owned track (UI fixture)" if track else "Portrait clip (UI fixture)",
                "author": "Test creator",
                "thumbnail": None,
                "duration": 12,
                "choices": [choice, second],
            },
        }
        tasks[:] = [task]
        route.fulfill(status=202, json=task)

    page.route("**/api/analyze", analyze_fixture)
    page.route("**/api/tasks", lambda route: route.fulfill(json=tasks))
    try:
        for track in (True, False):
            page.get_by_label("Media URL").fill(
                "https://soundcloud.com/test-artist/owned-track"
                if track
                else "https://www.tiktok.com/@test.creator/video/7100000000000000001"
            )
            page.get_by_role("button", name="Analyze link").click()
            expect(
                page.get_by_role(
                    "heading",
                    name="Owned track (UI fixture)" if track else "Portrait clip (UI fixture)",
                )
            ).to_be_visible()
            options = page.get_by_label("Source format").locator("option").all_text_contents()
            assert len(options) == len(set(options)) == 2
            assert ("160 kbps" if track else "watermarked") in options[0]
            page.get_by_label("Output preset").select_option("mp3")
            page.get_by_text("Advanced · source details & encoding").click()
            expect(page.get_by_label("MP3 output bitrate")).to_be_visible()
            expect(page.get_by_role("button", name="Add download to queue")).to_be_enabled()
            page.set_viewport_size(
                {"width": 1440, "height": 1050} if track else {"width": 390, "height": 844}
            )
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            page.screenshot(
                path=str(
                    screenshots
                    / ("source-soundcloud-desktop.png" if track else "source-tiktok-mobile.png")
                ),
                full_page=True,
            )
            page.get_by_text("Advanced · source details & encoding").click()
    finally:
        page.unroute("**/api/analyze")
        page.unroute("**/api/tasks")
        page.set_viewport_size({"width": 1440, "height": 1050})
        page.reload(wait_until="networkidle")


def check_source_failure(page):
    """The download error must retain its specific reason without opening task history."""
    task = {
        "id": "d" * 32,
        "kind": "analyze",
        "title": "Protected source UI fixture",
        "state": "failed",
        "operation": "analyzing",
        "expired": False,
        "result": None,
        "error": {
            "code": "drm_protected",
            "message": "The source offers this item only in DRM-protected formats.",
        },
    }
    page.route("**/api/analyze", lambda route: route.fulfill(status=202, json=task))
    page.route("**/api/tasks", lambda route: route.fulfill(json=[task]))
    try:
        page.get_by_label("Media URL").fill("https://soundcloud.com/test-artist/protected-track")
        page.get_by_role("button", name="Analyze link").click()
        expect(page.get_by_role("alert")).to_contain_text("DRM-protected")
        expect(page.get_by_role("alert")).to_contain_text("Error code: drm_protected")
        page.get_by_role("button", name="Dismiss error").click()
    finally:
        page.unroute("**/api/analyze")
        page.unroute("**/api/tasks")
        page.reload(wait_until="networkidle")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium", help="Optional system Chromium executable")
    parser.add_argument("--screenshots", type=Path, default=Path(".ui-artifacts"))
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory() as temporary,
        running_instance() as base,
        sync_playwright() as p,
    ):
        directory = Path(temporary)
        source = directory / ("Local test clip with a very long name " * 4 + ".mp4")
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=orange:s=160x90:r=12",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440",
                "-t",
                "1.2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(source),
            ],
            check=True,
        )
        image = directory / "Transparent test image.png"
        Image.new("RGBA", (64, 48), (255, 100, 0, 120)).save(image)
        browser = p.chromium.launch(**({"executable_path": args.chromium} if args.chromium else {}))
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
        navigation = page.get_by_role("navigation")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base, wait_until="networkidle")
        heading = page.get_by_role("heading", name="A link. A format. Make it yours.")
        expect(heading).to_be_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.keyboard.press("Tab")
        expect(page.get_by_role("link", name="Skip to content")).to_be_focused()
        heading.click()
        page.screenshot(path=str(args.screenshots / "download-desktop.png"), full_page=True)
        navigation.get_by_role("button", name="tasks", exact=True).click()
        expect(page.get_by_text("A clear queue. A fresh start.")).to_be_visible()
        navigation.get_by_role("button", name="download", exact=True).click()
        page.get_by_label("Media URL").fill("https://invalid.example/video")
        page.get_by_role("button", name="Analyze link").click()
        expect(page.get_by_role("alert")).to_contain_text("SoundCloud track")
        page.get_by_role("button", name="Dismiss error").click()
        check_source_forms(page, args.screenshots)
        check_source_failure(page)
        navigation.get_by_role("button", name="convert", exact=True).click()
        page.get_by_label("Choose media file").set_input_files(source)
        expect(page.get_by_label("What would you like to do?")).to_be_visible(timeout=20000)
        page.get_by_label("What would you like to do?").select_option("mp3")
        page.screenshot(path=str(args.screenshots / "convert-desktop.png"), full_page=True)
        page.get_by_role("button", name="Add conversion to queue").click()
        expect(page.get_by_role("link", name="Download result")).to_be_visible(timeout=30000)
        with page.expect_download() as download:
            page.get_by_role("link", name="Download result").click()
        output = directory / "result.mp3"
        download.value.save_as(output)
        result = json.loads(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)]
            )
        )
        assert result["streams"][0]["codec_name"] == "mp3"
        page.reload(wait_until="networkidle")
        expect(page.get_by_role("link", name="Download result")).to_be_visible()
        page.screenshot(path=str(args.screenshots / "tasks-desktop.png"), full_page=True)
        page.get_by_role("button", name="Choose conversion").click()
        page.get_by_label("What would you like to do?").select_option("gif")
        page.get_by_label("Duration (seconds)").fill("0.5")
        page.get_by_role("button", name="Add conversion to queue").click()
        preview = page.get_by_alt_text("Converted image preview")
        expect(preview).to_be_visible(timeout=30000)
        expect(preview).to_have_js_property("complete", True)
        assert preview.evaluate("img => img.naturalWidth > 0")
        navigation.get_by_role("button", name="convert", exact=True).click()
        page.get_by_role("button", name="Change file").click()
        page.get_by_label("Choose media file").set_input_files(image)
        expect(page.get_by_label("What would you like to do?")).to_be_visible(timeout=20000)
        page.get_by_label("What would you like to do?").select_option("webp")
        page.get_by_role("button", name="Add conversion to queue").click()
        expect(page.get_by_alt_text("Converted image preview")).to_have_count(2, timeout=30000)
        navigation.get_by_role("button", name="download", exact=True).click()
        page.get_by_label("Media URL").fill("")
        page.set_viewport_size({"width": 390, "height": 844})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "download-mobile.png"), full_page=True)
        navigation.get_by_role("button", name="tasks", exact=True).click()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "tasks-mobile.png"), full_page=True)
        navigation.get_by_role("button", name="settings", exact=True).click()
        expect(page.get_by_role("heading", name="Runtime diagnostics")).to_be_visible()
        expect(page.get_by_text("Browser transport support", exact=True)).to_be_visible()
        expect(page.get_by_text("curl-cffi", exact=True)).to_be_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert not errors, errors
        browser.close()
    print(
        "UI checks passed: desktop/mobile source forms (metadata fixtures), focus, validation, real upload/MP3/GIF/WebP conversion and persisted history."
    )


if __name__ == "__main__":
    main()
