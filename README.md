# Download & Convert

A self-hosted media workspace evolving from Nord_Fillin's YouTube Downloader. Vue 3 + TypeScript, FastAPI, a separate worker, yt-dlp, FFmpeg, Pillow and a persistent SQLite queue.

Analyze an individual YouTube/TikTok/Instagram video, a TikTok/Instagram photo post or carousel, a public SoundCloud track, or a Pinterest image/GIF/video pin. Select actual source formats or photos and queue a verified download. Upload media, inspect contents, convert files and retrieve verified results. The complete five-platform target remains in the [specification](docs/media-service/specification.md).

**Verification:** 309 backend/media/process cases pass locally. [Compatible TikTok playback verification](docs/media-service/tiktok-playback.md) passed all four offered source renditions for the supplied post, including 1080 × 1920 H.265 → H.264/AAC MP4, plus MP3 and full decoding/HTTP retrieval. The owner confirmed compatible TikTok playback in Windows Media Player and a public SoundCloud M4A download/playback on 11 November 2026. An unprotected SoundCloud control track passes M4A/MP3 delivery; the supplied remix returns DRM protection. The [source failure follow-up](docs/media-service/source-failure-followup.md), [YouTube owner verification](docs/media-service/owner-verification-2026-11-11.json) and earlier [CI evidence](docs/media-service/stage-2.md) are retained separately. TikTok [photo-post verification](docs/media-service/stage-3.md) adds a real single image and two-image carousel, original bytes, ZIP and PNG conversion; the owner has also confirmed photo/ZIP delivery. Only recorded scenarios are confirmed.

