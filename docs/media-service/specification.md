> Historical audit/handoff from the interrupted first session. Implementation has since been restored on `feat/media-platform`; see the root README and support matrix for current status. Historical test results below are not substituted for fresh checks.

# Download & Convert — consolidated specification

Combined functional and visual requirements, 11 November 2026. This is the complete target, not a claim that this documentation branch implements it. Preserve Git history, Nord_Fillin attribution and the existing MIT license. Code, UI and README are English; collaboration with the owner is Russian.

## Architecture

- Python 3.12+, FastAPI, Pydantic.
- Vue 3, TypeScript, Vite, Composition API.
- yt-dlp with yt-dlp-ejs and a supported explicitly enabled JS runtime.
- Evaluate gallery-dl or another suitable open-source extractor for photos/carousels.
- FFmpeg/ffprobe for audiovisual media; Pillow for images.
- SQLite for persisted task/asset metadata; a private persistent data directory.
- Separate Linux worker; one job at a time initially. SQLite transactions are sufficient without Redis or another broker.
- A separate process group per job for cancellation of yt-dlp, FFmpeg and children. Do not run extraction/encoding in HTTP handlers or the API event loop.
- Docker Compose with separate API and worker services, a persistent local volume and a shared image. The API may serve the compiled frontend.
- pytest, frontend typecheck/build/formatting, browser smoke checks and GitHub Actions.
- Business logic is ordinary code; AI assists development.

Start with local, single-owner/self-hosted use. Public hosting is a later milestone with authentication, file ownership, resource/network isolation and abuse controls.

## Download workflow

Paste link → analyze → metadata/actual available formats → choose item, quality and output → enqueue → follow operation → retrieve a verified result.

Normalize source ID, canonical URL, platform, title, author, thumbnail, type, duration/item count and format choices. Preserve source-specific details when useful. Show actual resolution, FPS, codecs, container, audio presence and exact/approximate/unknown size.

Distinguish direct download, merging tracks, audio extraction and re-encoding. Bind choices to stored analysis and revalidate at execution; if a format disappears, request fresh analysis rather than silently choosing another quality. MP3 output bitrate is separate from source characteristics. Offer Original/Best available only where meaningful.

For multi-file posts, show previews, item count and selection; create separate tasks and offer convenient result delivery such as ZIP. First support individual videos/tracks/pins/posts. Channels/profiles and mass crawling follow later.

Owner cookie jars are configured only through server environment/mounts. Keep credentials, signed media URLs and raw tool output out of frontend, Git and user-visible diagnostics. Explain unavailable, unsupported, authorization and region failures accurately.

## Platform target and verification

| Platform | Initial individual links | Video | Audio | Photos / animation | Multi-file | Quality and access | Extractor / current status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| YouTube | watch, youtu.be, Shorts, finished-live permalink | Target | Source audio and extraction | Photos not targeted; downstream GIF conversion | Playlists/channels later | Actual formats; public first, owner cookies when authorized/needed | yt-dlp + ejs + runtime; local controlled core passed, real metadata passed, real file downloading not passed |
| TikTok | Video/photo post | Target | When a stream exists | Evaluate by publication | Planned selection | Actual variants; source-dependent access | yt-dlp video; evaluate gallery-dl photos; not implemented on this branch or live-tested |
| SoundCloud | One track | Outside initial scope | Target | Cover art only if separately added | Collections later | Actual streams; restricted tracks may need access | yt-dlp; not implemented or live-tested |
| Instagram | One reel/post | Target | Derived from available stream | Photos target; animation source-dependent | Carousel selection | Actual variants; login/rate/region limits can apply | yt-dlp video; evaluate gallery-dl photos; not implemented or live-tested |
| Pinterest | One pin / safely resolved pin.it URL | Target | Only when present | Image/GIF/video pin by actual content | Evaluate pin contents | Original/actual variants; source-dependent access | Evaluate gallery-dl/yt-dlp per type; not implemented or live-tested |

