# Implemented support and remaining gates

This is the first web-service slice, not completion of the full specification. Source support must be distinguished from a successful live download. The complete five-platform target is preserved in specification.md.

| Source | Implemented in this build | Controlled verification | Live status |
| --- | --- | --- | --- |
| YouTube individual video / Shorts / finished-live permalink | Metadata, exact-format video/audio, lossless track merging and MP3 extraction | Real yt-dlp against a generated local HTTP media source; exact quality, merge/audio and missing-format rejection pass | Owner confirmed a real 1080p MP4 download/playback and MP3 workflows on 11 November 2026; see owner-verification-2026-11-11.json. The earlier failed development-environment test is retained separately. |
| TikTok | Planned | None | Not tested |
| SoundCloud | Planned | None | Not tested |
| Instagram | Planned | None | Not tested |
| Pinterest | Planned | None | Not tested |
| Channel/playlist, photo carousel, batch uploads, ZIP | Planned | None | Not implemented |

Other target platforms return `platform_planned`. Ongoing streams and collection URLs are rejected. Every new publication type needs an extractor/license review and a recorded live example before it is advertised.

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

The restored backend test suite passed locally with **45 tests**. GitHub Actions also passed desktop/mobile browser scenarios, real MP3 retrieval/GIF/WebP conversion, and Docker Compose build/start. Actual screenshots are captured as artifacts. Controlled CI checks remain distinct from the owner's successful real YouTube test; see verification.md and the separate dated reports. Only the tested live scenario is confirmed.
