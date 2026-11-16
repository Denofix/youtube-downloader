import assert from "node:assert/strict";
import { test } from "node:test";

const storage = new Map([["download-convert.language", "uk"]]);
globalThis.window = {
  localStorage: {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
  },
};
const {
  locale,
  languageStorageKey,
  resolveLocale,
  t,
  text,
  count,
  mediaKind,
  operationLabel,
  errorMessage,
  ukrainian,
} = await import("../src/i18n.ts");

test("restores the supported preference and persists language changes", () => {
  assert.equal(locale.value, "uk");
  locale.value = "en";
  assert.equal(storage.get(languageStorageKey), "en");
  assert.equal(t("Analyze link"), "Analyze link");
  locale.value = "uk";
  assert.equal(storage.get(languageStorageKey), "uk");
  assert.equal(t("Analyze link"), "Аналізувати посилання");
});

test("unsupported or missing preferences use English", () => {
  for (const value of [undefined, null, "", "ua", "fr", "uk-UA", {}]) {
    assert.equal(resolveLocale(value), "en");
  }
  assert.equal(resolveLocale("uk"), "uk");
  assert.equal(resolveLocale("en"), "en");
});

test("every translation retains the English interpolation parameters", () => {
  const tokens = (value) =>
    [...value.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
  for (const [english, translated] of Object.entries(ukrainian)) {
    assert.ok(translated.trim(), english);
    assert.deepEqual(tokens(translated), tokens(english), english);
  }
  locale.value = "uk";
  const supplied = "<script>alert(1)</script>";
  assert.equal(
    t("Analyze {platform} link", { platform: supplied }),
    `Аналіз посилання ${supplied}`,
  );
});

test("Ukrainian counters handle singular, few, many and fractional values", () => {
  locale.value = "uk";
  for (const [value, result] of [
    [0, "0 завдань"],
    [1, "1 завдання"],
    [2, "2 завдання"],
    [5, "5 завдань"],
    [11, "11 завдань"],
    [21, "21 завдання"],
    [22, "22 завдання"],
    [25, "25 завдань"],
    [111, "111 завдань"],
  ]) {
    assert.equal(count("task", value), result);
  }
  assert.equal(count("item", 3), "3 елементи");
  assert.equal(count("frame", 5), "5 кадрів");
  assert.equal(count("hour", 24), "24 години");
  assert.equal(count("hour", 1.5), "1,5 години");
  assert.equal(count("photo", 1), "1 фото");
  locale.value = "en";
  assert.equal(count("task", 1), "1 task");
  assert.equal(count("task", 2), "2 tasks");
});

test("capability labels and settings data change without altering IDs or source data", () => {
  locale.value = "uk";
  assert.equal(
    operationLabel("mp3", "video", "Extract audio to MP3"),
    "Видобути аудіо у MP3",
  );
  assert.equal(
    operationLabel("mp3", "audio", "Convert audio to MP3"),
    "Конвертувати аудіо у MP3",
  );
  assert.equal(
    operationLabel("webp", "image", "Convert image to WEBP"),
    "Перетворити зображення на WEBP",
  );
  assert.equal(
    operationLabel("gif", "video", "Create a short GIF clip"),
    "Створити короткий GIF",
  );
  assert.equal(mediaKind("animation"), "Анімація");
  assert.equal(
    text("Exact source format; merge separate tracks without re-encoding."),
    "Точний формат джерела; об’єднання окремих доріжок без перекодування.",
  );
  assert.equal(text("My original source title"), "My original source title");
  assert.equal(text("avc1.64001F"), "avc1.64001F");
});

test("errors respond to the selected language while retaining English API detail", () => {
  const original = "The source offers this item only in DRM-protected formats.";
  locale.value = "en";
  assert.equal(errorMessage(original, "drm_protected"), original);
  locale.value = "uk";
  assert.match(errorMessage(original, "drm_protected"), /DRM-захистом/);
  assert.match(errorMessage("No audio", "no_audio"), /аудіодоріжки/);
  assert.match(errorMessage("Expired", "file_expired"), /Термін зберігання/);
  assert.equal(
    errorMessage("Future server message", "future_code"),
    "Сталася помилка. Спробуйте ще раз.",
  );
  assert.equal(
    errorMessage("This analysis has expired. Analyze again."),
    "Термін дії аналізу минув. Проаналізуйте посилання знову.",
  );
});

test("switching remains usable when browser storage throws", () => {
  const previous = window.localStorage;
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    get() {
      throw new Error("Storage blocked");
    },
  });
  assert.doesNotThrow(() => {
    locale.value = "en";
    locale.value = "uk";
  });
  assert.equal(t("Language"), "Мова");
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: previous,
  });
});
