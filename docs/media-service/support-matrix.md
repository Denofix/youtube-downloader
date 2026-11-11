# Implemented support and remaining gates

This build includes TikTok photo posts and the first Instagram slice: individual Reels/video posts. Source implementation is distinct from a successful live download. The complete five-platform target is preserved in specification.md.

| Source | Implemented in this build | Controlled verification | Live status |
| --- | --- | --- | --- |
| YouTube individual video / Shorts / finished-live permalink | Metadata, exact-format video/audio, lossless track merging and MP3 extraction | Real yt-dlp against a generated local HTTP media source; exact quality, merge/audio and missing-format rejection pass | Owner confirmed a real 1080p MP4 download/playback and MP3 workflows on 11 November 2026; see owner-verification-2026-11-11.json. The earlier failed development-environment test is retained separately. |
| TikTok individual video | Metadata, exact-format video and MP3 extracted from that video; share links | Real yt-dlp against owned generated local media through API/queue/verification/delivery; photo/live/collection rejection | The owner-supplied link passed MP4/MP3 download in the development environment. Owner confirmed compatible 1080p playback in Windows Media Player on 11 November 2026. Earlier blocked sample is retained; see source-failure-followup.md and live-owner-tiktok-2026-11-11.json. |
| SoundCloud public individual track | Metadata, actual audio formats and bitrate, original/M4A or MP3; share links; preview-only rejection | Real yt-dlp against generated local audio through API/queue/verification/delivery | Passed 11 November 2026: full 143-second track, exact hls_aac_96k → M4A and MP3, verified and retrieved over HTTP. See live-soundcloud-2026-11-11.json. The owner also confirmed a separate public track downloaded and played as M4A. |
| TikTok individual photo post | Cached original JPEG/PNG/WebP, local previews, item selection, individual files, ZIP and image conversion | Real HTTP fixtures, exact bytes/order, cleanup/limits, persisted snapshots; browser photo scenarios | Public single-photo and two-photo carousel passed API/worker/original/ZIP/conversion checks; see stage-3.md. Owner photo recheck pending. |
| Instagram individual Reel / video post | Canonical permalinks, exact-quality original/MP3 delivery, same-source refresh checks; no automatic carousel processing | Real locked yt-dlp against owned HTTP video/audio through API/queue/full verification; access and quality failures | A real 720 × 1280 H.264/AAC Reel passed separate-track merge, MP4 and MP3 delivery; two silent returned video renditions also passed. A separate legacy video required access. See stage-4a.md for recorded cases and remaining owner check. |
| Instagram photo / carousel | Planned next | Explicit photo/carousel rejection | Not implemented |
| Pinterest | Planned | None | Not tested |
| Channel/playlist, batch upload UI, other-platform carousels | Planned | None | Not implemented |

Pinterest returns `platform_planned`; Instagram photo/carousel posts return specific next-stage errors. Ongoing streams and collection URLs are rejected; TikTok photo-post URLs enter the bounded photo workflow. Share links are resolved by the worker with a five-hop limit, exact host/path validation and same-platform redirects. See stage-2.md for extractor review, verified scope and remaining live gate.

| Conversion | Enabled when compatible | Controlled evidence |
| --- | --- | --- |
| MP4 → MP4/WebM/MKV/MOV | Installed H.264/VP9 and required audio encoder | Output streams plus full decoding |
| Video with audio → MP3/M4A/WAV/FLAC/OGG | Source audio stream and installed encoder | Output audio streams plus full decoding |
| Silent video → audio | Rejected | Capability and API rejection test |
| Video → GIF | Bounded start/duration/FPS/width; preview endpoint | Multiple frames, dimensions and decoding |
| PNG → JPG/PNG/WebP | Pillow encoder support | Dimensions, actual format and transparency |
| Animated GIF → MP4 | Installed encoder | Motion retained as video, full decode |
| Other audio/image inputs | Shared content/capability path | Expand individual input-type fixtures next |

Presets expose actual behavior: Original uses exact source streams; Audio MP3 has an explicit bitrate; Smaller Video encodes H.264 CRF 25 or VP9 CRF 34 with no guaranteed size reduction; GIF Clip has a maximum 15 seconds, 24 FPS and 720-pixel width. Increasing bitrate or resolution does not restore detail.

The expanded backend test suite passed locally with **209 cases**. The first-stage GitHub Actions passed desktop/mobile browser scenarios, real MP3 retrieval/GIF/WebP conversion and Docker Compose build/start. The second-stage browser check adds SoundCloud desktop and TikTok mobile forms using explicitly identified metadata fixtures. Actual CI results are recorded in stage-2.md; controlled checks remain separate from live source evidence.

The owner-supplied SoundCloud track was reported DRM-protected by the upstream extractor. It now produces a specific `drm_protected` error. Public unprotected SoundCloud track delivery still passes after installing curl-cffi. See source-failure-followup.md for the distinction and safe in-container diagnostics.

TikTok playback policy: only sources without a reported watermark; compatible H.264/AAC MP4, preserving selected dimensions, with same-post audio when a high-resolution rendition is video-only. See tiktok-playback.md for tests, dynamic source-ID handling and completed owner playback confirmation.

TikTok performance measurements and stage timing semantics are recorded in [tiktok-speed.md](tiktok-speed.md).

Stage 3 uses one queued job per selected photo subset with individual file assets and a ZIP for multiple items. Photo source snapshots are retained and validated locally; selected pending inputs are protected from expiry cleanup. See [stage-3.md](stage-3.md).
