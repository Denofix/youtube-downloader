# Download & Convert - Windows

Установка, настройка и пользование. Инструкция на русском; интерфейс платформы - **English / Українська**. Проверяемая среда запуска: Linux-контейнеры Docker Desktop. Команды вводите **по одной, сверху вниз** в PowerShell. Символы `PS ...>` и `>>` копировать не нужно.

## 1. Подготовка

1. Установите [Git for Windows](https://git-scm.com/install/windows).
2. Проверьте [требования Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/): поддерживаемая Windows x64, виртуализация в BIOS/UEFI, от 8 ГБ ОЗУ. В PowerShell **от имени администратора** выполните `wsl --install`, затем перезагрузите ПК. Если WSL уже установлен, выполните `wsl --update`.
3. Установите и запустите [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/). Используйте **WSL 2 engine** и **Linux containers**. Дождитесь работающего движка. Если Docker приостановлен, выберите **Resume / Unpause**.
4. Откройте новый обычный PowerShell и проверьте:

```powershell
git --version
docker compose version
docker run --rm hello-world
```

Ожидается `Hello from Docker!`. Python, Node.js и FFmpeg отдельно устанавливать не нужно - они включены в образ платформы.

## 2. Скачать и открыть проект

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Projects" | Out-Null
Set-Location "$env:USERPROFILE\Projects"
git clone --branch main https://github.com/Denofix/youtube-downloader.git
Set-Location .\youtube-downloader
Invoke-Item .
```

Откроется папка проекта. Для запуска редактор не требуется. Оставьте терминал в папке, где находятся `compose.yaml` и `Dockerfile`. Если проект уже скачан, используйте раздел обновления ниже. Для пути с пробелами нужны кавычки:

```powershell
Set-Location "D:\Portfolio projects\youtube-downloader"
```

## 3. Настроить и запустить

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
Invoke-RestMethod http://localhost:8080/api/health
Start-Process "http://localhost:8080"
```

Первая сборка скачает зависимости; дождитесь её завершения. Оба сервиса `api` и `worker` должны работать. API: `status = ok`, `worker_online = True`. Если обработчик ещё запускается, повторите запрос через несколько секунд. Адрес: [http://localhost:8080](http://localhost:8080).

Для изменения настроек откройте `notepad .env`, сохраните файл и повторите команду `docker compose up -d --build --wait`.

| Настройка | По умолчанию | Что меняет |
| --- | --- | --- |
| `PORT` | `8080` | Порт сайта на этом ПК; при `8081` открывайте `http://localhost:8081` |
| `MAX_FILE_BYTES` | `536870912` | До 512 МиБ на файл |
| `MAX_STORAGE_BYTES` | `5368709120` | До 5 ГиБ медиа в хранилище |
| `RESULT_TTL_SECONDS` | `86400` | Хранение файлов 24 часа |
| `JOB_TIMEOUT_SECONDS` | `1800` | До 30 минут на одно задание |

Настройки на странице Settings показывают значения сервера; редактируются они в `.env`. Для обычного запуска ключи API не нужны. Доступность публикации зависит от источника. Платформа по умолчанию доступна только на этом ПК.

## 4. Пользоваться платформой

Справа сверху выберите **English / Українська**. Язык сохранится в этом браузере.

| Раздел | Действие |
| --- | --- |
| **Download / Завантаження** | Вставьте ссылку на одну публичную публикацию YouTube, TikTok, Instagram, Pinterest или трек SoundCloud. Нажмите **Analyze link / Аналізувати посилання**, выберите формат, качество или фото и добавьте в очередь. Несколько выбранных фото/элементов также доступны в ZIP. |
| **Tasks / Завдання** | Дождитесь **Completed / Завершено**, скачайте результат и откройте его. Здесь же - отмена, повтор, срок хранения и переход к конвертации сохранённого файла. |
| **Convert / Конвертація** | Загрузите один локальный файл, дождитесь анализа и выберите доступное преобразование: например, видео со звуком в MP3, PNG в WebP или видео в короткий GIF. Настройте битрейт или параметры GIF и добавьте в очередь. |
| **Settings / Налаштування** | Проверьте состояние обработчика, версии инструментов, лимиты и свободное место. |

Для первой проверки используйте короткий ролик и небольшое изображение. У видео проверьте картинку и звук; у GIF - движение; у ZIP - состав файлов. MP3 предлагается только при наличии аудиодорожки. Повышение битрейта не восстанавливает потерянное качество. Пакетная загрузка, профили/каналы и плейлисты пока не поддерживаются.

## 5. Обновление и остановка

В папке проекта, при запущенном Docker Desktop, выполните **в таком порядке**:

```powershell
git fetch origin
git switch main
git pull --ff-only
docker compose up -d --build --wait
```

Затем нажмите **Ctrl+F5** и заново проанализируйте ссылку, если обновление касалось источников. Если Git сообщает о локальных изменениях, сохраните их перед переключением; не удаляйте их через `reset --hard`.

По необходимости:

```powershell
docker compose stop
docker compose up -d --wait
docker compose logs --tail 80 api worker
```

Первая команда останавливает, вторая запускает, третья показывает логи. История и файлы находятся в постоянном Docker-томе; `docker compose down` сохраняет его, а **`docker compose down -v` удаляет данные**.

## 6. Если не запускается

| Симптом | Что сделать |
| --- | --- |
| `Docker Desktop is manually paused` | Resume / Unpause в Docker Desktop, затем повторить запуск |
| `no configuration file provided` | Перейти в корень проекта и проверить `Test-Path .\compose.yaml`; сначала обновить Git, затем запускать Docker |
| `unknown flag: --buildgit` | Вставлять команды отдельно: `--build` и `git fetch` относятся к разным строкам |
| Путь с пробелами не открывается | Заключить весь путь в кавычки |
| Порт уже занят | Задать свободный `PORT`, например `8081`, в `.env`, пересоздать сервисы и открыть новый адрес |
| Задания стоят в очереди | Проверить `worker_online`, состояние `worker` и логи |
| Интерфейс выглядит устаревшим | Дождаться успешной сборки, затем Ctrl+F5 |

Для разбора проблемы сохраните текст ошибки, вывод `docker compose ps` и последние логи. [Репозиторий](https://github.com/Denofix/youtube-downloader) · [Матрица конвертера](../media-service/converter-matrix.md) · [Эксплуатация и резервные копии](../media-service/operations.md).
