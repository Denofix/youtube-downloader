import { ref, watch } from "vue";

export type Locale = "en" | "uk";
export const languageStorageKey = "download-convert.language";

// English messages are stable keys. Source titles, filenames and codec IDs are data.
export const ukrainian = {
  download: "Завантаження",
  convert: "Конвертація",
  tasks: "Завдання",
  settings: "Налаштування",
  Language: "Мова",
  "Skip to content": "Перейти до вмісту",
  "Main navigation": "Головна навігація",
  "Worker online": "Обробник працює",
  "Worker offline": "Обробник недоступний",
  Reconnecting: "Відновлення з’єднання",
  "Unable to continue": "Не вдалося продовжити",
  "Error code: {code}": "Код помилки: {code}",
  "Dismiss error": "Закрити повідомлення про помилку",
  "Something went wrong.": "Сталася помилка. Спробуйте ще раз.",
  "The worker is offline. Tasks will wait in the queue until it starts.":
    "Обробник недоступний. Завдання чекатимуть у черзі, доки він не запуститься.",
  "YOUR MEDIA. YOUR WORKSPACE.": "ВАШІ МЕДІА. ВАШ ПРОСТІР.",
  "A link. A format.": "Посилання. Формат.",
  "Make it yours.": "Збережіть для себе.",
  "Download a video or save a track.": "Завантажте відео або збережіть трек.",
  "Choose what you need. Keep the quality you picked.":
    "Обирайте потрібне. Зберігайте обрану якість.",
  "Download media": "Завантаження медіа",
  "Start with a link": "Почніть із посилання",
  "Video · audio · photos": "Відео · аудіо · фото",
  "Media URL": "Посилання на медіа",
  "Paste a YouTube, SoundCloud, TikTok, Instagram or Pinterest link":
    "Вставте посилання з YouTube, SoundCloud, TikTok, Instagram або Pinterest",
  "Analyzing…": "Аналізуємо…",
  "Analyze link": "Аналізувати посилання",
  "YouTube videos & Shorts, SoundCloud tracks, TikTok videos or photo posts, Instagram Reels, photos or carousels, and Pinterest image, GIF or video pins. One post at a time.":
    "Відео й Shorts із YouTube, треки SoundCloud, відео або фотопублікації TikTok, Reels, фото й каруселі Instagram, а також зображення, GIF і відеопіни Pinterest. Одна публікація за раз.",
  "Waiting for the worker…": "Очікуємо на обробник…",
  "Analyzing your link…": "Аналізуємо ваше посилання…",
  Cancel: "Скасувати",
  "Source media artwork": "Обкладинка медіа",
  "Photo post preview": "Перегляд фотопублікації",
  "Creator unknown": "Автор невідомий",
  "Choose your items": "Оберіть елементи",
  "Choose your photos": "Оберіть фотографії",
  "Select all": "Обрати всі",
  "Clear selection": "Скасувати вибір",
  "Choose the items and video quality you want. Original photos keep their source bytes; multiple selected files also include a ZIP.":
    "Оберіть елементи та якість відео. Оригінали фото зберігаються без змін; кілька обраних файлів також доступні в ZIP-архіві.",
  "Verified original images, with no re-encoding. Multiple selected photos also include a ZIP.":
    "Перевірені оригінали зображень без перекодування. Кілька обраних фото також доступні в ZIP-архіві.",
  "Select item {position}": "Обрати елемент {position}",
  "Select photo {position}": "Обрати фото {position}",
  "{kind} {position} preview": "Попередній перегляд: {kind} {position}",
  Photo: "Фото",
  Video: "Відео",
  Audio: "Аудіо",
  Image: "Зображення",
  Animation: "Анімація",
  "Source format": "Формат джерела",
  "Output preset": "Профіль результату",
  "Source format for item {position}": "Формат джерела елемента {position}",
  "Output preset for item {position}": "Профіль результату елемента {position}",
  "MP3 bitrate for item {position}": "Бітрейт MP3 для елемента {position}",
  "Original · no re-encoding": "Оригінал · без перекодування",
  "Audio MP3 · re-encode": "Аудіо MP3 · перекодування",
  "Compatible MP4 · H.264 + AAC": "Сумісний MP4 · H.264 + AAC",
  "MP3 bitrate": "Бітрейт MP3",
  "Add selected items to queue ({count})":
    "Додати обрані елементи до черги ({count})",
  "Add selected photos to queue ({count})":
    "Додати обрані фото до черги ({count})",
  "Source: ": "Джерело: ",
  "About ": "Приблизно ",
  "Audio encoding required": "Потрібне кодування аудіо",
  "Output: MP4 · H.264 + AAC": "Результат: MP4 · H.264 + AAC",
  "Separate tracks · lossless merge":
    "Окремі доріжки · об’єднання без перекодування",
  "Direct source download": "Пряме завантаження з джерела",
  "Sources with a reported watermark are excluded. Video delivery keeps the selected resolution; HEVC is re-encoded for compatible playback. Output size may change.":
    "Джерела із заявленим водяним знаком виключено. Обрана роздільність зберігається; HEVC перекодовується для сумісного відтворення. Розмір результату може змінитися.",
  "This source does not report audio presence. Original keeps the available streams; MP3 requires an audio stream in the actual file.":
    "Джерело не повідомляє про наявність звуку. Оригінал зберігає доступні потоки; для MP3 потрібна аудіодоріжка в самому файлі.",
  "Advanced · source details & encoding": "Додатково · джерело та кодування",
  "Source format IDs": "Ідентифікатори форматів джерела",
  "Source codecs": "Кодеки джерела",
  "Source dimensions": "Розміри джерела",
  "Source audio bitrate": "Бітрейт аудіо джерела",
  "MP3 output bitrate": "Бітрейт результату MP3",
  "A higher output bitrate does not restore detail missing from the source.":
    "Вищий бітрейт результату не відновлює деталі, втрачені в джерелі.",
  "Add download to queue": "Додати завантаження до черги",
  "A queue that stays": "Черга зберігається",
  "Tasks survive a page refresh.":
    "Завдання зберігаються після оновлення сторінки.",
  "Saved, then converted": "Зберігайте й конвертуйте",
  "Reuse a result while it is available.":
    "Використовуйте результат повторно, поки він доступний.",
  "Your own instance": "Ваш власний сервіс",
  "Files are processed on your server.":
    "Файли обробляються на вашому сервері.",
  "Have a file already?": "Уже маєте файл?",
  "Open the converter ↗": "Відкрити конвертер ↗",
  "A DIFFERENT FORMAT. THE SAME IDEA.": "ІНШИЙ ФОРМАТ. ТА САМА ІДЕЯ.",
  "Give your file": "Надайте файлу",
  "a new format.": "новий формат.",
  "Video, audio, images and short GIFs.":
    "Відео, аудіо, зображення та короткі GIF.",
  "Compatible operations appear after inspection.":
    "Доступні перетворення з’являться після перевірки файлу.",
  "Convert media": "Конвертація медіа",
  "Inspecting your file…": "Перевіряємо ваш файл…",
  "Drop your file here": "Перетягніть файл сюди",
  "Detecting contents and compatible operations.":
    "Визначаємо вміст і доступні перетворення.",
  "Or choose a video, audio file, image or animation.":
    "Або оберіть відео, аудіофайл, зображення чи анімацію.",
  "Uploading…": "Надсилаємо…",
  "Choose a file": "Обрати файл",
  "{size} per file · Files expire after {retention}":
    "{size} на файл · Файли зберігаються протягом {retention}",
  "Inspecting file": "Перевірка файлу",
  "Choose media file": "Обрати медіафайл",
  "Change file": "Змінити файл",
  "What would you like to do?": "Що ви хочете зробити?",
  "No compatible output encoder is installed. Check server diagnostics.":
    "Сумісний кодувальник результату не встановлено. Перевірте діагностику сервера.",
  "Start (seconds)": "Початок (секунди)",
  "Duration (seconds)": "Тривалість (секунди)",
  "Frames per second": "Кадрів за секунду",
  "Width (pixels)": "Ширина (пікселі)",
  "Animation is preserved in video/GIF outputs. Still-frame extraction is planned.":
    "Анімація зберігається у відео та GIF. Видобування окремого кадру заплановано.",
  "JPEG does not support transparency. Transparent areas will use a white background.":
    "JPEG не підтримує прозорість. Прозорі ділянки матимуть біле тло.",
  "Smaller Video: H.264 CRF 25 or VP9 CRF 34. Size depends on the source; encoding does not improve source quality.":
    "Менше відео: H.264 CRF 25 або VP9 CRF 34. Розмір залежить від джерела; кодування не покращує його якість.",
  "Output bitrate": "Бітрейт результату",
  "Add conversion to queue": "Додати конвертацію до черги",
  "Source available until {date}.": "Джерело доступне до {date}.",
  "EVERYTHING IN ONE PLACE": "УСЕ В ОДНОМУ МІСЦІ",
  "Your ": "Ваші ",
  "tasks.": "завдання.",
  "Downloads and conversions, from queued to ready.":
    "Завантаження й конвертації — від черги до готового результату.",
  "A clear queue. A fresh start.": "Черга порожня. Час почати.",
  "Your downloads and conversions will appear here.":
    "Тут з’являться ваші завантаження й конвертації.",
  "Create your first task": "Створити перше завдання",
  "In progress": "У роботі",
  History: "Історія",
  "Processed in {duration}": "Оброблено за {duration}",
  Download: "Завантаження",
  "Convert & check": "Конвертація та перевірка",
  "{operation} progress": "Перебіг: {operation}",
  "{duration} left": "Залишилося {duration}",
  "Technical details": "Технічні подробиці",
  "Task {id}": "Завдання {id}",
  "Result expired. Run this task again to create a new result.":
    "Термін зберігання результату минув. Запустіть завдання ще раз, щоб отримати новий результат.",
  "Available until {date}": "Доступно до {date}",
  "Converted image preview": "Перегляд перетвореного зображення",
  "Choose items": "Обрати елементи",
  "Choose photos": "Обрати фото",
  "View formats": "Переглянути формати",
  "Download ZIP ({count})": "Завантажити ZIP ({count})",
  "Download result": "Завантажити результат",
  "Choose conversion": "Обрати перетворення",
  Convert: "Конвертувати",
  "Analyze again": "Аналізувати знову",
  Retry: "Повторити",
  "Downloaded item {position}": "Завантажений елемент {position}",
  "Downloaded photo {position}": "Завантажене фото {position}",
  "Download item {position}": "Завантажити елемент {position}",
  "Download photo {position}": "Завантажити фото {position}",
  "Convert item {position}": "Конвертувати елемент {position}",
  "Convert photo {position}": "Конвертувати фото {position}",
  "YOUR INSTANCE, AT A GLANCE": "ВАШ СЕРВІС: ГОЛОВНЕ",
  "Workspace ": "Налаштування ",
  "settings.": "простору.",
  "Runtime diagnostics and limits configured by the owner.":
    "Діагностика середовища та обмеження, встановлені власником.",
  "Processing & storage": "Обробка та зберігання",
  "Maximum file size": "Максимальний розмір файлу",
  "Storage used / limit": "Використано / ліміт сховища",
  "Result retention": "Термін зберігання результатів",
  "Concurrent tasks": "Одночасних завдань",
  "Task timeout": "Граничний час завдання",
  "Owner cookie file": "Файл cookie власника",
  "Configured on server": "Налаштовано на сервері",
  "Not configured": "Не налаштовано",
  "The owner can adjust these limits in the server environment and restart the service.":
    "Власник може змінити ці обмеження в налаштуваннях середовища сервера та перезапустити сервіс.",
  "Runtime diagnostics": "Діагностика середовища",
  "Browser transport support": "Підтримка браузерного транспорту",
  Available: "Доступно",
  "Missing · rebuild the worker image":
    "Відсутня · перебудуйте образ обробника",
  missing: "не встановлено",
  "Sources & rollout": "Джерела та підтримка",
  "Access depends on the link, region, authorization and extractor. An extractor listing does not guarantee a successful download.":
    "Доступ залежить від посилання, регіону, авторизації та екстрактора. Наявність джерела у списку екстрактора не гарантує успішного завантаження.",
  "Processing presets": "Профілі обробки",
  Original: "Оригінал",
  "Audio MP3": "Аудіо MP3",
  "Smaller Video": "Менше відео",
  "GIF Clip": "Фрагмент GIF",
  "Exact source format; merge separate tracks without re-encoding.":
    "Точний формат джерела; об’єднання окремих доріжок без перекодування.",
  "MP3 at 128, 192 or 320 kbps. Does not restore lost source detail.":
    "MP3 із бітрейтом 128, 192 або 320 кбіт/с. Не відновлює втрачені деталі джерела.",
  "H.264 CRF 25 or VP9 CRF 34; actual size depends on the source.":
    "H.264 CRF 25 або VP9 CRF 34; фактичний розмір залежить від джерела.",
  "Up to 15 seconds, 24 FPS and 720 pixels wide.":
    "До 15 секунд, 24 кадрів/с і 720 пікселів завширшки.",
  "implemented; see live verification report":
    "реалізовано; див. звіт перевірки на реальних джерелах",
  "public unprotected tracks; see live verification report":
    "публічні треки без захисту; див. звіт перевірки на реальних джерелах",
  "individual videos and photo posts verified by owner; selected files and ZIP available":
    "окремі відео та фотопублікації перевірено власником; доступні обрані файли й ZIP",
  "individual Reels/video posts, photos, photo-carousel subsets and retained video-to-MP3 verified by owner; see verification reports":
    "окремі Reels/відеопублікації, фото, вибір із фотокаруселей і збережене відео → MP3 перевірено власником; див. звіти перевірок",
  "individual image/GIF/video pins and pin.it links implemented; see verification reports":
    "реалізовано окремі піни із зображеннями/GIF/відео та посилання pin.it; див. звіти перевірок",
  "Open source ↗": "Відкритий код ↗",
  "by Nord_Fillin": "автор: Nord_Fillin",
  "Size unknown": "Розмір невідомий",
  "Duration unknown": "Тривалість невідома",
  KB: "КБ",
  MB: "МБ",
  GB: "ГБ",
  fps: "кадрів/с",
  kbps: "кбіт/с",
  s: "с",
  "audio unknown": "наявність звуку невідома",
  "with audio": "зі звуком",
  "no audio": "без звуку",
  unknown: "невідомо",
  waiting: "очікування",
  starting: "запуск",
  analyzing: "аналіз",
  inspecting: "перевірка файлу",
  downloading: "завантаження",
  merging: "об’єднання",
  converting: "конвертація",
  verifying: "перевірка результату",
  preparing: "підготовка",
  ready: "готово",
  interrupted: "перервано",
  queued: "У черзі",
  running: "Виконується",
  completed: "Завершено",
  failed: "Помилка",
  cancelled: "Скасовано",
  analyze: "аналіз",
  inspect: "перевірка файлу",
  "Analyze {platform} link": "Аналіз посилання {platform}",
  "Encode video as {format}": "Перекодувати відео у {format}",
  "Convert image to {format}": "Перетворити зображення на {format}",
  "Extract audio to {format}": "Видобути аудіо у {format}",
  "Convert audio to {format}": "Конвертувати аудіо у {format}",
  "Create a short GIF clip": "Створити короткий GIF",
  "Download added to the queue.": "Завантаження додано до черги.",
  "Conversion added to the queue.": "Конвертацію додано до черги.",
  "This analysis has expired. Analyze again.":
    "Термін дії аналізу минув. Проаналізуйте посилання знову.",
  "Analyze this TikTok link again to refresh compatible sources without a reported watermark.":
    "Проаналізуйте посилання TikTok знову, щоб оновити сумісні джерела без заявленого водяного знака.",
  "This build accepts one file at a time. Upload additional files separately.":
    "Ця версія приймає один файл за раз. Надсилайте інші файли окремо.",
  "Check the selected parameters.": "Перевірте обрані параметри.",
  "The server could not complete this request.":
    "Сервер не зміг виконати цей запит.",
  "Cannot connect to the server. Check the connection and try again.":
    "Не вдалося з’єднатися із сервером. Перевірте з’єднання та спробуйте знову.",
  "Your self-hosted space to download and convert media.":
    "Ваш власний простір для завантаження та конвертації медіа.",
} as const;

