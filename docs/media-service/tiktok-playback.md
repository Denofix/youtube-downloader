# TikTok playback and source delivery — 11 November 2026

The owner successfully downloaded TikTok media, but a highest-resolution H.265 result played with black video and audible sound. Windows Media Player explicitly requested an HEVC codec extension. The watermarked H.264 source played, showing that the download was decodable but the original codec was unsuitable for that player. The fix changes delivery rather than asking the owner to install a codec.

## Delivery policy

- TikTok video results use **Compatible MP4 — H.264 + AAC**, with 8-bit `yuv420p` video and faststart. Already compatible H.264/AAC-LC stereo streams are remuxed without re-encoding. HEVC/10-bit/incompatible video is encoded with libx264, CRF 18; audio is AAC-LC stereo. Encoding can take longer and change the output size. It does not improve the source or promise a lossless re-encode.
- Selected width and height are checked before and after processing. Portrait 1080 × 1920 is labelled **1080p**, with exact dimensions shown separately. There is no lower-resolution or different-source-video-codec fallback.
- Sources explicitly marked watermarked, including the web `download` rendition, are excluded. The worker checks the selected source again before publication. If no usable source without a reported watermark is available, the task fails instead of returning the marked variant. This selects available source media; it does not crop, blur or reconstruct a watermark.
- High-resolution HEVC renditions can alternate between muxed video/audio and video-only endpoints. Their audio is explicitly taken from an unmarked video rendition of the **same post**; the standalone music URL is never substituted. Only the selected high-resolution video stream and that clip audio are muxed into the final result.
- Duplicate CDN IDs are one quality option. TikTok can change mirror suffixes and the ID's total-bitrate number when removing muxed audio. Refreshing the URL is constrained to the same rendition family, dimensions, FPS and source video codec. The actual resolved IDs are recorded in the task result; a different resolution/codec fails with `format_unavailable`.
- Existing API requests using `original` for TikTok are handled as compatible video delivery. Cached watermarked choices are rejected, and the UI hides them. Fresh analysis after updating is required to see the current source choices. Other platforms retain their original-download behavior.

## Verification

The expanded local backend suite has **129 passing tests**, including real generated portrait HEVC/10-bit video with no audio, same-clip audio muxing, H.264 output with nonblack decoded pixels, audible PCM samples, MP3 extraction, watermark changes/rejection, CDN-ID changes, muxed-audio ID changes and rejection of changed geometry. Existing YouTube, SoundCloud, conversion, queue and process checks remain included.

The browser suite now generates HEVC/10-bit input, converts it to MP4, actually plays the H.264 result in a browser and reads visible pixels from a frame. It also checks the compatible default, hiding cached watermarked options, highest-source selection, mobile overflow and existing MP3/GIF/image/history flows. Actual CI results are recorded in PR #3; the workflow file alone is not evidence of a pass.

The live verification script supports `--quality lowest|highest|all` and optional `--save-results` for local playback inspection. Release verification checks each offered rendition, not only the smallest video. Dated live reports are linked here after those checks finish. The owner-instance playback gate remains open until the updated output is played there.

## SoundCloud scope

The newly supplied `mC39...` share link resolves to the same `jeembo-music/fallen-baldscum-remix` track, ID 2398469850. It still returns `drm_protected`; changing URL form does not produce an unprotected format. yt-dlp documents this SoundCloud encrypted-format limitation in [issue #17335](https://github.com/yt-dlp/yt-dlp/issues/17335). A creator-provided official download or a different available unprotected track is required.

The unprotected control track is [ethmusic/lostin-powers-she-so-heavy](https://soundcloud.com/ethmusic/lostin-powers-she-so-heavy). Its original M4A and MP3 results are checked separately. This establishes support for that available source, not universal SoundCloud downloading.

## Update the existing instance

```powershell
git pull --ff-only origin feat/soundcloud-tiktok
docker compose up -d --build
```

Refresh with Ctrl+F5 and analyze the TikTok link again. Choose the desired resolution and **Compatible MP4**; do not reuse the previously downloaded HEVC file. Download and play the new result. MP3 remains available as a separate output.
