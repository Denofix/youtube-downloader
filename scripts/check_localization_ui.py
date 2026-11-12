"""English/Ukrainian browser checks with owned files and a disposable queue."""

import argparse
import shutil
from pathlib import Path

from local_instance import running_instance
from playwright.sync_api import expect, sync_playwright


def assert_fits(page):
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    picker = page.locator(".language-picker").bounding_box()
    brand = page.locator(".brand").bounding_box()
    assert picker and brand
    assert picker["x"] > brand["x"] + brand["width"]
    assert abs(picker["y"] - brand["y"]) < 20


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium")
    parser.add_argument("--screenshots", type=Path, default=Path(".ui-artifacts"))
    args = parser.parse_args()
    args.screenshots.mkdir(exist_ok=True, parents=True)
    with (
        running_instance(Path(__file__).with_name("pinterest_fixture_worker.py")) as base,
        sync_playwright() as p,
    ):
        browser = p.chromium.launch(executable_path=args.chromium or shutil.which("google-chrome"))
        context = browser.new_context(
            viewport={"width": 1440, "height": 1050}, reduced_motion="reduce", locale="en-US"
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base, wait_until="networkidle")
        expect(page.locator("html")).to_have_attribute("lang", "en")
        english_picker = page.get_by_label("Language", exact=True)
        expect(english_picker.locator("option")).to_have_text(["English", "Українська"])
        assert_fits(page)
        page.screenshot(path=str(args.screenshots / "language-en-desktop.png"), full_page=True)

        url = "https://www.pinterest.com/pin/123456789/?tracking=discarded"
        page.get_by_label("Media URL", exact=True).fill(url)
        # The native select is keyboard-accessible and occupies the top-right header area.
        english_picker.focus()
        english_picker.press("ArrowDown")
        # ArrowDown changes the accessible name immediately; keep using keyboard focus.
        page.keyboard.press("Enter")
        expect(page.locator("html")).to_have_attribute("lang", "uk")
        expect(page.get_by_label("Мова", exact=True)).to_have_value("uk")
        expect(page.get_by_label("Посилання на медіа", exact=True)).to_have_value(url)
        expect(page.get_by_role("heading", name="Почніть із посилання")).to_be_visible()
        assert "Ваш власний простір" in page.locator('meta[name="description"]').get_attribute(
            "content"
        )
        assert page.evaluate("localStorage.getItem('download-convert.language')") == "uk"

        for width in (320, 390, 768, 1440):
            page.set_viewport_size({"width": width, "height": 1050})
            assert_fits(page)
            if width in (390, 1440):
                page.screenshot(
                    path=str(args.screenshots / f"language-uk-download-{width}.png"), full_page=True
                )

        nav = page.get_by_role("navigation", name="Головна навігація")
        nav.get_by_role("button", name="Завдання", exact=True).click()
        expect(page.get_by_text("Черга порожня. Час почати.", exact=True)).to_be_visible()
        nav.get_by_role("button", name="Конвертація", exact=True).click()
        expect(page.get_by_role("button", name="Обрати файл", exact=True)).to_be_visible()
        expect(page.get_by_text("512,0 МБ на файл", exact=False)).to_be_visible()
        expect(page.get_by_text("24 години", exact=False)).to_be_visible()
        nav.get_by_role("button", name="Налаштування", exact=True).click()
        expect(page.get_by_role("heading", name="Обробка та зберігання")).to_be_visible()
        expect(page.get_by_text("30 хвилин", exact=True)).to_be_visible()
        expect(page.get_by_text("Не налаштовано", exact=True)).to_be_visible()
        expect(page.get_by_text("реалізовано окремі піни", exact=False)).to_be_visible()
        expect(page.get_by_text("Точний формат джерела;", exact=False)).to_be_visible()
        page.screenshot(path=str(args.screenshots / "language-uk-settings.png"), full_page=True)
        page.reload(wait_until="networkidle")
        expect(page.get_by_label("Мова", exact=True)).to_have_value("uk")
        expect(page.locator("html")).to_have_attribute("lang", "uk")
        expect(page.get_by_role("heading", name="Обробка та зберігання")).to_be_visible()

        nav.get_by_role("button", name="Завантаження", exact=True).click()
        page.get_by_label("Посилання на медіа", exact=True).fill(url)
        page.get_by_role("button", name="Аналізувати посилання", exact=True).click()
        expect(
            page.get_by_role("heading", name="Owned Pinterest image", exact=False)
        ).to_be_visible(timeout=30000)
        expect(page.locator(".media-preview p")).to_contain_text("1 фото")
        photo = page.get_by_role("checkbox", name="Обрати фото 1", exact=True)
        expect(photo).to_be_checked()
        page.get_by_label("Мова", exact=True).select_option("en")
        expect(page.get_by_role("checkbox", name="Select photo 1", exact=True)).to_be_checked()
        expect(
            page.get_by_role("heading", name="Owned Pinterest image", exact=False)
        ).to_be_visible()
        page.get_by_label("Language", exact=True).select_option("uk")
        expect(photo).to_be_checked()
        page.get_by_role("button", name="Додати обрані фото до черги (1)", exact=True).click()
        expect(page.get_by_text("Завантаження додано до черги.", exact=True)).to_be_visible()
        download = page.get_by_role("link", name="Завантажити фото 1", exact=True)
        expect(download).to_be_visible(timeout=30000)
        response = page.request.get(base + download.get_attribute("href"))
        assert response.ok and response.body().startswith(b"\xff\xd8")
        expect(page.get_by_text("Аналіз посилання Pinterest", exact=True)).to_be_visible()
        expect(page.get_by_text("Завершено", exact=True)).to_have_count(2)
        page.set_viewport_size({"width": 390, "height": 844})
        assert_fits(page)
        page.screenshot(path=str(args.screenshots / "language-uk-tasks-mobile.png"), full_page=True)

        page.get_by_role("button", name="Конвертувати фото 1", exact=True).click()
        operations = page.get_by_label("Що ви хочете зробити?", exact=True)
        expect(operations).to_contain_text("Перетворити зображення на PNG")
        operations.select_option("webp")
        filename = page.locator(".filename").inner_text()
        page.get_by_label("Мова", exact=True).select_option("en")
        expect(page.get_by_label("What would you like to do?", exact=True)).to_have_value("webp")
        expect(page.locator(".filename")).to_have_text(filename)
        page.get_by_label("Language", exact=True).select_option("uk")
        expect(operations).to_have_value("webp")
        assert_fits(page)
        page.screenshot(
            path=str(args.screenshots / "language-uk-convert-mobile.png"), full_page=True
        )
        operations.select_option("png")
        page.get_by_role("button", name="Додати конвертацію до черги", exact=True).click()
        expect(page.get_by_text("Конвертацію додано до черги.", exact=True)).to_be_visible()
        converted = page.get_by_role("link", name="Завантажити результат", exact=True).first
        expect(converted).to_be_visible(timeout=30000)
        response = page.request.get(base + converted.get_attribute("href"))
        assert response.ok and response.body().startswith(b"\x89PNG\r\n\x1a\n")

        nav.get_by_role("button", name="Завантаження", exact=True).click()
        page.get_by_label("Посилання на медіа", exact=True).fill(
            "https://www.pinterest.com/pin/423456789/"
        )
        page.get_by_role("button", name="Аналізувати посилання", exact=True).click()
        preset = page.get_by_label("Профіль результату", exact=True)
        expect(preset).to_be_visible(timeout=30000)
        preset.select_option("mp3")
        page.get_by_text("Додатково · джерело та кодування", exact=True).click()
        page.get_by_label("Бітрейт результату MP3", exact=True).select_option("128")
        page.get_by_label("Мова", exact=True).select_option("en")
        expect(page.get_by_label("Output preset", exact=True)).to_have_value("mp3")
        expect(page.get_by_label("MP3 output bitrate", exact=True)).to_have_value("128")
        page.get_by_label("Language", exact=True).select_option("uk")
        expect(page.get_by_label("Бітрейт результату MP3", exact=True)).to_have_value("128")
        expect(page.get_by_label("Формат джерела", exact=True)).to_contain_text("зі звуком")
        assert_fits(page)
        page.screenshot(path=str(args.screenshots / "language-uk-mp3-mobile.png"), full_page=True)

        # Immediate API errors and stored task failures must both translate reactively.
        page.get_by_label("Посилання на медіа", exact=True).fill("https://example.com/unsupported")
        page.get_by_role("button", name="Аналізувати посилання", exact=True).click()
        alert = page.get_by_role("alert")
        expect(alert).to_contain_text("Код помилки: invalid_url")
        expect(alert).to_contain_text("Вставте коректне посилання")
        page.get_by_label("Мова", exact=True).select_option("en")
        expect(alert).to_contain_text("Error code: invalid_url")
        page.get_by_label("Language", exact=True).select_option("uk")
        expect(alert).to_contain_text("Код помилки: invalid_url")

        failed = {
            "id": "f" * 32,
            "kind": "analyze",
            "title": "Analyze Pinterest link",
            "state": "failed",
            "operation": "analyzing",
            "progress": None,
            "speed": None,
            "eta": None,
            "created_at": 1794481200,
            "expires_at": 4102444800,
            "expired": False,
            "result": None,
            "error": {"code": "drm_protected", "message": "DRM-protected source fixture."},
        }
        page.route("**/api/tasks", lambda route: route.fulfill(json=[failed]))
        nav.get_by_role("button", name="Завдання", exact=True).click()
        expect(page.get_by_text("DRM-захистом", exact=False)).to_be_visible(timeout=5000)
        expect(page.get_by_text("1 завдання", exact=True)).to_be_visible()
        expect(page.locator(".task-meta")).to_contain_text("лист.")
        page.get_by_label("Мова", exact=True).select_option("en")
        expect(page.get_by_text("DRM-protected source fixture.", exact=True)).to_be_visible()
        page.get_by_label("Language", exact=True).select_option("uk")
        expect(page.get_by_text("DRM-захистом", exact=False)).to_be_visible()
        page.unroute("**/api/tasks")
        assert not errors, errors

        for blocked in (False, True):
            isolated = browser.new_context(viewport={"width": 390, "height": 844})
            isolated.add_init_script(
                "Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Blocked', 'SecurityError'); } });"
                if blocked
                else "localStorage.setItem('download-convert.language', 'unsupported');"
            )
            other = isolated.new_page()
            other.on("pageerror", lambda error: errors.append(str(error)))
            other.goto(base, wait_until="networkidle")
            expect(other.locator("html")).to_have_attribute("lang", "en")
            other.get_by_label("Language", exact=True).select_option("uk")
            expect(other.get_by_role("heading", name="Почніть із посилання")).to_be_visible()
            assert_fits(other)
            isolated.close()
        assert not errors, errors
        context.close()
        browser.close()
    print(
        "PASS: English/Ukrainian pages, persisted selection, state retention, real JPEG/PNG, MP3 controls, errors, keyboard, blocked storage and 320–1440px layouts"
    )


if __name__ == "__main__":
    main()
