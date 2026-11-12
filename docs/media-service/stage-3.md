# Stage 3 — TikTok photo posts and selected-photo delivery

Branch: `feat/tiktok-photos`, based on the owner-verified video/audio revision `8929f28aa86cad0adbacf0c1a56f802f807ac6f3`. This stage is stacked on `feat/soundcloud-tiktok` / PR #3; neither parent PR is assumed merged. No database schema migration or new runtime dependency is required.

## Behavior

A public TikTok `/@creator/photo/id` URL or safely resolved share link enters the existing worker queue. Analysis reads the photo-post metadata, downloads and fully decodes bounded original images, and creates local JPEG previews. The returned analysis contains opaque asset IDs, dimensions, formats, sizes and SHA-256 fingerprints, not signed CDN URLs.

The user selects photos, clears/reselects all, and adds a selection to the queue. The selected subset is one post-level job with individual image assets. Multiple selected images also produce a flat ZIP in source order, irrespective of the order of clicks. Original bytes are copied without re-encoding; ZIP uses stored entries because image formats are already compressed. A retained photo can be passed to the existing JPG/PNG/WebP converter.

Analysis caches the verified originals as well as previews. Consequently the initial analysis includes image-transfer time; subsequent selection/delivery does not fetch those images again. A selection is bound to that retained snapshot, not a later changed version of the remote post. Copies are hash-checked and decoded again before publication. Expired/missing inputs request fresh analysis; changed bytes fail the whole selection. Failure/cancellation discards partial task assets. Pending selections protect their retained input IDs from cleanup, and successful results receive their own retention period.

Limits: 40 photos per post, 16 MiB per original photo, 24 megapixels per image, plus the existing combined file/ZIP and storage limits. JPEG, PNG and still WebP are supported. Photo-post soundtrack extraction, photo-to-video rendering and other platforms are separate stages.

CDN image requests accept HTTPS only, known TikTok media domains, no embedded credentials, and the normal HTTPS port. Every redirect is checked before following it; redirects and URL mirrors are bounded. Both declared and streamed byte limits are enforced. Received contents are decoded, rather than trusting extensions or HTTP content types. ZIP names come from the backend's filename sanitizer and fixed photo positions.

## Extractor decision

Reviewed [gallery-dl's TikTok extractor](https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/tiktok.py), [its public photo test cases](https://github.com/mikf/gallery-dl/blob/master/test/results/tiktok.py), and the [locked yt-dlp TikTok implementation](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/extractor/tiktok.py). gallery-dl's implementation is GPL-2.0; none of its code is copied and no new dependency is added.

The existing yt-dlp browser/cookie transport can fetch the same TikTok video-detail data containing `imagePost`. This small adapter calls the locked extractor's `_extract_web_data_and_status` method; that private interface must be rechecked when yt-dlp is updated. The pinned dependency, adapter tests and separate live checks bound that dependency. Ordinary video and SoundCloud adapters remain in use for their existing scenarios.

## Verification

Controlled coverage includes a real local HTTP media server, JPEG/PNG/WebP decoding, actual previews, subset selection/source order, exact original bytes and ZIP contents, image conversion, persisted tasks, expired input protection, changed-snapshot cleanup, wrong dimensions, watermark flags, source/item/byte/pixel limits and redirect-host restrictions.

The browser photo suite uses explicitly labelled **owned local image fixtures**, with the real API/SQLite/runner/media/delivery path. Its test worker lives under `scripts/` and is excluded from the production image. It checks selection/clear/all, downloaded ZIP bytes, individual files, refresh persistence, conversion of a retained photo and mobile/desktop overflow. Public-source checks are separate.

Two public TikTok cases passed through the normal API and production worker:

| Publication | Result |
| --- | --- |
| [Single photo](live-tiktok-photo-single-2026-11-11.json) | 1080 × 1920 JPEG, 189,999 bytes; local preview, exact original retrieval and PNG conversion passed |
| [Two-photo carousel](live-tiktok-photo-carousel-2026-11-11.json) | JPEGs 1290 × 824 and 1440 × 2470; 87,345 and 207,275 bytes; original retrieval, a 294,990-byte ZIP with identical contents/order and PNG conversion passed |

The two-item live carousel selects both items; partial selection from a larger post is covered by the three-item controlled API/browser fixture. These cases establish those publications, not universal TikTok access. Source media and screenshots from public posts are not republished. Actual CI evidence is recorded in the stage PR. The owner subsequently confirmed TikTok photo downloads, opening the ZIP and viewing an original JPEG; see [owner acceptance](owner-acceptance-2026-11-12.json). Extended keyboard/long-title browser checks remain a separate CI gate.

## Update the existing Windows checkout

```powershell
git fetch origin
git switch feat/tiktok-photos
docker compose up -d --build
```

Refresh with Ctrl+F5. Paste a public photo-post link, wait for previews, select the desired items and add them to the queue. Check a single file, a multi-file ZIP, source order and conversion of a retained image. The existing volume, video/audio history and saved files remain available.

On Linux, an isolated opt-in check uses:

```bash
YTDLP_USE_SYSTEM_CA=1 PYTHONPATH=backend uv run --no-sync python scripts/verify_photos.py --ephemeral 'PUBLIC_TIKTOK_PHOTO_URL' --output /tmp/live-photos.json
```

`YTDLP_USE_SYSTEM_CA` is only needed for an owner-configured trusted proxy; normal installations can omit it. The ephemeral mode creates disposable API/worker/data and does not touch owner storage.

## Following stage

The owner photo check is confirmed. Instagram individual video/photo/carousel support is now implemented in stages 4a/4b; Pinterest image/video pins are next, with their own source/access verification. Batch uploads, profile/channel scanning, subscriptions and public multi-user hosting remain later stages.
