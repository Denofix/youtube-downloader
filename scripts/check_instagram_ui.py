"""Browser Instagram delivery using owned fixtures; public-source evidence is separate."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from local_instance import running_instance
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium")
    parser.add_argument("--screenshots", type=Path, default=Path(".ui-artifacts"))
    args = parser.parse_args()
    args.screenshots.mkdir(exist_ok=True, parents=True)
    with (
        tempfile.TemporaryDirectory() as temporary,
        running_instance(Path(__file__).with_name("instagram_fixture_worker.py")) as base,
        sync_playwright() as p,
    ):
        executable = args.chromium or shutil.which("google-chrome")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base, wait_until="networkidle")
        page.get_by_label("Media URL").fill("https://instagram.com/reel/OwnedIG01?igsh=tracking")
        page.get_by_role("button", name="Analyze link", exact=True).click()
        expect(page.get_by_label("Source format")).to_be_visible(timeout=30000)
        expect(page.get_by_label("Source format")).to_contain_text("160 × 90")
        expect(page.get_by_label("Source format")).to_contain_text("with audio")
        expect(page.get_by_label("Output preset")).to_have_value("original")
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "source-instagram-desktop.png"), full_page=True)
        page.get_by_role("button", name="Add download to queue", exact=True).click()
        link = page.get_by_role("link", name="Download result", exact=True)
        expect(link).to_be_visible(timeout=30000)
        with page.expect_download() as download:
            link.click()
        video_path = Path(temporary) / "owned.mp4"
        download.value.save_as(video_path)
        streams = json.loads(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video_path)]
            )
        )["streams"]
        assert any(
            s["codec_type"] == "video" and s["width"] == 160 and s["height"] == 90 for s in streams
        )
        assert any(s["codec_type"] == "audio" for s in streams)
        pixel = page.evaluate(
            """async src => {
                const video = document.createElement('video');
                video.muted = true;
                document.body.append(video);
                try {
                    await new Promise((resolve, reject) => {
                        const timer = setTimeout(() => reject(new Error('Video did not decode')), 15000);
                        video.onloadeddata = () => {clearTimeout(timer); resolve();};
                        video.onerror = () => {clearTimeout(timer); reject(new Error('Video playback failed'));};
                        video.src = src;
                    });
                    await video.play();
                    await new Promise(resolve => setTimeout(resolve, 250));
                    const canvas = document.createElement('canvas');
                    canvas.width = canvas.height = 1;
                    const context = canvas.getContext('2d');
                    context.drawImage(video, 0, 0, 1, 1);
                    return [...context.getImageData(0, 0, 1, 1).data];
                } finally {video.remove();}
            }""",
            link.get_attribute("href"),
        )
        assert pixel[0] > 100 and pixel[1] > 20
        page.reload(wait_until="networkidle")
        expect(page.get_by_role("link", name="Download result", exact=True)).to_be_visible()
        page.get_by_role("button", name="View formats", exact=True).click()
        page.get_by_label("Output preset").select_option("mp3")
        page.set_viewport_size({"width": 390, "height": 844})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "source-instagram-mobile.png"), full_page=True)
        page.get_by_role("button", name="Add download to queue", exact=True).click()
        expect(page.get_by_role("link", name="Download result", exact=True)).to_have_count(
            2, timeout=30000
        )
        with page.expect_download() as download:
            page.get_by_role("link", name="Download result", exact=True).first.click()
        audio_path = Path(temporary) / "owned.mp3"
        download.value.save_as(audio_path)
        streams = json.loads(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(audio_path)]
            )
        )["streams"]
        assert len(streams) == 1 and streams[0]["codec_name"] == "mp3"
        page.reload(wait_until="networkidle")
        expect(page.get_by_role("link", name="Download result", exact=True)).to_have_count(2)
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(args.screenshots / "instagram-results-mobile.png"), full_page=True)
        page.get_by_role("navigation").get_by_role("button", name="download", exact=True).click()
        page.get_by_label("Media URL").fill("https://instagram.com/p/NeedsAccess/")
        page.get_by_role("button", name="Analyze link", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text(
            "Error code: access_required", timeout=30000
        )
        expect(page.get_by_role("alert")).not_to_contain_text("owner-session.txt")
        assert not errors, errors
        browser.close()
    print(
        json.dumps(
            {
                "state": "completed",
                "source": "owned local fixture; not live Instagram evidence",
                "checks": [
                    "real MP4 and MP3 delivery",
                    "browser playback with visible pixels",
                    "reload history",
                    "long title and desktop/mobile overflow",
                    "private access error",
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
