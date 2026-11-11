# Stage 4a — individual Instagram Reels and video posts

Branch: `feat/instagram-video`, stacked on `feat/tiktok-photos` / PR #4 at `8e81b6a7`. The parent photo feature remains available and its owner-instance acceptance is separate. This first Instagram slice implements individual videos; Instagram photo/carousel selection is the next slice. No database migration or runtime dependency change is required.

## Behavior

Full `/reel/shortcode/`, `/reels/shortcode/`, `/p/shortcode/` and legacy `/tv/shortcode/` permalinks use the existing API, persistent queue, locked yt-dlp extractor, server-side cookies, verification and retained assets. Canonicalization removes tracking, uses HTTPS and rejects credentials, extra path segments, unknown subdomains and nonstandard ports. Profiles, Stories, live pages and opaque `/share/` links are rejected with instructions to paste one full video permalink.

Analysis exposes actual source formats, dimensions, FPS, codecs, audio state and size. Original delivery retains the selected streams without re-encoding; separate video/audio streams merge without re-encoding. MP3 uses that video's audio and the selected output bitrate. Silent choices cannot create MP3. The existing API compatible-MP4 profile also remains available for videos with audio; the Instagram UI offers Original and Audio MP3. Original output can retain a source codec that a particular player does not support; the existing Convert workflow provides H.264 MP4 conversion.

Instagram format IDs can change between requests. Delivery binds the selection to the post ID, container, dimensions, reported FPS, video/audio codecs and reported bitrates. A changed ID is accepted only for that same representation. Missing quality or audio fails with a fresh-analysis instruction. A changed post fails before downloading. Final files undergo content inspection and full decoding; a wrong actual resolution fails instead of publishing an apparently successful result.

Instagram carousel results are rejected before processing any children during analysis or delivery. Photo-only posts receive a specific next-stage message. This stage does not flatten a carousel, silently choose its first video, scan a profile or substitute a separate music URL.

The source may require owner-configured cookies or impose an anonymous-access limit. Existing safe error classification distinguishes access requirements, rate limits, unavailable content and protected media. Errors do not expose cookie paths, signed media URLs or upstream stderr.

## Extractor decision

Reviewed the [pinned upstream Instagram extractor](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/extractor/instagram.py) and its individual Reel/video test URLs. The normal public yt-dlp `extract_info(..., process=False)` / `process_ie_result(...)` flow permits checking a single result before download. No private extractor override, dependency update or copied upstream implementation is introduced in production. Test workers override upstream extraction only to serve clearly labelled owned local fixtures, and remain excluded from the production image.

## Verification

The full local suite passes **209 tests**, including 50 Instagram cases: canonicalization, URL boundaries, actual locked yt-dlp/HTTP MP4 and MP3 delivery, separate-track merging, changed format IDs, vanished quality, changed posts, carousel child rejection, silent-video behavior, content/dimension validation, source error redaction and artwork host restrictions. Ruff and frontend formatting/type/build checks pass.

The new browser scenario uses generated owned video through the real API/SQLite/worker/yt-dlp/asset path: actual MP4/MP3 downloads, browser playback with visible pixels, history after refresh, long unbroken titles, desktop/mobile overflow and a private access-error message. The existing TikTok photo browser scenario now additionally checks keyboard selection, reverse tab order, visible focus and long unbroken titles. GitHub Actions runs these alongside existing video/audio checks and the production Docker build/start check. Actual CI outcome is recorded in this stage's PR.

Public checks on 11 November 2026 use the normal API and production worker, without configured cookies:

| Source | Recorded result |
| --- | --- |
| [Reel with audio](live-instagram-audio-2026-11-11.json) | 720 × 1280 H.264/AAC-LC stereo MP4, 13.50 seconds, 3,257,605 bytes; exact separate-track merge, full decoding and HTTP retrieval passed. MP3 at 192 kbps also passed (325,583 bytes). |
| [Silent returned Reel rendition](live-instagram-reel-2026-11-11.json) | Highest returned rendition: 720 × 1280 H.264/yuv420p, 4.97 seconds, 1,949,801 bytes. Download, full decoding and HTTP retrieval passed. The returned rendition has no audio. |
| [Video post](live-instagram-post-2026-11-11.json) | Highest returned rendition: 640 × 640 H.264/yuv420p, 8.74 seconds, 1,017,829 bytes. Download, full decoding and HTTP retrieval passed. The returned rendition has no audio. |
| [Legacy video](live-instagram-access-2026-11-11.json) | Upstream required access; returned `access_required` with no file published. |

The successful samples establish original video and MP3 delivery for those sources, not universal Instagram access. The two silent returned renditions are preserved as additional evidence; MP3 is offered only where audio is available. No public-source video bytes or screenshots are republished. Owner-instance Instagram checks remain pending.

## Update the Windows checkout

```powershell
git fetch origin
git switch feat/instagram-video
docker compose up -d --build
```

Refresh with Ctrl+F5. Paste one public Reel or video-post permalink, choose a returned quality and download. Where an audio source is available, also check MP3. The persistent volume and prior TikTok/SoundCloud/YouTube/photo history are retained. Existing owner cookies can be configured using [operations.md](operations.md); credentials are never pasted into the browser form.

An isolated optional live check is:

```bash
PYTHONPATH=backend uv run --no-sync python scripts/verify_live.py --ephemeral --quality highest --output /tmp/live-instagram.json 'PUBLIC_INSTAGRAM_VIDEO_URL'
```

Use the existing trusted-system-CA setting only if the owner has configured a trusted proxy. Instagram photo/carousel support and Pinterest remain following stages.