export type Message = keyof typeof ukrainian;
type Parameters = Record<string, string | number>;

export function resolveLocale(value: unknown): Locale {
  return value === "uk" ? "uk" : "en";
}

function storedLocale(): Locale {
  try {
    return resolveLocale(window.localStorage.getItem(languageStorageKey));
  } catch {
    return "en";
  }
}

export const locale = ref<Locale>(storedLocale());

export function t(message: Message, parameters: Parameters = {}): string {
  const translated = locale.value === "uk" ? ukrainian[message] : message;
  return translated.replace(/\{(\w+)\}/g, (token, key: string) =>
    Object.hasOwn(parameters, key) ? String(parameters[key]) : token,
  );
}

export function text(value: string): string {
  return Object.hasOwn(ukrainian, value) ? t(value as Message) : value;
}

const pluralForms = {
  task: ["завдання", "завдання", "завдань", "завдання"],
  photo: ["фото", "фото", "фото", "фото"],
  item: ["елемент", "елементи", "елементів", "елемента"],
  frame: ["кадр", "кадри", "кадрів", "кадру"],
  hour: ["година", "години", "годин", "години"],
  minute: ["хвилина", "хвилини", "хвилин", "хвилини"],
};
export function count(noun: keyof typeof pluralForms, value: number): string {
  if (locale.value === "en") return `${value} ${noun}${value === 1 ? "" : "s"}`;
  const rule = new Intl.PluralRules("uk").select(value);
  const index = { one: 0, few: 1, many: 2, other: 3 }[
    rule as "one" | "few" | "many" | "other"
  ];
  return `${new Intl.NumberFormat("uk-UA").format(value)} ${pluralForms[noun][index]}`;
}

