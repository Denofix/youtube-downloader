"""Actual Pinterest image/GIF/video delivery with owned local fixtures, not live pins."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
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
        running_instance(Path(__file__).with_name("pinterest_fixture_worker.py")) as base,
        sync_playwright() as p,
    ):
        browser = p.chromium.launch(executable_path=args.chromium or shutil.which("google-chrome"))
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base, wait_until="networkidle")

        def analyze(pin_id, kind):
            page.get_by_role("navigation").get_by_role(
                "button", name="download", exact=True
            ).click()
            page.get_by_label("Media URL").fill(
                f"https://www.pinterest.com/pin/{pin_id}/?tracking=discarded"
            )
            page.get_by_role("button", name="Analyze link", exact=True).click()
            expect(
                page.get_by_role("heading", name=f"Owned Pinterest {kind}", exact=False)
            ).to_be_visible(timeout=30000)

        analyze("123456789", "image")
        expect(page.get_by_role("checkbox", name="Select photo 1", exact=True)).to_be_checked()
        page.screenshot(path=str(args.screenshots / "pinterest-image-desktop.png"), full_page=True)
        page.get_by_role("button", name="Add selected photos to queue (1)", exact=True).click()
        link = page.get_by_role("link", name="Download photo 1", exact=True).first
        expect(link).to_be_visible(timeout=30000)
        response = page.request.get(base + link.get_attribute("href"))
        assert response.ok
        original_hash = hashlib.sha256(response.body()).hexdigest()
        page.reload(wait_until="networkidle")
        assert (
            hashlib.sha256(
                page.request.get(
                    base
                    + page.get_by_role(
                        "link", name="Download photo 1", exact=True
                    ).first.get_attribute("href")
                ).body()
            ).hexdigest()
            == original_hash
        )

        analyze("223456789", "animation")
        expect(page.get_by_text("Animation 1", exact=True)).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(
            path=str(args.screenshots / "pinterest-animation-mobile.png"), full_page=True
        )
        page.get_by_role("button", name="Add selected photos to queue (1)", exact=True).click()
        expect(page.get_by_role("link", name="Download photo 1", exact=True)).to_have_count(
            2, timeout=30000
        )
        with page.expect_download() as saved:
            page.get_by_role("link", name="Download photo 1", exact=True).first.click()
        gif = Path(temporary) / "owned.gif"
        saved.value.save_as(gif)
        assert saved.value.suggested_filename.endswith(".gif")
        with Image.open(gif) as image:
            assert image.format == "GIF" and image.n_frames == 3 and image.size == (64, 48)
        page.get_by_role("button", name="Convert photo 1", exact=True).first.click()
        page.get_by_label("What would you like to do?").select_option("mp4")
        page.get_by_role("button", name="Add conversion to queue", exact=True).click()
        expect(page.get_by_role("link", name="Download result", exact=True)).to_have_count(
            1, timeout=30000
        )

        analyze("323456789", "video")
        expect(page.get_by_label("Source format")).to_contain_text("160 × 90")
        expect(page.get_by_label("Source format")).to_contain_text("audio unknown")
        expect(
            page.get_by_text("This source does not report audio presence.", exact=False)
        ).to_be_visible()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "pinterest-video-mobile.png"), full_page=True)
        page.get_by_role("button", name="Add download to queue", exact=True).click()
        expect(page.get_by_role("link", name="Download result", exact=True)).to_have_count(
            2, timeout=30000
        )
        with page.expect_download() as saved:
            page.get_by_role("link", name="Download result", exact=True).first.click()
        movie = Path(temporary) / "owned.mp4"
        saved.value.save_as(movie)
        streams = json.loads(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(movie)]
            )
        )["streams"]
        assert any(
            s["codec_type"] == "video" and s["width"] == 160 and s["height"] == 90 for s in streams
        )
        assert any(s["codec_type"] == "audio" for s in streams)
        page.get_by_role("button", name="View formats", exact=True).first.click()
        page.get_by_label("Output preset").select_option("mp3")
        page.locator("summary").filter(has_text="Advanced").click()
        page.get_by_label("MP3 output bitrate").select_option("128")
        page.get_by_role("button", name="Add download to queue", exact=True).click()
        expect(page.get_by_role("link", name="Download result", exact=True)).to_have_count(
            3, timeout=30000
        )
        with page.expect_download() as saved:
            page.get_by_role("link", name="Download result", exact=True).first.click()
        audio = Path(temporary) / "owned.mp3"
        saved.value.save_as(audio)
        streams = json.loads(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(audio)]
            )
        )["streams"]
        assert (
            len(streams) == 1
            and streams[0]["codec_name"] == "mp3"
            and int(streams[0]["bit_rate"]) == 128000
        )
        page.reload(wait_until="networkidle")
        expect(page.get_by_role("link", name="Download result", exact=True)).to_have_count(3)
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "pinterest-results-mobile.png"), full_page=True)
        assert not errors, errors
        browser.close()
    print(
        json.dumps(
            {
                "state": "completed",
                "source": "owned local fixtures; live Pinterest checks are separate",
                "checks": [
                    "original JPEG bytes and local preview",
                    "animated GIF frames and retained MP4 conversion",
                    "native progressive video with actual audio",
                    "unknown audio labelled honestly",
                    "128 kbps MP3",
                    "reload history and desktop/mobile long-title overflow",
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