Instagram [stage 4a](docs/media-service/stage-4a.md) passed a real 720 × 1280 H.264/AAC Reel download and MP3 delivery, plus two silent video samples. The owner confirmed Reel download/playback. [Stage 4b](docs/media-service/stage-4b.md) adds Instagram photos and selected carousel items, including videos, with real photo and video-carousel reports. Its [implementation CI](https://github.com/Denofix/youtube-downloader/actions/runs/43139081555) passed 256 tests, all four browser suites and Docker Compose; focused desktop/mobile and gallery screenshots were visually reviewed. The owner has now confirmed Instagram photos, a selected photo-carousel subset, video with audio and retained video-to-MP3 delivery. Access varies by publication.

Pinterest [stage 5](docs/media-service/stage-5.md) adds individual image/GIF/video pins and bounded pin.it redirects. Live checks passed an unchanged JPEG, animated GIF and GIF → MP4, a short link, all six offered video formats up to 1080 × 1920, and MP3. Pinterest owner testing and current browser/Docker results are tracked separately in the stage report.

## Start

```bash
git clone --branch feat/pinterest https://github.com/Denofix/youtube-downloader.git download-convert
cd download-convert
cp .env.example .env
docker compose up --build -d --wait
```

Open **http://localhost:8080**. Both API and worker must run. The named `media-data` volume keeps files and SQLite state. The default listener is loopback for a private owner-operated instance. Public hosting is a separate milestone. On Windows use Docker Desktop; in a Linux VM, view localhost from that VM or use an SSH port forward from the host.

## Screenshots

Actual running interface, captured by the [browser integration run](https://github.com/Denofix/youtube-downloader/actions/runs/42974101607). Conversion/history examples use generated local test media.

![Download workspace](docs/screenshots/download-desktop.png)

<details>
<summary>Conversion, history and mobile layouts</summary>

![Conversion workspace](docs/screenshots/convert-desktop.png)

![Task history](docs/screenshots/tasks-desktop.png)

| Mobile download                                          | Mobile tasks                                       |
| -------------------------------------------------------- | -------------------------------------------------- |
| ![Mobile download](docs/screenshots/download-mobile.png) | ![Mobile tasks](docs/screenshots/tasks-mobile.png) |

</details>

## Current features

TikTok video delivery now uses **compatible H.264/AAC MP4** at the selected dimensions and excludes reported watermarked sources. HEVC is converted when needed; see the [playback fix and verified scope](docs/media-service/tiktok-playback.md). [Speed follow-up](docs/media-service/tiktok-speed.md) removes redundant source requests/input decoding, uses the `veryfast` CRF 18 preset and displays task-stage timings.

- Download real source format IDs with resolution/FPS/codecs/audio/size details, track merging and explicit MP3 encoding. Missing formats require fresh analysis; no silent quality fallback.
- Accept public SoundCloud track permalinks and TikTok video permalinks, plus bounded same-platform share redirects. SoundCloud previews are rejected; TikTok MP3 comes from the selected video, not a separate potentially different music track.
- Accept full Instagram Reel/video-post permalinks through the same queue, exact-quality selection and MP3 workflow. Instagram photos and carousels use the item-selection workflow; Stories, profiles and opaque share URLs remain outside the supported scope. See [stage 4a](docs/media-service/stage-4a.md) for live evidence and access limits.
- Select individual Instagram carousel photos/videos, set each video format or MP3, retrieve originals and a flat source-ordered ZIP, and reuse retained files in the converter. The link input has one focus indicator around the icon and complete field.
- Analyze TikTok photo posts, preview and select images, retrieve separate originals plus a source-ordered ZIP, and convert retained photos. Originals/previews are cached during analysis; the selected delivery reuses the verified snapshot.
- Accept one Pinterest image, GIF or video pin, including bounded pin.it redirects. Preserve actual GIF frames and source bytes, use real video choices and MP3, and convert retained results. Progressive video audio is labelled unknown when the source does not report it. Multi-page pins, boards and external players are outside this stage.
- Convert compatible MP4/WebM/MKV/MOV, MP3/M4A/WAV/FLAC/OGG, GIF clips, JPG/PNG/WebP and animated GIF to video. Options depend on detected contents and installed encoders.
- Persist queued/running/completed/failed/cancelled tasks, separate operations and real per-operation progress. Cancel, retry, recover after restart, reuse a result and show file expiry.
- Default limits: one processing job, 512 MiB per file, 5 GiB media storage, 30 minutes per task, 24-hour results. Configure owner values in `.env`.
- Graphite/orange Download, Convert, Tasks and Settings pages, keyboard focus/labels, mobile layout and worker diagnostics.

Batch upload UI is planned. Pinterest single-pin delivery is implemented in [stage 5](docs/media-service/stage-5.md). Instagram post selection is implemented in [stage 4b](docs/media-service/stage-4b.md), following [stage 4a](docs/media-service/stage-4a.md); TikTok photo selection and ZIP delivery are implemented in [stage 3](docs/media-service/stage-3.md). The original desktop source, assets, copyright and license remain available; [legacy notes](legacy/README.md) explain the separate dependency lists.

## Architecture

The browser uses the same-origin API. FastAPI streams bounded uploads and persists tasks in SQLite. A separate Linux worker atomically claims one task and runs it in a killable process group. Source/media adapters normalize formats or inspect contents. Only verified results become opaque asset IDs in generated private directories. API and worker share a persistent local volume; no external queue broker is required.

| Path                         | Purpose                                                                 |
| ---------------------------- | ----------------------------------------------------------------------- |
| `backend/service/api.py`     | Validated API, diagnostics and compiled frontend                        |
| `backend/service/worker.py`  | Claims, process supervision, cancellation, limits and heartbeat         |
| `backend/service/runner.py`  | Isolated task execution                                                 |
| `backend/service/sources.py` | URL validation, metadata normalization and exact selection              |
| `backend/service/media.py`   | Content inspection, capabilities, conversion and full decoding          |
| `backend/service/store.py`   | SQLite tasks/assets, recovery, retention and cleanup                    |
| `frontend/`                  | Vue 3 / TypeScript / Vite                                               |
| `tests/`, `scripts/`         | Generated fixtures, process/browser checks and opt-in live verification |

## Native Linux development

Install Python 3.12+, uv 0.13.6, Node 24 and FFmpeg/ffprobe. From the repository root:

```bash
uv sync --frozen --all-groups
npm --prefix frontend ci
npm --prefix frontend run build
PYTHONPATH=backend uv run --no-sync uvicorn service.api:app --host 127.0.0.1 --port 8000
```

In another terminal in the same directory:

```bash
PYTHONPATH=backend uv run --no-sync python -m service.worker
```

Open http://localhost:8000. For hot reload, `npm --prefix frontend run dev` proxies `/api` to port 8000. The source-of-truth dependency files are `uv.lock` and `frontend/package-lock.json`; root requirements.txt is a UTF-8 frozen runtime export.

## Verification and operations

```bash
uv run --no-sync ruff check backend tests scripts
uv run --no-sync ruff format --check backend tests scripts
uv run --no-sync pytest -q
npm --prefix frontend run format:check
npm --prefix frontend run build
```

[Operations](docs/media-service/operations.md) covers real browser screenshots, opt-in live tests, owner cookies, trusted certificates, updates, backup and recovery. CI runs the controlled suite and builds the container stack; review actual run results rather than treating the workflow file itself as a pass.

The first owner-tested download/conversion and browser/Compose gates are confirmed. Next, expand publication types and sources one at a time. Light theme, batch uploads, subscriptions, channel/profile scanning, media library and public multi-user hosting remain later stages.

## References & Inspiration

[VERT](https://vert.sh/) ([source](https://github.com/VERT-sh/VERT)) — visual clarity and upload area; [MeTube](https://github.com/alexta69/metube) — queue organization; [yt-dlp-web-ui](https://github.com/marcopiovanello/yt-dlp-web-ui) — format selection; [ConvertX](https://github.com/C4illin/ConvertX) — conversion flow; [Parabolic](https://github.com/NickvisionApps/Parabolic) — compact metadata/tasks; [Pinchflat](https://github.com/kieraneglin/pinchflat) — presets and naming.

These are product/design references, not copied source/assets. Unlike VERT's on-device processing, this service processes files on the owner's server.

## Author and license

Created by **Nord_Fillin**. The original [MIT license](LICENSE), attribution and Git history are preserved. Dependency licenses apply separately, including yt-dlp/ejs, Vue, FastAPI, Pillow and the particular FFmpeg build/codecs supplied by the base OS. No reference application's code or visual assets were imported.
