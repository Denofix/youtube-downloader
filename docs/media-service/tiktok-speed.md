# TikTok processing speed — 11 November 2026

The owner confirmed that compatible TikTok MP4 now plays in Windows Media Player and that a public SoundCloud track downloads and plays as M4A. The remaining concern was TikTok preparation time. The earlier DRM-only SoundCloud remix is a separate source restriction.

The default Compose worker has a two-CPU limit. A TikTok job includes metadata retrieval, media transfer, sometimes same-post audio retrieval, HEVC-to-H.264 encoding and final decoding checks. Internet throughput affects transfer; CPU and selected resolution affect conversion. The displayed download ETA covers the current transfer, not the entire job.

## Changes

- Use libx264 `veryfast` instead of `fast`, keeping CRF 18, selected dimensions, H.264 High, 8-bit yuv420p and AAC-LC. A faster preset changes compression decisions; this is not a lossless encode or a guarantee of identical output size.
- Inspect the actual selected source for embedded clip audio. When it is already present, skip the extra metadata request, extra clip-audio download and intermediate merge. When audio is absent, retain the same-post audio fallback. Extractor claims alone do not decide whether audio is present.
- Avoid fully decoding the input once before converting it. Encoding uses FFmpeg `-xerror`, and the final MP4 is still fully decoded before publication. Compatible H.264/AAC is copied and then fully decoded. Corrupt-input rejection is covered by a real damaged HEVC fixture.
- Record monotonic processing time and accumulated operation times in `result.timings`. Completed download/conversion cards show total processing, transfer and conversion/check time. Processing time starts when the worker executes a job; queue waiting and the separate initial analysis are excluded. Old tasks without timings remain readable.

## Measurements

The [recorded report](tiktok-speed-2026-11-11.json) uses the owner's complete approximately 73.7-second, 1080 × 1920 post. These are single measurements on a shared Linux development host with two encoder/decoder threads; wall times vary with host load and TikTok responses.

| Measurement | Before | After |
| --- | ---: | ---: |
| Complete video job after initial analysis | 248.526 s | 119.022 s |
| Conversion including final decoding check | 197.552 s | 84.035 s |
| Media transfer inside the job | 2.379 s | 2.164 s |
| Source extraction inside the job | 33.323 s | 32.181 s |
| Additional input-verification operation | 14.838 s | 0.190 s |
| Delivered video size | 61,720,267 bytes | 54,307,202 bytes |

A separate conversion of the exact same cached full source took 84.659 seconds with the new preset, including its final decoding check. The live after-test used a video-only upstream variant, so it exercised the audio fallback; it still required both source extractions. The embedded-audio optimization is independently covered by the real local fixture and makes only one extraction during download.

The optimized live MP4 preserved 1080 × 1920, H.264 High/yuv420p, AAC-LC stereo and approximately 73.7 seconds. Full decoding and HTTP 200 retrieval passed. MP3 also passed, taking 19.825 seconds including 16.142 seconds of source extraction.

## Validation and scope

The full backend/media/process suite passes **131 tests**, including playable HEVC conversion, audible clip audio, actual embedded-audio reuse, silent-source fallback, corrupt HEVC rejection, watermark rejection, changed-source quality checks and persisted timings. Frontend format, type and build checks pass. The real browser suite checks processing-time visibility and H.264 frame playback; CI results are recorded in PR #3.

These changes preserve the selected resolution and watermark policy. They do not silently select lower-quality H.264, add watermarked fallbacks, require GPU setup or increase the worker's CPU limit. Choosing an available native H.264 source can avoid video re-encoding; the offered H.264 source in this post is lower resolution than its 1080p HEVC source.
