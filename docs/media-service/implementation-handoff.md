> Historical audit/handoff from the interrupted first session. Implementation has since been restored on `feat/media-platform`; see the root README and support matrix for current status. Historical test results below are not substituted for fresh checks.

# Implementation handoff — interrupted before source publication

## Publication boundary

This branch contains **documentation only**. A local implementation was written and tested, but the execution environment became unavailable before `git add`, commit/push and draft implementation PR creation could complete. No web-service source, lockfile, Compose stack or workflow has been published by this documentation change. Main remains the original desktop application.

Do not interpret this report as a claim that the tested code can be checked out from this branch. Availability of the local files cannot be confirmed while that environment is unavailable.

## Local work location

- Repository: Denofix/youtube-downloader.
- Base: `30f0e41abd27c091c71342c19b0f277ca64e7f9d`.
- Local implementation branch: `feat/media-platform` (confirmed absent on remote after the interruption).
- Checkout: `/workspace/scratch/93ce67a800fd/youtube-downloader`.
- Source requirements supplied in the conversation: main functional prompt plus visual/reference addendum; consolidated in the adjacent specification.

## Files prepared locally

- `backend/service/{__init__,config,errors,store,sources,media,runner,worker,api}.py`.
- `frontend/src/{App.vue,Icon.vue,api.ts,main.ts,style.css,tokens.css}`, package/lock, Vite/TypeScript config, index and original SVG favicon.
- `pyproject.toml`, `uv.lock`, UTF-8 runtime `requirements.txt`.
- `Dockerfile`, `compose.yaml`, `.env.example`, `.dockerignore`, gitignore updates.
- Original GUI/source/license retained; original UTF-16 requirements copied to `legacy/requirements-original.txt`; separate desktop runtime/Windows build lists.
- Tests: generated media fixtures, URL/format/download checks, API/queue checks, conversion checks, cancellation/timeout checks, and full API → worker → isolated runner → MP3 delivery.
- Scripts: disposable local instance helper, opt-in live source report, browser smoke/screenshot script.
- CI intended to run backend checks, frontend typecheck/build/formatting, actual browser conversions/screenshots, and a separate Compose build/start check.
- English README and audit/specification/support/operations documents.

## Architecture already exercised locally

The API persists tasks and streams bounded uploads; a separate worker atomically claims one task at a time. Jobs execute in separate process groups. The supervisor enforces wall time/storage and stops the entire group for cancellation. SQLite uses WAL, persisted states, cancellation flags, expiry and safe per-job directories.

The YouTube adapter canonicalizes specific video links, normalizes actual formats and builds exact selectors with no unrestricted fallback. It uses explicit Node runtime/EJS dependencies and optional server-only cookies/system CA trust. Actual output is probed/decoded before publication. FFmpeg/Pillow conversion capabilities are generated on the backend from detected media and installed encoders.

Default model: queued/running/completed/failed/cancelled, separate operations; failed/interrupted work can be retried, downloads retry via fresh analysis, expired files return 410, active conversion inputs are protected during cleanup. Linux advisory lock prevents a second worker on the same volume.

## Checks actually observed before interruption

| Check | Observed result |
| --- | --- |
| Full pytest suite | **44 passed**, one upstream Starlette/httpx deprecation warning, latest run 11.47 seconds |
| Actual-process integration | Generated MP4 uploaded through real API; separate worker/runner produced MP3, API served it, result decoded successfully |
| Controlled real yt-dlp download | Local HTTP media source with controlled extractor metadata; exact selection, merge and MP3 extraction passed |
| Missing selected format | Failed without quality fallback |
| Actual conversions | MP4 → MP4/WebM/MKV/MOV/MP3/M4A/WAV/FLAC/OGG/GIF; PNG → JPG/PNG/WebP; animated GIF → MP4 passed content/stream/decode checks |
| Lifecycle | Cancel, retry/recovery, timeout, expiry, protected inputs, persisted SQLite and isolated files passed |
| Backend lint/format | Ruff passed before the final attempted edit |
| Frontend | Typecheck, Vite build and Prettier format check passed |
| Runtime export | Frozen requirements export compared byte-for-byte successfully using `--no-header` |
| Real YouTube analysis | One public 19-second video returned metadata and 17 formats |
| Real YouTube files | **Not passed**: exact 160/140 media responses were each 195 bytes and failed ffprobe; precise upstream/network cause unknown |
| Browser | **Not verified**: local navigation blocked by installed extension; command environment prevented Chromium Unix socket creation |
| Compose | **Not run locally**: Docker executable absent; workflow prepared for a runner |
| GitHub CI | **Not run for implementation**: code/workflow were never pushed |
| Screenshots | **None delivered**; do not invent or use fabricated UI images |

These results apply to the local implementation observed during this session, not to a hypothetical recreation or the contents of this documentation branch.

## Versions observed

| Component | Version |
| --- | --- |
| Python | 3.12.14 |
| uv | 0.13.6 |
| Node | 24.22.1 |
| yt-dlp | 2026.10.26 |
| yt-dlp-ejs | 0.8.0 |
| Pillow | 13.0.0 |
| FastAPI | 0.162.4 |
| Pydantic | 2.14.3 |
| FFmpeg / ffprobe | 7.1.5 (Debian build) |
| Vue | Resolved in inaccessible local npm lock; do not guess exact patch |
| Vite | 7.3.8 |
| Playwright Python | 1.65.0 |

Current upstream action releases were checked while preparing CI: checkout v7.0.1, setup-python v7.1.0, setup-node v7.1.0, setup-uv v10.3.3, upload-artifact v7.0.2. Recheck them when resuming; no workflow from the unavailable checkout is present here.

## Resume safely

1. Restore the execution environment and inspect the original checkout/status before recreating or overwriting any files. Do not discard uncommitted changes.
2. Confirm original main/license/history remain intact; inspect all prepared files and the final diff.
3. The last attempted patch failed because the exec-server transport closed. It was intended to add frontend formatting to CI and classify FFmpeg's invalid-source-media error more precisely. Do not assume it applied.
4. Resolve any actual source issues, then run the same checks again if edits warrant them:
   - `uv sync --frozen --all-groups`
   - `uv run --no-sync ruff check backend tests scripts`
   - `uv run --no-sync ruff format --check backend tests scripts`
   - `uv run --no-sync pytest -q`
   - `npm --prefix frontend ci`
   - `npm --prefix frontend run format:check`
   - `npm --prefix frontend run build`
5. Export runtime requirements consistently with `uv export --no-header --frozen --no-dev --no-group ui --format requirements-txt --output-file requirements.txt`. The generated header otherwise changes when the output path changes.
6. Commit/push the implementation branch and create a separate draft implementation PR. Run the prepared browser and Compose gates where supported; inspect artifacts and add only real screenshots.
7. Re-run the first live link-to-file scenario from an environment that actually returns media bytes. Do not mark live downloads working based on metadata or tool exit status alone.
8. Expand other sources only after the first download/conversion acceptance gate. Preserve all targets in the specification.
