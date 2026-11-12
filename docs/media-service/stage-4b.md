# Stage 4b — Instagram photos, carousels and the link-field focus fix

Branch: `feat/instagram-gallery`, stacked on `feat/instagram-video` / PR #5 at `165c6216`. No schema migration or runtime dependency change is needed. The owner confirmed Instagram Reel playback and TikTok photo/ZIP delivery; see [owner acceptance](owner-acceptance-2026-11-12.json). Instagram MP3 and this new carousel workflow have separate owner checks.

## Behavior

One Instagram post may contain a photo, a photo carousel, a video carousel or mixed photos/videos. Image-only posts use the existing photo selection workflow. Other carousels show each item's preview and type, with a source-format and Original/MP3 selector for each video. The user selects a subset; one queued job returns individual files and a flat ZIP for multiple results. Clicking a video selector does not toggle its checkbox. Source order is retained regardless of click order. Saved images and videos can enter the existing converter.

Images are bounded, fully decoded and cached during analysis, with local previews and SHA-256 fingerprints. Selected photos reuse that snapshot without another remote request and preserve the returned bytes. Video delivery refreshes the parent metadata once, checks the same parent/item identities and order, and binds each selected format to the existing exact-quality rules. Missing audio, changed items, changed quality or changed retained bytes fails the selection atomically. Pending jobs protect all retained image/preview inputs from expiry cleanup.

The Instagram adapter intercepts the locked extractor's `_extract_product` result before its video-only path discards images or expands a carousel. It reuses native authentication/browser transport and native video format parsing. The pinned private method is an explicit upgrade boundary. [Upstream yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/extractor/instagram.py) and [gallery-dl's public test cases](https://github.com/mikf/gallery-dl/blob/master/test/results/instagram.py) were reviewed; no gallery-dl dependency or GPL implementation is copied.

For images, the largest reported candidate is chosen. Logged-out metadata can contain only ordered image URLs without candidate dimensions; then the first offered source is used, with no guessed mirror substitutions. Its actual format and dimensions come from decoding. Declared dimensions, when present, must match. Unknown dimensions do not relax actual pixel/byte/content limits. A declared progressive audio stream with an unknown codec remains labelled `unknown`; final verification must establish audio rather than inventing a codec.

Limits remain 40 items per post, 16 MiB and 24 megapixels per original image, supported still JPEG/PNG/WebP, and existing video/job/storage/combined-file/ZIP limits. Image and redirect hosts are checked against the source platform's HTTPS CDN allowlist. Native media URLs, owner cookies and file paths stay out of public results and reports. Stories, profiles, live streams and opaque share URLs remain unsupported.

The link field now has one continuous focus indicator around the complete field and icon. The nested input's outline is removed only in this composite field. Other keyboard focus indicators are retained.

## Verification

**256 local tests pass**, including native-product image/video fixtures, real locked yt-dlp/HTTP downloads, MP3/compatible delivery, original image hashes and ZIP order, refreshed identities/quality/audio, incomplete posts, private URL redaction, actual pixel limits with missing metadata, expired inputs, restart, atomic cleanup and retained conversion. Ruff and frontend formatting/type/build pass. The new owned-fixture worker also passed a real local API/queue analysis smoke check.

Public checks on 12 November 2026 used the normal API and production worker, without configured cookies:

| Case | Result |
| --- | --- |
| [Single photo](live-instagram-single-photo-2026-11-12.json) | JPEG 1080 × 1350, 383,468 bytes; preview, unchanged original and PNG conversion passed |
| [Five-photo carousel](live-instagram-photo-carousel-2026-11-12.json) | All five previews; selected positions 1 and 5, both 1080 × 1080 JPEGs; 298,394-byte ZIP with identical bytes/order and PNG conversion passed |
| [Two-video carousel](live-instagram-video-carousel-2026-11-12.json) | Both returned 640 × 640 H.264 renditions fully decoded and delivered; a 5,208,059-byte ZIP preserved files/order. Those returned renditions have no audio |
| [Reel regression](live-instagram-reel-regression-2026-11-12.json) | 720 × 1280 H.264/AAC stereo MP4 and 192 kbps MP3 passed again after the adapter change |

Mixed photo/video delivery and per-item MP3 are covered by controlled native-product fixtures with real files. The public carousel above contains two videos, so it is not claimed as a live mixed-post or carousel-MP3 pass. Public source media and owner screenshots are not republished.

The browser suite adds actual single-photo/mixed-file downloads, source-ordered ZIP bytes, retained conversion, per-item MP3, reload/history, long titles and mobile/desktop overflow. Existing browser checks also assert that URL keyboard focus has no nested outline and capture focused desktop/mobile views. These are enabled in CI, but not recorded as passed merely because they exist. Local Chromium is blocked before startup by `socket() ... Operation not permitted`; Docker is unavailable in this development environment. Parent CI also remains queued without jobs. The new stage PR records the current CI result; owner-instance testing of the new gallery and focus appearance remains pending.

## Windows update

```powershell
git fetch origin
git switch feat/instagram-gallery
docker compose up -d --build
```

Refresh with Ctrl+F5. Check the link-field outline, an Instagram photo, a photo carousel and, where available, a carousel video with audio. Select a subset, compare individual files and ZIP, then convert a retained photo. Existing volumes, history and prior source workflows are preserved.

Opt-in isolated public checks are `scripts/verify_photos.py` for image-only posts and `scripts/verify_gallery.py` for video/mixed carousels; both support `--ephemeral --output /tmp/report.json URL`. Pinterest is the next source stage.
