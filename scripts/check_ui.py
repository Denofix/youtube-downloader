"""Real browser smoke test using only generated files and a disposable service instance."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from local_instance import running_instance
from PIL import Image
from playwright.sync_api import expect, sync_playwright


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
        page.get_by_label("YouTube video URL").fill("https://invalid.example/video")
        page.get_by_role("button", name="Analyze link").click()
        expect(page.get_by_role("alert")).to_contain_text("individual YouTube")
        page.get_by_role("button", name="Dismiss error").click()
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
        page.get_by_label("YouTube video URL").fill("")
        page.set_viewport_size({"width": 390, "height": 844})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "download-mobile.png"), full_page=True)
        navigation.get_by_role("button", name="tasks", exact=True).click()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "tasks-mobile.png"), full_page=True)
        navigation.get_by_role("button", name="settings", exact=True).click()
        expect(page.get_by_role("heading", name="Runtime diagnostics")).to_be_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert not errors, errors
        browser.close()
    print(
        "UI checks passed: desktop/mobile, focus, validation, upload, MP3 download, GIF preview, WebP conversion and persisted history."
    )


if __name__ == "__main__":
    main()
