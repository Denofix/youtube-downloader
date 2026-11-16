# Operations and verification

## Run

Use Docker Compose from the repository root: `docker compose up --build -d --wait`, then open http://localhost:8080. Both API and worker are required. Health checks verify the API/SQLite; Settings and the header additionally report worker heartbeat. A worker outage leaves tasks queued.

The named local volume `media-data` contains SQLite and generated file directories. This implementation uses SQLite WAL and a Linux worker lock: use one worker and a local filesystem, not a multi-host/network share. The default listener is loopback for a single owner. Windows can run Docker Desktop or use a Linux VM. In a VM, localhost refers to that VM; use its browser or an SSH port forward when viewing from the host.

## Interface language

Use the language selector in the top-right header to choose **English** or **Українська**. English is the default. The selection is stored per browser under `download-convert.language` and restored after reload. When storage is disabled, switching still works for the open page. An unsupported saved value falls back to English.

All four pages, accessible labels, task states, conversion choices, supported error messages, settings descriptions, counters, dates and units follow the selection. Switching does not submit a form, reload the page, clear a selection or modify server tasks. Original media titles, author names, filenames, platform names, codec IDs and technical error codes retain their original values. The API, CLI diagnostics and logs remain in English.

## Limits, expiry and restart

Defaults are one running job, 50 active jobs, 512 MiB per file, 5 GiB media storage, 30-minute job timeout, two-hour media duration, 24 megapixels per image and 500 animation frames. The container also limits CPU, actual memory and process count. Change owner environment values in `.env` and recreate the services. These are guardrails for a private instance; public multi-user deployment is a separate milestone.

Queued jobs survive restart. Previously running jobs become failed/cancelled with a retry action and their partial outputs are removed. Normal shutdown terminates the active process group, including FFmpeg. The single-worker lock prevents duplicate recovery.

Files expire after 24 hours by default. Expired access returns 410; active/queued conversion inputs are protected from physical cleanup. A conversion retry needs an unexpired input. A download retry refreshes analysis instead of silently reusing obsolete format IDs. History metadata is retained separately and the API lists the latest 200 tasks.

Stop both services before backing up the entire data volume, including SQLite and files. Do not copy only a live SQLite main file while its WAL is active. Restore with UID/GID 10001 access. `docker compose down` keeps the volume; `down -v` deletes it.

## Owner cookies and certificate trust

Create a dedicated Netscape-format jar outside the repository. Protect it and allow the worker's UID 10001 to read/write the dedicated copy; yt-dlp may update it. Do not mount an irreplaceable browser profile. Example ignored `compose.override.yaml`:

```yaml
services:
  worker:
    volumes:
      - /absolute/private/youtube-cookies.txt:/run/secrets/youtube-cookies.txt
```

Set `COOKIE_FILE=/run/secrets/youtube-cookies.txt` in `.env`, restart, and analyze again. No cookie upload UI, raw stderr, cookie path/content or signed media URL is exposed by the API. Cookies do not guarantee source access.

When a trusted owner-controlled proxy CA is installed in the system trust store, `YTDLP_USE_SYSTEM_CA=1` selects system certificates instead of certifi. Containers need that CA installed too. TLS verification remains enabled. Do not disable certificate validation.

## Tests

```bash
uv sync --frozen --all-groups
uv run --no-sync ruff check backend tests scripts
uv run --no-sync ruff format --check backend tests scripts
uv run --no-sync pytest -q
npm --prefix frontend ci
npm --prefix frontend run format:check
npm --prefix frontend test
npm --prefix frontend run build
uv run --no-sync playwright install --with-deps chromium
uv run --no-sync python scripts/check_ui.py
uv run --no-sync python scripts/check_localization_ui.py
```

The browser test starts a disposable API/worker, generates tiny local media and exercises desktop/mobile overflow, keyboard focus, errors, uploading, MP3 download, GIF preview, WebP conversion and history after reload. It writes real screenshots to `.ui-artifacts`; CI uploads them. `--chromium /path/to/chromium` selects an installed browser. The environment must allow browser IPC and local navigation.

The localization suite uses owned Pinterest fixtures in a separate disposable instance. It checks all four Ukrainian pages, language persistence, keyboard selection, preserved photo/format/bitrate choices, actual JPEG download and PNG conversion, immediate API errors and stored task errors, blocked storage, unsupported preferences and widths from 320 to 1440 pixels. No live platform access or owner data is required. The frontend unit suite checks interpolation parameters, Ukrainian plural forms, language persistence and translated capability/error labels.

Opt-in live test:

```bash
uv run --no-sync python scripts/verify_live.py \
  'https://www.youtube.com/watch?v=VIDEO_ID_HERE' \
  --ephemeral --output /tmp/live-report.json
```

Choose an appropriate public short source. The report records UTC date, versions, selected formats and validated results/errors. Ephemeral mode deletes only its own temporary instance. Alternatively, `--base http://localhost:8080` creates visible tasks on an existing instance. Offline CI does not require external platform access.

## Updates

Create a branch and record current diagnostics. Update intentionally with `uv lock --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs`, then sync and run controlled tests. Regenerate `requirements.txt` using `uv export --no-header --frozen --no-dev --no-group ui --format requirements-txt --output-file requirements.txt`; `--no-header` keeps the export independent of output path. Re-run relevant opt-in live cases and update the matrix.

Build a new image, gracefully stop processing, back up the volume and restart. Roll back to the prior image/commit if verification fails; do not mutate dependencies in running containers. Python and npm are locked. Major base-image tags and OS packages can change on rebuild, so images are not claimed byte-identical; release promotion can pin verified image digests.
