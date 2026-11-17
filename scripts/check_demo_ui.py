"""Public preview: real browser, prepared downloads, no processing API calls."""

import argparse
import functools
import http.server
import shutil
import tempfile
import threading
import zipfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium")
    parser.add_argument("--screenshots", type=Path, default=Path(".ui-artifacts"))
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(root / "frontend/dist-demo")
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=args.chromium or shutil.which("google-chrome")
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 1050}, reduced_motion="reduce"
            )
            errors, forbidden = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda request: (
                    forbidden.append(request.url)
                    if "/api/" in request.url or not request.url.startswith(base + "/")
                    else None
                ),
            )
            page.goto(base, wait_until="networkidle")
            expect(page.get_by_text("Interactive UI preview", exact=True)).to_be_visible()
            expect(page.get_by_text("Worker online", exact=True)).to_have_count(0)
            page.get_by_role("button", name="Try video example", exact=True).click()
            expect(page.locator(".media-preview")).to_contain_text(
                "Generated motion and tone", timeout=10000
            )
            page.screenshot(
                path=str(args.screenshots / "demo-download-desktop.png"), full_page=True
            )
            page.get_by_role("button", name="Add download to queue", exact=True).click()
            result = page.get_by_role("link", name="Download result", exact=True)
            expect(result).to_be_visible(timeout=10000)
            assert result.get_attribute("href") == "/demo-assets/sample-video.mp4"
            with page.expect_download() as download:
                result.click()
            target = Path(temporary) / "sample.mp4"
            download.value.save_as(target)
            assert (
                target.read_bytes()
                == (root / "frontend/demo-public/demo-assets/sample-video.mp4").read_bytes()
            )
            page.screenshot(path=str(args.screenshots / "demo-tasks-desktop.png"), full_page=True)
            page.reload(wait_until="networkidle")
            expect(result).to_be_visible()
            page.get_by_role("button", name="Try photo example", exact=True).click()
            expect(page.get_by_text("Two generated sample images", exact=True)).to_be_visible(
                timeout=10000
            )
            page.get_by_role("button", name="Add selected photos to queue (2)", exact=True).click()
            archive = page.get_by_role("link", name="Download ZIP (2)", exact=True)
            expect(archive).to_be_visible(timeout=10000)
            with page.expect_download() as download:
                archive.click()
            target = Path(temporary) / "photos.zip"
            download.value.save_as(target)
            with zipfile.ZipFile(target) as files:
                assert files.namelist() == ["01-sample.png", "02-sample.jpg"]
                assert files.testzip() is None
            page.get_by_role("button", name="convert", exact=True).click()
            expect(page.get_by_label("Choose media file", exact=True)).to_be_disabled()
            page.get_by_role("button", name="Sample image", exact=True).click()
            page.get_by_role(
                "combobox", name="What would you like to do?", exact=True
            ).select_option("webp")
            page.screenshot(
                path=str(args.screenshots / "demo-converter-desktop.png"), full_page=True
            )
            page.get_by_role("button", name="Add conversion to queue", exact=True).click()
            result = page.get_by_role("link", name="Download result", exact=True).first
            expect(result).to_have_attribute(
                "href", "/demo-assets/sample-image-1.webp", timeout=10000
            )
            with page.expect_download() as download:
                result.click()
            target = Path(temporary) / "image.webp"
            download.value.save_as(target)
            with Image.open(target) as image:
                image.load()
                assert image.size == (320, 200) and image.mode == "RGBA"
            page.get_by_role("button", name="Reset demo", exact=True).click()
            page.get_by_label("Media URL", exact=True).fill("https://example.com/private-file")
            page.get_by_role("button", name="Analyze link", exact=True).click()
            expect(page.get_by_role("alert")).to_contain_text("prepared samples")
            page.get_by_label("Language", exact=True).select_option("uk")
            expect(page.get_by_role("alert")).to_contain_text("готові приклади")
            page.get_by_role("button", name="Спробувати відео", exact=True).click()
            page.get_by_role("button", name="Скасувати", exact=True).click()
            page.get_by_role("button", name="Завдання", exact=True).click()
            expect(page.locator(".task-card")).to_contain_text("Скасовано")
            page.get_by_role("button", name="Повторити", exact=True).click()
            expect(page.get_by_text("Generated motion and tone", exact=True)).to_be_visible(
                timeout=10000
            )
            for width in (320, 390, 768, 1440):
                page.set_viewport_size({"width": width, "height": 1050})
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                if width == 390:
                    page.screenshot(
                        path=str(args.screenshots / "demo-download-uk-mobile.png"), full_page=True
                    )
            page.get_by_role("button", name="Налаштування", exact=True).click()
            expect(page.get_by_role("heading", name="Про цей огляд", exact=True)).to_be_visible()
            expect(page.get_by_text("Runtime versions", exact=True)).to_have_count(0)
            assert not forbidden, forbidden
            assert not errors, errors
            browser.close()
            print(
                "Demo browser flow passed: prepared MP4/ZIP/WebP bytes, history, blocked custom input, cancel/retry, EN/UK, 320–1440px layouts, zero processing-API requests."
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