Recheck [yt-dlp's extractor list](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) and [gallery-dl's site list](https://github.com/mikf/gallery-dl/blob/master/docs/supportedsites.md). An upstream listing never guarantees that every publication type works.

## Conversion workflow

Accept an uploaded file or a retained download result. Detect actual contents/streams with ffprobe or an appropriate decoder, not a filename. The backend owns compatible operations, installed-encoder detection, parameters, restrictions and transcoding semantics; frontend renders the capabilities API.

| Input | Output target |
| --- | --- |
| Video | MP4, WebM, MKV, MOV |
| Video with audio | MP3, M4A/AAC, WAV, FLAC, OGG |
| Audio | MP3, M4A/AAC, WAV, FLAC, OGG |
| Image | JPG, PNG, WebP |
| Video fragment | GIF |
| Animation | GIF → MP4/WebM; preserve animation or explicitly label still-frame extraction |

GIF controls: start, duration, FPS, width and result preview. Initial defaults: 5 seconds, 12 FPS, 480 pixels; limits: 15 seconds, 24 FPS, 720 pixels. Keep image proportions/orientation, explain transparency loss and use an explicit white JPEG matte. Never claim that increasing bitrate/resolution restores lost detail.

Inspect output streams and fully decode media before publishing a completed result. Reuse already saved files while available. First complete one file end-to-end, then extend the same queue to multiple uploads.

| Preset | Behavior |
| --- | --- |
| Original | Exact appropriate source variant, merge only as needed |
| Audio MP3 | Explicit 128/192/320 kbps encoding |
| Smaller Video | Defined H.264/VP9 profile; no guaranteed size reduction |
| GIF Clip | Explicit bounded start/duration/FPS/width |

Expose each preset's parameters. Backend-sanitize names and include source title/output characteristics; isolate physical files by generated IDs.

## Task lifecycle and storage

States: `queued`, `running`, `completed`, `failed`, `cancelled`. Operations are independent: analyzing, inspecting, downloading, merging, converting, verifying, preparing.

Show title/file, source/parameters, current operation, reported progress and trustworthy speed/ETA. Unknown percentages use indeterminate activity. Download-stage completion does not mean processed output is ready.

Provide cancellation, retry, file download, details and conversion of retained results. Reload fetches persisted tasks. Queued tasks survive restart; interrupted tasks become failed/cancelled with explicit retry. A download retry refreshes analysis. A single-worker advisory lock prevents conflicting recovery.

Initial limits: one processing job, 50 active tasks, 512 MiB per file, 5 GiB media storage, 30 minutes per task, two-hour media duration, 24 MP images, 500 animation frames. Docker bounds CPU, actual memory and process count. Keep uploads/results for 24 hours and show expiry; expired access returns HTTP 410. Protect inputs used by queued/running conversions, clean partial outputs and stale unregistered uploads. History metadata is separate from file retention; initially list the newest 200 tasks.

Use controlled argv without shell interpolation, validated URLs/IDs/paths/uploads and server-owned encoding fields. Restrict decoder network protocols for uploaded content, use private per-job directories, loopback defaults, trusted Host checks and same-origin mutations. Do not expose arbitrary tool arguments.

## Visual direction and interaction

Navigation: Download, Convert, Tasks (active count), Settings (owner-set limits/runtime diagnostics). Compact top navigation and limited content width on desktop; vertical sequence on mobile.

Start Download with one URL field and analysis action. Start Convert with drop zone and an accessible file picker. Increase information density after analysis. Provide initial/loading/empty/success/access-required/unsupported/expired/server-error states with an actionable next step. Use text/icons together with state colors and keep rare parameters under Advanced.

| Token | Value |
| --- | --- |
| Page | `#0D1015` |
| Card | `#151A23` |
| Secondary surface | `#1D2530` |
| Borders | `#2D3746` |
| Main text | `#F4F6FA` |
| Secondary text | `#A8B3C4` |
| Accent | `#F97316` |
| Accent hover | `#FB923C` |

Dark text on orange fills. Moderate rounding, clear hierarchy, consistent spacing, readable typography, visible focus, explicit labels, keyboard navigation, a skip link, readable long titles, short transitions and reduced-motion support. Dark theme first; light theme later.

## References reviewed

Current README documentation from all six projects and VERT's landing page were reviewed on 11 November 2026. This does not imply interactive testing of every reference. Implement original components; review licenses before any code/asset transplant.

| Reference | Documented upstream feature | Our use |
| --- | --- | --- |
| [VERT](https://vert.sh), [source](https://github.com/VERT-sh/VERT) | Prominent drop/click converter, settings, WebAssembly/device processing | Simplicity/space with our own orange identity; our processing is server-side |
| [MeTube](https://github.com/alexta69/metube) | Queue, concurrency, saved state, per-download options | Active/history organization on our task model |
| [yt-dlp-web-ui](https://github.com/marcopiovanello/yt-dlp-web-ui) | Optional format selection/audio extraction | Actual format choices and controlled advanced fields |
| [ConvertX](https://github.com/C4illin/ConvertX) | Multiple converters, format lists, expiry settings | Capability-driven inspection/conversion |
| [Parabolic](https://github.com/NickvisionApps/Parabolic) | Multiple outputs, metadata, concurrent downloads | Compact metadata/task presentation |
| [Pinchflat](https://github.com/kieraneglin/pinchflat) | Presets, naming, periodic channel discovery | Presets/naming first; subscriptions/library later |

Add References & Inspiration to the implementation README. Keep original copyright/license and separate dependency licenses, including the actual distributed FFmpeg build.

## Staged delivery and acceptance

1. Audit: inspect current code, reproduce deterministic defects, separate hypotheses/environment limitations, combine requirements.
2. YouTube core: actual format IDs, correct quality, merging/audio extraction, current runtime dependencies. Complete one real link-to-file scenario first.
3. Web slice: Vue UI, API and persisted worker; complete upload → inspect → MP3 → retrieve, cancellation/retry/recovery, refresh persistence.
4. Other sources: add one platform/publication type at a time, photos/carousels, item selection and convenient delivery.
5. Converter: expand all compatible input/output profiles, GIF controls/preview, animation and image semantics.
6. Packaging: Compose/volumes, locked dependencies, .env.example, CI, English README, support matrix, diagnostics/update/backup instructions and screenshots of the actual running UI.

The first local slice covered much of stages 2/3/5 before the environment interruption. It is not in this branch; see the handoff for exact evidence and blockers.

After those gates: batch uploads, light theme, preset customization, channel/profile crawling, subscriptions, scheduled scanning, a media library and public multi-user hosting.

## Verification

Deterministic tests use generated/owned small fixtures and controlled extractor replies. Cover URL/parameter validation, metadata/options, selected quality, lifecycle/cancellation/cleanup, tool errors, actual conversion/content/full decoding, SQLite persistence and directory isolation.

Live tests are separate opt-in cases. Record date, tool versions, publication type, selected source formats, operation, result and limitations. Required matrix: short YouTube video/quality/audio; TikTok video/photo; SoundCloud track; Instagram video/photo; Pinterest image/video; MP4 → MP3/GIF, JPG/PNG/WebP, GIF → MP4.

Check desktop/mobile widths, keyboard/focus, long titles, empty/error/expired states, cancellation/retry and reload recovery. Take screenshots of the real UI, never fabricated success states. Extractor updates use the lockfile plus controlled and relevant live regression checks.
