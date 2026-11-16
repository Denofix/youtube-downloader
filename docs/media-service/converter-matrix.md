# Converter compatibility - stage 6a

The converter detects file contents, rather than trusting an extension. Available
operations depend on the installed output encoders. A container name alone does
not guarantee that every codec, damaged file or encrypted stream inside it works.

## Verified inputs and outputs

All examples below are generated local **real media files**: video test patterns,
sine-wave audio and Pillow images. No owner media, cookies or platform access is
used. The [recorded run](converter-matrix-2026-11-16.json) contains **104 successful
conversions**, actual output metadata, sizes, hashes and tool versions.

| Input example | Actual contents | Verified outputs |
| --- | --- | --- |
| MP4 | H.264, yuv420p + AAC | MP4, MOV, MKV, WebM; MP3, M4A, WAV, FLAC, OGG; GIF clip |
| MOV | H.264 + AAC | MP4, MOV, MKV, WebM; MP3, M4A, WAV, FLAC, OGG; GIF clip |
| MKV | FFV1 + FLAC | MP4, MOV, MKV, WebM; MP3, M4A, WAV, FLAC, OGG; GIF clip |
| WebM | VP9 + Opus | MP4, MOV, MKV, WebM; MP3, M4A, WAV, FLAC, OGG; GIF clip |
| MP3, M4A, WAV, FLAC, OGG | MP3, AAC, PCM signed 16-bit, FLAC, Vorbis respectively | Each of MP3, M4A, WAV, FLAC, OGG |
| JPEG, PNG, static WebP, single-frame GIF | RGB, RGBA, palette images | JPEG, PNG, WebP |
| CMYK JPEG | CMYK pixels | JPEG, PNG, WebP; PNG receives RGB pixels |
| JPEG with EXIF orientation 6 | Stored 64 x 48, displayed 48 x 64 | JPEG, PNG, WebP with physically oriented pixels |
| Animated GIF | Three different frames, 0.36 seconds | MP4, MOV, MKV, WebM; a bounded GIF clip |
| Rotated MOV | Stored 160 x 90 + a 90-degree display matrix | MP4, MOV, MKV, WebM at 90 x 160; portrait GIF without enlargement |
| Portrait MP4 | H.264, 96 x 160, no audio | MP4, WebM, GIF |
| Odd-size MKV | FFV1, 161 x 91, no audio | MP4/WebM at 162 x 92; GIF without forced even padding |
| Silent MP4 | H.264, no audio stream | MP4, MOV, MKV, WebM, GIF; audio outputs rejected |

Outputs MP4/MOV/MKV use H.264 yuv420p and AAC when sound exists. WebM uses
VP9/Opus. Odd-sized video receives at most one black pixel on the right/bottom,
preserving its original pixels instead of resizing them. Phone rotation is
applied during normal conversion. The displayed dimensions are exposed separately
from stored dimensions; source download quality checks still use stored dimensions.

## Contents checked

- Every video/audio/animation result is fully decoded before it becomes available.
- Images are decoded with Pillow, including **every GIF frame**. A JPEG with a
  readable header but truncated pixel data is rejected as `invalid_image`.
- Moving inputs produce multiple different frame hashes, rather than just a
  valid container holding a repeated still frame.
- Audio outputs are decoded to PCM and checked for a non-silent signal. Silent
  videos do not offer MP3 or other audio-only operations.
- Full video/audio durations differ by at most 0.2 seconds in these short
  fixtures, allowing codec priming and frame rounding. Original video FPS is
  checked. This is a test tolerance, not a guarantee for every damaged/VFR input.
- PNG/WebP preserve fully transparent and semitransparent pixels. JPEG has an
  explicitly documented white background. EXIF output orientation and actual
  pixels are checked, not just width/height tags.
- A wrongly named video and a Unicode/space-containing path still work by content.
- Upload -> inspection -> queue -> HTTP result -> MP3 reuse is tested with the
  real API and worker execution against an isolated SQLite store.

## Reproduce

From the repository root after installing development dependencies and FFmpeg:

```bash
uv sync --frozen --all-groups
uv run --no-sync pytest -q tests/test_conversion_matrix.py
PYTHONPATH=backend uv run --no-sync python scripts/verify_converter.py \
  --output /tmp/converter-matrix.json
```

The report runner creates and removes only its temporary fixture directory.
Generated media are not committed. The JSON records the local FFmpeg/Pillow
versions; CI separately tests the bookworm runtime used by the Docker image.

The additional real-browser scenario is:

```bash
uv run --no-sync python scripts/check_converter_ui.py --chromium /usr/bin/chromium
```

It exercises real upload/processing/download, a rotated-video GIF, history after
reload, displayed orientation, silent-input options, Ukrainian errors, preserved
language/form state and 320-1440-pixel layouts. CI runs it along with the six
existing browser suites and Docker startup checks. See [stage 6a](stage-6a.md)
for the observed run status; a workflow definition is not itself a passing result.

## Current boundaries and next steps

Animated WebP/APNG are rejected with a specific message: use GIF or video for
animation. Single-frame extraction, adjustable JPEG backgrounds/quality, resizing,
video quality profiles and video/audio trimming belong to **6b/6c**. They are not
implemented by this compatibility checkpoint.

GIF output is limited to a 15-second clip, 24 FPS and 720-pixel requested width;
actual width never exceeds the displayed input width. Existing upload limits,
two-hour media duration, 24-megapixel images and 500 animation frames still apply.
Video formats do not retain image transparency. Larger bitrate or re-encoding
does not improve source detail or guarantee a smaller file.

Setup and usage: [Windows](../users/windows.ru.md) · [Linux](../users/linux.ru.md).
