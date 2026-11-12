# Stage 5 — Pinterest individual image, GIF and video pins

Branch: `feat/pinterest`, based on `feat/instagram-gallery` at `3b497f8b`. No schema migration or runtime dependency change is needed. Instagram owner acceptance is recorded in [owner-acceptance-2026-11-12.json](owner-acceptance-2026-11-12.json): photos, a photo-carousel subset, video with audio and retained video-to-MP3 delivery.

## Behavior and boundaries

One public Pinterest pin can return an original image, an animated GIF or native video streams. Full and localized pin permalinks are canonicalized to one numeric pin ID. Tracking data is removed. `pin.it` links are resolved in the worker with the existing five-hop bound; Pinterest's observed `api.pinterest.com/url_shortener/TOKEN/redirect/` hop is permitted only on HTTPS with its exact path and no query, credentials or arbitrary API endpoint. Each final target is checked before a request. A `/sent/` share permalink resolves to the same pin.

The adapter reuses the locked [yt-dlp Pinterest extractor](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/extractor/pinterest.py), its native Pin API, authentication/transport and native video/manifest parser. This private API is a tested upgrade boundary. Upstream [gallery-dl test URLs](https://github.com/mikf/gallery-dl/blob/master/test/results/pinterest.py) helped locate public examples; no gallery-dl implementation or dependency is copied.

For images, the offered `orig` candidate is used, or the largest candidate with reported dimensions when `orig` is absent. No larger CDN path is invented. Actual bytes are fully decoded and checked against reported dimensions, retained with a SHA-256 fingerprint, previewed locally and delivered unchanged. Actual image type and dimensions determine the output. A declared GIF must return GIF content rather than a still cover. Its original frames remain intact; the existing converter can turn a retained GIF into MP4. Native GIF embeds are limited to Pinterest's own CDN.

Native video formats reuse the existing resolution/codec/FPS/bitrate identity matching and full output verification. Format IDs are identifiers, not quality labels: a rendition named `V_720P` in the live example actually reports and delivers 1080 × 1920. Unreported progressive codecs/audio remain `unknown` in the UI. Original delivery keeps actual available streams; MP3 requires audio in the file. Missing declared audio still fails verification. A format with unknown codec cannot be substituted under a changed ID without a new analysis.

Boards, profiles, searches, multi-page/multi-media pins, separate story audio layers and external players are outside this stage. A video whose streams disappear fails rather than returning its image cover. The supported native image/video URLs are restricted to HTTPS Pinterest CDN hosts. Signed source addresses and cookie paths are not exposed in public task results or reports.

Limits reuse existing settings: one queued task, 512 MiB per result by default, bounded storage/retention/time, 16 MiB and 24 megapixels per image, and up to 500 GIF frames. Each selected image/GIF remains protected for pending delivery; retained conversion, cancellation, retry and restart use the existing queue. Existing TikTok and Instagram photo rules continue to reject animations.

## Verification

**309 local tests pass**, including 53 Pinterest cases for native image/GIF/video and one-page video metadata, exact original bytes, local previews, GIF frame limits/cover rejection, retained conversion, MP3, silent video, changed identity/quality/format, strict share hops and private diagnostic redaction. Existing source, queue, process, photo/gallery and conversion tests also pass. Ruff, frontend formatting, TypeScript and production build pass. The owned browser fixture worker passed an actual local API/queue smoke check for all three pin types.

Public checks on 12 November 2026 used the ordinary API and production worker without configured cookies:

| Case                                               | Verified result                                                                                                                                                         |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Image pin](live-pinterest-image-2026-11-12.json)  | JPEG 399 × 600, 77,302 bytes; local preview, identical original bytes and retained PNG conversion                                                                       |
| [GIF pin](live-pinterest-gif-2026-11-12.json)      | GIF 400 × 400, 4 frames, 106,361 bytes; original bytes/frames preserved; retained MP4 conversion downloaded and independently probed                                    |
| [pin.it](live-pinterest-shortlink-2026-11-12.json) | Bounded Pinterest API share hop to one pin; JPEG 577 × 1024, 114,842 bytes; preview, identical original and PNG conversion                                              |
| [Video pin](live-pinterest-video-2026-11-12.json)  | All six offered renditions fully decoded and retrieved: 240 × 424, 360 × 640, 480 × 852, 640 × 1136, 720 × 1280 and 1080 × 1920, H.264/AAC; MP3 at 192 kbps also passed |

The browser suite uses clearly labelled owned local files through the real native adapter, API, SQLite queue and worker. It checks JPEG bytes, GIF frames and MP4 conversion, video/audio delivery, 128 kbps MP3, honest unknown-audio labels, retained history and long-title desktop/mobile layout. The workflow runs this alongside the four existing suites and production Docker Compose build/start. The feature PR records actual CI conclusions and screenshot review; enabling a test alone is not treated as a pass. Local Chromium startup is blocked by the development environment's socket restriction, and Docker is unavailable locally.

Live source media and owner screenshots are not republished. Public examples verify those exact scenarios and do not imply access to every pin. Pinterest owner-instance acceptance is still pending.

## Windows update

```powershell
git fetch origin
git switch feat/pinterest
git pull --ff-only
docker compose up -d --build
```

Refresh with Ctrl+F5. Try an image pin, an animated GIF, a video and a `pin.it` link. Check the original type, actual video resolution and audio, MP3 when audio exists, and retained conversion. The persistent volume and existing history are preserved. Opt-in isolated checks are `scripts/verify_photos.py --ephemeral --output /tmp/report.json URL` for image/GIF pins and `scripts/verify_live.py --ephemeral --quality all --output /tmp/report.json URL` for videos.

The next planned block expands the converter's actual input/output coverage, animation/transparency and GIF controls; batch uploads and collection scanning remain later work.
