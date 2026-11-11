"""Real browser photo selection/ZIP/conversion using owned local media fixtures."""

import argparse
import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from local_instance import running_instance
from PIL import Image
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium")
    parser.add_argument("--screenshots", type=Path, default=Path(".ui-artifacts"))
    args = parser.parse_args()
    args.screenshots.mkdir(exist_ok=True, parents=True)
    with (
        tempfile.TemporaryDirectory() as temp,
        running_instance(Path(__file__).with_name("photo_fixture_worker.py")) as base,
        sync_playwright() as p,
    ):
        executable = args.chromium or shutil.which("google-chrome")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base, wait_until="networkidle")
        page.get_by_label("Media URL").fill(
            "https://www.tiktok.com/@ui.fixture/photo/7100000000000000001"
        )
        page.get_by_role("button", name="Analyze link", exact=True).click()
        expect(page.get_by_role("heading", name="Choose your photos")).to_be_visible(timeout=30000)
        expect(page.get_by_role("checkbox")).to_have_count(3)
        for position in (1, 2, 3):
            expect(page.get_by_label(f"Select photo {position}", exact=True)).to_be_checked()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        clear = page.get_by_role("button", name="Clear selection", exact=True)
        clear.focus()
        page.keyboard.press("Enter")
        page.keyboard.press("Tab")
        first = page.get_by_label("Select photo 1", exact=True)
        expect(first).to_be_focused()
        assert first.evaluate("el => el.matches(':focus-visible')")
        assert first.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
        page.keyboard.press("Space")
        expect(first).to_be_checked()
        page.keyboard.press("Tab")
        second = page.get_by_label("Select photo 2", exact=True)
        expect(second).to_be_focused()
        page.keyboard.press("Space")
        expect(second).to_be_checked()
        page.keyboard.press("Shift+Tab")
        expect(first).to_be_focused()
        page.keyboard.press("Space")
        expect(first).not_to_be_checked()
        page.keyboard.press("Shift+Tab")
        expect(clear).to_be_focused()
        page.keyboard.press("Shift+Tab")
        expect(page.get_by_role("button", name="Select all", exact=True)).to_be_focused()
        page.keyboard.press("Enter")
        for position in (1, 2, 3):
            expect(page.get_by_label(f"Select photo {position}", exact=True)).to_be_checked()
        page.screenshot(path=str(args.screenshots / "photos-select-desktop.png"), full_page=True)
        page.get_by_role("button", name="Clear selection", exact=True).click()
        expect(
            page.get_by_role("button", name="Add selected photos to queue (0)", exact=True)
        ).to_be_disabled()
        page.get_by_label("Select photo 3", exact=True).check()
        page.get_by_label("Select photo 1", exact=True).check()
        page.set_viewport_size({"width": 390, "height": 844})
        for image in page.locator(".photo-grid img").all():
            image.scroll_into_view_if_needed()
            expect(image).to_have_js_property("complete", True)
            assert image.evaluate("(image) => image.naturalWidth") > 0
        page.evaluate("scrollTo(0,0)")
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "photos-select-mobile.png"), full_page=True)
        page.get_by_role("button", name="Add selected photos to queue (2)", exact=True).click()
        archive_link = page.get_by_role("link", name="Download ZIP (2)", exact=True)
        expect(archive_link).to_be_visible(timeout=30000)
        expect(page.get_by_role("link", name="Download photo 1", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Download photo 3", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Download photo 2", exact=True)).to_have_count(0)
        with page.expect_download() as download:
            archive_link.click()
        target = Path(temp) / "selected.zip"
        download.value.save_as(target)
        tasks = page.request.get(base + "/api/tasks").json()
        delivered = next(t for t in tasks if t["kind"] == "download")["result"]["files"]
        assert [f["position"] for f in delivered] == [1, 3]
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None and archive.namelist() == [
                f["name"] for f in delivered
            ]
            for item in delivered:
                response = page.request.get(base + "/api/assets/" + item["asset_id"] + "/file")
                assert response.status == 200 and response.body() == archive.read(item["name"])
                with Image.open(io.BytesIO(response.body())) as image:
                    image.load()
                    assert image.size == (item["width"], item["height"])
        page.reload(wait_until="networkidle")
        expect(page.get_by_role("link", name="Download ZIP (2)", exact=True)).to_be_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "photos-results-mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1050})
        page.screenshot(path=str(args.screenshots / "photos-results-desktop.png"), full_page=True)
        page.get_by_role("button", name="Convert photo 1", exact=True).click()
        expect(page.get_by_label("What would you like to do?")).to_be_visible()
        page.get_by_label("What would you like to do?").select_option("png")
        page.get_by_role("button", name="Add conversion to queue", exact=True).click()
        link = page.get_by_role("link", name="Download result", exact=True)
        expect(link).to_be_visible(timeout=30000)
        with page.expect_download() as download:
            link.click()
        image_path = Path(temp) / "converted.png"
        download.value.save_as(image_path)
        with Image.open(image_path) as image:
            image.load()
            assert image.format == "PNG" and image.size == (320, 640)
        page.get_by_role("button", name="Choose photos", exact=True).click()
        expect(page.get_by_role("checkbox")).to_have_count(3)
        page.get_by_role("button", name="Select all", exact=True).click()
        expect(
            page.get_by_role("button", name="Add selected photos to queue (3)", exact=True)
        ).to_be_enabled()
        assert not errors, errors
        browser.close()
        print(
            json.dumps(
                {
                    "state": "completed",
                    "checks": [
                        "real original images and local previews",
                        "clear/select subset",
                        "keyboard selection, reverse tab order and visible focus",
                        "long unbroken publication title",
                        "ZIP and individual downloads with identical bytes",
                        "source order",
                        "reload persistence",
                        "retained photo to PNG",
                        "desktop/mobile overflow",
                        "selection history",
                    ],
                    "source": "owned local fixture; not live TikTok evidence",
                }
            )
        )


if __name__ == "__main__":
    main()
