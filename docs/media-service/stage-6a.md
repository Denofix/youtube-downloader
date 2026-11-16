# Stage 6a - converter compatibility and user guides

## Result

The next checkpoint after the five source adapters and English/Ukrainian UI
establishes a content-verified converter baseline. Quality/resolution profiles,
video/audio trimming and image editing remain the next checkpoints, **6b/6c**.

- Added a [104-case real-file matrix](converter-matrix.md), its
  [local evidence](converter-matrix-2026-11-16.json), reusable owned fixtures and
  a report runner. Actual sound, moving frames, dimensions, FPS, duration,
  transparency, orientation and output decoding are checked.
- Distinguish stored and displayed dimensions for EXIF photos/rotated videos;
  show displayed dimensions in Convert and bound GIF width by displayed width.
- Pad odd video sizes by one pixel where needed instead of stretching pixels.
- Convert CMYK JPEG pixels to RGB for PNG output.
- Decode actual image pixels and every GIF frame before publishing metadata.
  Truncated JPEGs and unsupported non-GIF animations fail with specific,
  Ukrainian-translated errors. Animated GIF duration is exposed; the form keeps
  its duration inside the existing minimum bound.
- Added separate [Windows](../users/windows.ru.md) and
  [Linux/Ubuntu](../users/linux.ru.md) installation, configuration and usage
  instructions, linked from README. They include main updates, Docker pause,
  quoted paths, health, language selection, troubleshooting and VM/SSH access.
  Matching three-page PDFs are delivered separately; the Markdown guides are
  the repository's editable source.

## Observed verification - 16 November 2026

- Local backend/media/process regression suite: **428 passed**.
- Local frontend localization suite: **7 passed**; formatting, type checking and
  production build passed.
- Standalone matrix runner: **104 passed**, with actual file hashes and versions
  recorded in the JSON report.
- Each PDF contains three pages; all pages were rendered and visually reviewed,
  text and clickable links checked. Clean Docker installation on a new Windows
  or Ubuntu host was not repeated here; that remains a stage-7 acceptance gate.
- Local browser execution is blocked by this environment's Chromium Unix-socket
  permission restriction. [PR #9](https://github.com/Denofix/youtube-downloader/pull/9)
  links the current CI results for all seven browser suites and the production
  Docker startup. CI also runs the 428 backend and 7 localization cases against
  the bookworm environment; its current checks are the integration gate.

## Owner acceptance

Update the feature branch, rebuild Docker, hard-refresh and test:

1. A phone-rotated MOV -> MP4/GIF. The preview dimensions and output should be
   portrait, with no unwanted enlargement.
2. A transparent PNG -> WebP and JPEG. WebP keeps alpha; JPEG uses white.
3. A short video with sound -> MP3; a silent video should not offer MP3.
4. An animated GIF -> MP4. Several changing frames should remain visible.
5. Follow the relevant installation/usage guide on Windows or Ubuntu.

Owner verification is pending; passing generated fixtures does not mean that
every possible codec or platform publication is supported.
