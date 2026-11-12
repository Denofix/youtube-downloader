"""Real browser selection and delivery using labelled owned Instagram publication fixtures."""

import argparse
import io
import json
import shutil
import subprocess
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
        tempfile.TemporaryDirectory() as temporary,
        running_instance(Path(__file__).with_name("instagram_gallery_fixture_worker.py")) as base,
        sync_playwright() as p,
    ):
        executable = args.chromium or shutil.which("google-chrome")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base, wait_until="networkidle")
        page.get_by_label("Media URL").fill("https://instagram.com/p/OwnedPhoto01/?igsh=tracking")
        page.get_by_role("button", name="Analyze link", exact=True).click()
        expect(page.get_by_role("heading", name="Choose your photos")).to_be_visible(timeout=30000)
        expect(page.get_by_role("checkbox")).to_have_count(1)
        page.get_by_role("button", name="Add selected photos to queue (1)", exact=True).click()
        first_photo = page.get_by_role("link", name="Download photo 1", exact=True)
        expect(first_photo).to_be_visible(timeout=30000)
        with page.expect_download() as download:
            first_photo.click()
        photo_path = Path(temporary) / "single.jpg"
        download.value.save_as(photo_path)
        with Image.open(photo_path) as image:
            image.load()
            assert image.size == (80, 60) and image.format == "JPEG"
        nav = page.get_by_role("navigation")
        nav.get_by_role("button", name="download", exact=True).click()
        page.get_by_label("Media URL").fill("https://www.instagram.com/p/OwnedPost01/")
        page.get_by_role("button", name="Analyze link", exact=True).click()
        expect(page.get_by_role("heading", name="Choose your items")).to_be_visible(timeout=30000)
        expect(page.get_by_role("checkbox")).to_have_count(3)
        expect(page.get_by_label("Source format for item 2", exact=True)).to_contain_text(
            "160 × 90"
        )
        page.get_by_label("Output preset for item 2", exact=True).select_option("mp3")
        expect(page.get_by_label("Select item 2", exact=True)).to_be_checked()
        page.get_by_label("Output preset for item 2", exact=True).select_option("original")
        page.get_by_label("Select item 3", exact=True).uncheck()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(
            path=str(args.screenshots / "instagram-gallery-desktop.png"), full_page=True
        )
        page.set_viewport_size({"width": 390, "height": 844})
        for image in page.locator(".photo-grid img").all():
            image.scroll_into_view_if_needed()
            expect(image).to_have_js_property("complete", True)
            assert image.evaluate("el => el.naturalWidth") > 0
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "instagram-gallery-mobile.png"), full_page=True)
        page.get_by_role("button", name="Add selected items to queue (2)", exact=True).click()
        archive_link = page.get_by_role("link", name="Download ZIP (2)", exact=True)
        expect(archive_link).to_be_visible(timeout=30000)
        expect(page.get_by_role("link", name="Download item 1", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Download item 2", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Download item 3", exact=True)).to_have_count(0)
        with page.expect_download() as download:
            archive_link.click()
        archive_path = Path(temporary) / "mixed.zip"
        download.value.save_as(archive_path)
        tasks = page.request.get(base + "/api/tasks").json()
        files = next(t for t in tasks if (t.get("result") or {}).get("kind") == "gallery")[
            "result"
        ]["files"]
        assert [f["position"] for f in files] == [1, 2]
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.testzip() is None and archive.namelist() == [f["name"] for f in files]
            for item in files:
                content = page.request.get(base + "/api/assets/" + item["asset_id"] + "/file")
                assert content.status == 200 and archive.read(item["name"]) == content.body()
                if item["kind"] == "image":
                    with Image.open(io.BytesIO(content.body())) as image:
                        image.load()
                        assert image.size == (80, 60)
                else:
                    video_path = Path(temporary) / "carousel.mp4"
                    video_path.write_bytes(content.body())
                    streams = json.loads(
                        subprocess.check_output(
                            [
                                "ffprobe",
                                "-v",
                                "error",
                                "-show_streams",
                                "-of",
                                "json",
                                str(video_path),
                            ]
                        )
                    )["streams"]
                    assert any(s.get("width") == 160 and s.get("height") == 90 for s in streams)
                    assert any(s.get("codec_type") == "audio" for s in streams)
        page.reload(wait_until="networkidle")
        expect(page.get_by_role("link", name="Download ZIP (2)", exact=True)).to_be_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(
            path=str(args.screenshots / "instagram-gallery-results-mobile.png"), full_page=True
        )
        page.get_by_role("button", name="Convert item 1", exact=True).click()
        page.get_by_label("What would you like to do?").select_option("png")
        page.get_by_role("button", name="Add conversion to queue", exact=True).click()
        converted = page.get_by_role("link", name="Download result", exact=True)
        expect(converted).to_be_visible(timeout=30000)
        with page.expect_download() as download:
            converted.click()
        png = Path(temporary) / "converted.png"
        download.value.save_as(png)
        with Image.open(png) as image:
            image.load()
            assert image.format == "PNG" and image.size == (80, 60)
        page.get_by_role("button", name="Choose items", exact=True).click()
        page.get_by_role("button", name="Clear selection", exact=True).click()
        expect(
            page.get_by_role("button", name="Add selected items to queue (0)", exact=True)
        ).to_be_disabled()
        page.get_by_label("Select item 2", exact=True).check()
        page.get_by_label("Output preset for item 2", exact=True).select_option("mp3")
        page.get_by_label("MP3 bitrate for item 2", exact=True).select_option("128")
        page.get_by_role("button", name="Add selected items to queue (1)", exact=True).click()
        expect(page.get_by_role("link", name="Download item 2", exact=True)).to_have_count(
            2, timeout=30000
        )
        with page.expect_download() as download:
            page.get_by_role("link", name="Download item 2", exact=True).first.click()
        mp3 = Path(temporary) / "carousel.mp3"
        download.value.save_as(mp3)
        streams = json.loads(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(mp3)]
            )
        )["streams"]
        assert len(streams) == 1 and streams[0]["codec_name"] == "mp3"
        assert int(streams[0]["bit_rate"]) == 128000
        assert not errors, errors
        browser.close()
    print(
        json.dumps(
            {
                "state": "completed",
                "source": "owned local fixtures; public-source checks are separate",
                "checks": [
                    "single original photo",
                    "mixed item selection and quality",
                    "exact image/video ZIP and individual files",
                    "reload persistence",
                    "retained image conversion",
                    "selected video MP3 at 128 kbps",
                    "desktop/mobile long-title overflow",
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