export function mediaKind(kind?: string): string {
  const names: Record<string, Message> = {
    video: "Video",
    audio: "Audio",
    image: "Image",
    animation: "Animation",
  };
  return t(names[kind || ""] || "Photo");
}

export function operationLabel(
  id: string,
  kind: string,
  fallback: string,
): string {
  if (id === "gif") return t("Create a short GIF clip");
  const format = id.toUpperCase();
  if (["jpg", "png", "webp"].includes(id))
    return t("Convert image to {format}", { format });
  if (["mp4", "mov", "mkv", "webm"].includes(id))
    return t("Encode video as {format}", { format });
  if (["mp3", "m4a", "wav", "flac", "ogg"].includes(id))
    return t(
      kind === "video"
        ? "Extract audio to {format}"
        : "Convert audio to {format}",
      { format },
    );
  return text(fallback);
}

const errors: Record<string, string> = {
  access_required:
    "Для цього джерела потрібен доступ. Власник може налаштувати cookie на сервері та повторити аналіз.",
  analysis_expired: "Термін дії аналізу минув. Проаналізуйте посилання знову.",
  analysis_refresh_required:
    "Оновіть аналіз посилання, щоб отримати актуальні сумісні формати.",
  collection_planned:
    "Підтримується одна публікація за раз. Посилання на колекції, канали та профілі поки не підтримуються.",
  drm_protected:
    "Джерело надає цей матеріал лише з DRM-захистом. Оберіть матеріал із доступним завантаженням без захисту або скористайтеся офіційним завантаженням автора.",
  empty_file: "Оберіть непорожній медіафайл.",
  file_expired:
    "Термін зберігання файлу минув. Завантажте або створіть його знову.",
  file_limit:
    "Файл або результат перевищує встановлене обмеження розміру. Оберіть менший файл чи набір.",
  format_unavailable:
    "Цей формат більше недоступний. Проаналізуйте посилання знову.",
  image_limit: "Зображення перевищує обмеження розміру або кількості пікселів.",
  image_unsupported: "Цей формат зображення або анімації не підтримується.",
  incompatible_conversion:
    "Це перетворення недоступне для файлу або встановлених кодеків.",
  inspection_pending: "Дочекайтеся завершення перевірки файлу.",
  instagram_permalink_required:
    "Вставте пряме посилання на одну публікацію або Reel Instagram.",
  instagram_post_unreadable:
    "Instagram не повернув придатних даних публікації. Перевірте доступ до джерела та повторіть аналіз.",
  invalid_clip:
    "Початок фрагмента має бути в межах тривалості джерела. Перевірте параметри GIF.",
  invalid_format: "Оберіть доступний формат після нового аналізу посилання.",
  invalid_origin: "Використовуйте сервіс через його власний інтерфейс.",
  invalid_parameters: "Перевірте обрані параметри.",
  invalid_photo:
    "Не вдалося повністю декодувати зображення. Спробуйте інше джерело.",
  invalid_result:
    "Результат не пройшов перевірку вмісту або звуку. Перевірте джерело й повторіть спробу.",
  invalid_selection:
    "Вибір елементів некоректний. Оновіть аналіз та оберіть елементи знову.",
  invalid_source_media:
    "Джерело повернуло некоректні медіадані. Перевірте доступ і з’єднання, потім повторіть аналіз.",
  invalid_url: "Вставте коректне посилання на одну підтримувану публікацію.",
  live_unsupported:
    "Прямі трансляції поки не підтримуються. Оберіть готовий запис.",
  media_limit: "Матеріал перевищує встановлене обмеження тривалості.",
  media_tool_error:
    "Інструмент обробки медіа завершився з помилкою. Перевірте файл і діагностику сервера.",
  missing_encoder:
    "Потрібний кодувальник не встановлено. Перевірте діагностику сервера.",
  missing_ffmpeg: "Потрібен FFmpeg. Перевірте діагностику сервера.",
  network_blocked:
    "Джерело заблокувало доступ із мережі сервера. Перевірте доступність або оберіть інший публічний матеріал.",
  network_error:
    "Не вдалося з’єднатися із сервером. Перевірте з’єднання та спробуйте знову.",
  no_audio: "Цей варіант не має аудіодоріжки. Оберіть формат зі звуком.",
  no_formats:
    "Джерело не повернуло доступних форматів. Перевірте доступ і повторіть аналіз.",
  not_found: "Завдання або файл не знайдено.",
  not_photo_post: "Посилання не містить підтримуваної фотопублікації.",
  photo_download_failed:
    "Не вдалося завантажити зображення. Перевірте доступ до джерела й повторіть аналіз.",
  photo_limit: "Публікація перевищує обмеження кількості елементів.",
  photo_snapshot_changed:
    "Збережені дані зображення змінилися або недоступні. Повторіть аналіз публікації.",
  photo_source_unavailable:
    "Джерело зображення недоступне або не пройшло перевірку. Повторіть аналіз.",
  pinterest_external_embed:
    "Піни із зовнішніми плеєрами не підтримуються. Оберіть матеріал, розміщений у Pinterest.",
  pinterest_multi_item_unsupported:
    "Цей тип піна з кількома елементами поки не підтримується.",
  pinterest_permalink_required:
    "Вставте пряме посилання на один пін Pinterest або посилання pin.it.",
  preview_only:
    "Це лише попередній перегляд. Завантажте оригінал перед конвертацією.",
  preview_unavailable: "Попередній перегляд цього файлу недоступний.",
  processing_failed:
    "Не вдалося обробити завдання. Перевірте джерело, файл і діагностику інструментів, потім повторіть спробу.",
  server_error:
    "Сервер не зміг виконати цей запит. Спробуйте ще раз і перевірте діагностику сервера.",
  quality_mismatch:
    "Джерело не відповідає обраній якості. Повторіть аналіз і оберіть актуальний формат.",
  queue_full: "Черга заповнена. Дочекайтеся завершення одного із завдань.",
  short_link_error:
    "Не вдалося розкрити коротке посилання. Вставте пряме посилання на публікацію.",
  soundcloud_client_id:
    "Не вдалося отримати публічні дані доступу до API SoundCloud. Перевірте доступ сервера та версії інструментів.",
  source_changed:
    "Публікація або доступні потоки змінилися. Проаналізуйте посилання знову.",
  source_error:
    "Не вдалося обробити джерело. Перевірте з’єднання та версії інструментів і повторіть аналіз.",
  source_page_unreadable:
    "Екстрактор не зміг прочитати сторінку джерела. Повторіть спробу; якщо помилка зберігається, перевірте браузерний транспорт у налаштуваннях і доступ сервера.",
  source_rate_limited:
    "Джерело обмежує кількість запитів. Зачекайте перед наступною спробою.",
  source_region:
    "Матеріал недоступний у регіоні сервера. Оберіть інший доступний матеріал.",
  source_unavailable:
    "Матеріал недоступний. Перевірте посилання та права доступу.",
  storage_full:
    "У сховищі недостатньо місця. Звільніть місце або дочекайтеся очищення прострочених файлів.",
  task_active: "Дочекайтеся завершення завдання перед повторним запуском.",
  tiktok_source_unavailable:
    "Сумісне джерело TikTok недоступне. Повторіть аналіз посилання.",
  tls_error:
    "Сервер не зміг перевірити сертифікат джерела. Перевірте довірені сертифікати та налаштування проксі.",
  unknown_job: "Цей тип завдання не підтримується.",
  unsupported_file:
    "Формат або вміст файлу не підтримується. Оберіть підтримуваний медіафайл.",
  cancelled: "Завдання скасовано.",
  worker_interrupted:
    "Обробник перезапущено або перервано. Запустіть завдання повторно.",
  timeout:
    "Перевищено граничний час завдання. Спробуйте коротший або менший файл.",
  worker_error:
    "Обробник завершився з помилкою. Перевірте діагностику й повторіть завдання.",
};

export function errorMessage(message: string, code = ""): string {
  if (locale.value === "en") return message || t("Something went wrong.");
  return (
    errors[code] ||
    (Object.hasOwn(ukrainian, message)
      ? text(message)
      : t("Something went wrong."))
  );
}

watch(
  locale,
  (value) => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = value;
      document
        .querySelector('meta[name="description"]')
        ?.setAttribute(
          "content",
          t("Your self-hosted space to download and convert media."),
        );
    }
    try {
      window.localStorage.setItem(languageStorageKey, value);
    } catch {
      // Language switching still works when browser storage is disabled.
    }
  },
  { immediate: true, flush: "sync" },
);
