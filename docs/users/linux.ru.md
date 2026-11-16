# Download & Convert - Linux

Установка, настройка и пользование. Команды ниже рассчитаны на **Ubuntu 24.04 LTS**, Desktop, Server или VMware. Для других дистрибутивов используйте [официальную установку Docker Engine](https://docs.docker.com/engine/install/) и Compose plugin, затем продолжайте с раздела 2. Вводите команды **по одной, сверху вниз**. Символ приглашения `$` копировать не нужно.

## 1. Подготовка Ubuntu

Если Docker и `docker compose` уже работают, не переустанавливайте их. Для чистой Ubuntu установите пакеты из репозитория Ubuntu:

```bash
sudo apt update
sudo apt install -y git curl software-properties-common
sudo add-apt-repository -y universe
sudo apt update
sudo apt install -y docker.io docker-compose-v2 docker-buildx
sudo systemctl enable --now docker
git --version
sudo docker compose version
sudo docker run --rm hello-world
```

Ожидается `Hello from Docker!`. Пакеты: [docker.io](https://packages.ubuntu.com/noble/docker.io), [docker-compose-v2](https://packages.ubuntu.com/noble/docker-compose-v2), [docker-buildx](https://packages.ubuntu.com/noble/docker-buildx). Альтернативная установка из репозитория производителя описана в [Docker Docs](https://docs.docker.com/engine/install/ubuntu/); не смешивайте два способа на уже настроенном сервере.

В инструкции команды Docker выполняются с `sudo`; вводимый пароль не отображается. Git запускайте от своего пользователя. Python, Node.js и FFmpeg отдельно не нужны - они включены в образ платформы.

## 2. Скачать и открыть проект

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone --branch main https://github.com/Denofix/youtube-downloader.git
cd youtube-downloader
ls compose.yaml Dockerfile
```

Все дальнейшие команды выполняются из этой папки. Если репозиторий уже скачан, перейдите в него и используйте раздел обновления ниже. На Ubuntu Desktop папку можно открыть через `xdg-open .`; на сервере графический интерфейс не требуется.

## 3. Настроить и запустить

```bash
[ -f .env ] || cp .env.example .env
sudo docker compose config --quiet
sudo docker compose up -d --build --wait
sudo docker compose ps
curl -fsS http://127.0.0.1:8080/api/health
```

Дождитесь завершения первой сборки. Должны работать оба сервиса `api` и `worker`; API возвращает `"status":"ok"` и `"worker_online":true`. Если обработчик ещё запускается, повторите запрос через несколько секунд. В браузере **на этой Ubuntu** откройте [http://localhost:8080](http://localhost:8080).

Для изменения конфигурации используйте `nano .env`, затем повторите `sudo docker compose up -d --build --wait`.

| Настройка | По умолчанию | Что меняет |
| --- | --- | --- |
| `PORT` | `8080` | Локальный порт сайта; при `8081` открывайте `http://localhost:8081` |
| `MAX_FILE_BYTES` | `536870912` | До 512 МиБ на файл |
| `MAX_STORAGE_BYTES` | `5368709120` | До 5 ГиБ медиа в хранилище |
| `RESULT_TTL_SECONDS` | `86400` | Хранение файлов 24 часа |
| `JOB_TIMEOUT_SECONDS` | `1800` | До 30 минут на одно задание |

Settings показывает значения сервера; редактируются они в `.env`. Для обычного запуска ключи API не нужны. Доступность публикации зависит от источника. Сервис по умолчанию слушает только `127.0.0.1`.

## 4. Ubuntu в VMware или на сервере

Чтобы открыть сайт с основного компьютера, подготовьте SSH **в Ubuntu**, если он ещё не работает:

```bash
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
whoami
hostname -I
```

В PowerShell или терминале **основного ПК** подставьте имя пользователя и доступный IP Ubuntu:

```text
ssh -N -L 18080:127.0.0.1:8080 USER@IP_UBUNTU
```

Оставьте этот терминал открытым и перейдите на [http://localhost:18080](http://localhost:18080). Для туннеля нужен сетевой доступ к SSH Ubuntu. Если `PORT` изменён, замените последний `8080` в команде. `localhost` основного ПК и `localhost` VM - разные машины; прямой вход на IP VM по порту 8080 при стандартной конфигурации не работает.

## 5. Пользоваться платформой

Справа сверху выберите **English / Українська**. Язык сохраняется в этом браузере.

| Раздел | Действие |
| --- | --- |
| **Download / Завантаження** | Вставьте ссылку на одну публичную публикацию YouTube, TikTok, Instagram, Pinterest или трек SoundCloud. Нажмите **Analyze link / Аналізувати посилання**, выберите формат, качество или фото и добавьте в очередь. Несколько выбранных элементов также доступны в ZIP. |
| **Tasks / Завдання** | Дождитесь **Completed / Завершено**, скачайте и откройте файл. Здесь доступны отмена, повтор, срок хранения и конвертация сохранённого результата. |
| **Convert / Конвертація** | Загрузите один локальный файл, дождитесь проверки, выберите преобразование, битрейт или параметры GIF и добавьте задание в очередь. Например: видео со звуком в MP3, PNG в WebP, видео в короткий GIF. |
| **Settings / Налаштування** | Проверьте состояние обработчика, версии инструментов, лимиты и место в хранилище. |

Начните с короткого ролика и небольшого изображения. У видео проверьте изображение и звук; у GIF - движение; у ZIP - состав файлов. MP3 доступен только при наличии аудиодорожки. Повышение битрейта не восстанавливает потерянное качество. Пакетная загрузка, профили/каналы и плейлисты пока не поддерживаются.

## 6. Обновление и остановка

В папке проекта выполните **в таком порядке**:

```bash
git fetch origin
git switch main
git pull --ff-only
sudo docker compose up -d --build --wait
```

Нажмите **Ctrl+F5** и повторите анализ ссылки, если обновление касалось источников. При локальных изменениях сначала сохраните их; `reset --hard` для обычного обновления не нужен.

По необходимости:

```bash
sudo docker compose stop
sudo docker compose up -d --wait
sudo docker compose logs --tail 80 api worker
```

Первая команда останавливает, вторая запускает, третья показывает логи. История и файлы хранятся в постоянном Docker-томе. `docker compose down` сохраняет том, а **`docker compose down -v` удаляет данные**.

## 7. Если не запускается

| Симптом | Что сделать |
| --- | --- |
| `permission denied` при обращении к Docker | Выполнять команды Docker с `sudo`, как в инструкции |
| `Cannot connect to the Docker daemon` | Проверить `sudo systemctl status docker`; запустить через `sudo systemctl start docker` |
| `no configuration file provided` | Перейти в корень репозитория с `compose.yaml`; сначала обновить Git |
| Порт занят | Задать свободный `PORT` в `.env`, пересоздать сервисы и использовать новый адрес |
| Задания стоят в очереди | Проверить `worker_online`, сервис `worker` и логи |
| С основного ПК сайт не открывается | Проверить SSH-туннель и открыть `localhost:18080` на основном ПК |
| Интерфейс устарел | Дождаться успешной сборки, затем Ctrl+F5 |

Для разбора ошибки сохраните её текст, `sudo docker compose ps` и последние логи. [Репозиторий](https://github.com/Denofix/youtube-downloader) · [Матрица конвертера](../media-service/converter-matrix.md) · [Эксплуатация и резервные копии](../media-service/operations.md).
