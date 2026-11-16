"""Stage-6a upload -> worker -> verified file -> browser, with owned fixtures."""

import argparse
import shutil
import tempfile
from pathlib import Path

from conversion_fixtures import build_fixtures
from local_instance import running_instance
from PIL import Image
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium")
    parser.add_argument("--screenshots", type=Path, default=Path(".ui-artifacts"))
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory() as temporary,
        running_instance() as base,
        sync_playwright() as p,
    ):
        root = Path(temporary)
        fixtures = build_fixtures(root / "inputs")
        browser = p.chromium.launch(executable_path=args.chromium or shutil.which("google-chrome"))
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base + "/#convert", wait_until="networkidle")
        page.get_by_label("Choose media file", exact=True).set_input_files(fixtures / "rotated.mov")
        choice = page.get_by_role("combobox", name="What would you like to do?", exact=True)
        expect(choice).to_be_visible(timeout=20000)
        expect(page.locator(".source-facts")).to_contain_text("90 × 160")
        choice.select_option("gif")
        page.get_by_label("Duration (seconds)", exact=True).fill("0.3")
        # Changing the language retains this file/operation and the selected clip duration.
        page.get_by_label("Language", exact=True).select_option("uk")
        expect(
            page.get_by_role("combobox", name="Що ви хочете зробити?", exact=True)
        ).to_have_value("gif")
        expect(page.get_by_label("Тривалість (секунди)", exact=True)).to_have_value("0.3")
        for width in (320, 390, 768, 1440):
            page.set_viewport_size({"width": width, "height": 1050})
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            if width in (390, 1440):
                page.screenshot(
                    path=str(args.screenshots / f"converter-rotated-uk-{width}.png"), full_page=True
                )
        page.get_by_label("Мова", exact=True).select_option("en")
        page.get_by_role("button", name="Add conversion to queue", exact=True).click()
        result = page.get_by_role("link", name="Download result", exact=True)
        expect(result).to_be_visible(timeout=30000)
        with page.expect_download() as download:
            result.click()
        target = root / "portrait.gif"
        download.value.save_as(target)
        with Image.open(target) as image:
            assert image.size == (90, 160) and image.n_frames > 1
            for frame in range(image.n_frames):
                image.seek(frame)
                image.load()
        page.reload(wait_until="networkidle")
        expect(result).to_be_visible()
        # After reload, recover the retained asset through history rather than
        # assuming that the unsaved upload form still exists in browser memory.
        page.get_by_role("button", name="Choose conversion", exact=True).click()
        page.get_by_role("button", name="Change file", exact=True).click()
        page.get_by_label("Choose media file", exact=True).set_input_files(fixtures / "silent.mp4")
        expect(choice).to_be_visible(timeout=20000)
        assert "mp3" not in choice.locator("option").evaluate_all(
            "options => options.map(o => o.value)"
        )
        page.get_by_role("button", name="Change file", exact=True).click()
        page.get_by_label("Choose media file", exact=True).set_input_files(
            fixtures / "oriented.jpg"
        )
        expect(choice).to_be_visible(timeout=20000)
        expect(page.locator(".source-facts")).to_contain_text("48 × 64")
        page.screenshot(
            path=str(args.screenshots / "converter-oriented-photo-en.png"), full_page=True
        )
        page.get_by_role("button", name="Change file", exact=True).click()
        page.get_by_label("Language", exact=True).select_option("uk")
        page.get_by_label("Обрати медіафайл", exact=True).set_input_files(
            fixtures / "animated.webp"
        )
        expect(page.get_by_role("alert")).to_contain_text("Для анімації використовуйте")
        assert not errors, errors
        browser.close()
        print(
            "Converter browser flow passed: displayed orientation, GIF pixels/download/history, silent source, Ukrainian errors and 320-1440px layouts."
        )


if __name__ == "__main__":
    main()
