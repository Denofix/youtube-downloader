# Implemented support and remaining gates

This build includes the second source stage. Source implementation is distinct from a successful live download. The complete five-platform target is preserved in specification.md.

| Source | Implemented in this build | Controlled verification | Live status |
| --- | --- | --- | --- |
| YouTube individual video / Shorts / finished-live permalink | Metadata, exact-format video/audio, lossless track merging and MP3 extraction | Real yt-dlp against a generated local HTTP media source; exact quality, merge/audio and missing-format rejection pass | Owner confirmed a real 1080p MP4 download/playback and MP3 workflows on 11 November 2026; see owner-verification-2026-11-11.json. The earlier failed development-environment test is retained separately. |
| TikTok individual video | Metadata, exact-format video and MP3 extracted from that video; share links | Real yt-dlp against owned generated local media through API/queue/verification/delivery; photo/live/collection rejection | Live metadata blocked by the source for the development server's IP (`network_blocked`); owner-instance verification pending. See live-tiktok-2026-11-11.json. |
| SoundCloud public individual track | Metadata, actual audio formats and bitrate, original/M4A or MP3; share links; preview-only rejection | Real yt-dlp against generated local audio through API/queue/verification/delivery | Passed 11 November 2026: full 143-second track, exact hls_aac_96k → M4A and MP3, verified and retrieved over HTTP. See live-soundcloud-2026-11-11.json. |
| Instagram | Planned | None | Not tested |
| Pinterest | Planned | None | Not tested |
| Channel/playlist, photo carousel, batch uploads, ZIP | Planned | None | Not implemented |

Instagram/Pinterest return `platform_planned`. Ongoing streams and collection URLs are rejected; TikTok photos return `photo_planned`. Share links are resolved by the worker with a five-hop limit, exact host/path validation and same-platform redirects. See stage-2.md for extractor review, verified scope and remaining live gate.

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

The expanded backend test suite passed locally with **103 cases**. The first-stage GitHub Actions passed desktop/mobile browser scenarios, real MP3 retrieval/GIF/WebP conversion and Docker Compose build/start. The second-stage browser check adds SoundCloud desktop and TikTok mobile forms using explicitly identified metadata fixtures. Actual CI results are recorded in stage-2.md; controlled checks remain separate from live source evidence.
