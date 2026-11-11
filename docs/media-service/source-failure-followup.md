# Source failure follow-up — 11 November 2026

The owner rebuilt the stage-2 Windows Compose stack successfully, but both supplied share links failed with an opaque `source_error`. This follow-up fixes missing browser transport support and distinguishes actionable source errors. The owner's network-specific TikTok failure is not claimed to be conclusively reproduced or fixed until that instance is checked again.

## Findings and live evidence

| Case | Actual observation |
| --- | --- |
| Owner's TikTok share link | Resolves to video 7705216175302659350. In the development environment, analysis and exact original MP4/MP3 downloads succeeded both before and after installing curl-cffi. The post-update outputs were decoded/verified and retrieved with HTTP 200: 576 × 1024 H.264/AAC MP4, 9,065,487 bytes; MP3, 1,767,594 bytes. Clip duration is approximately 73.6 seconds. |
| Owner's SoundCloud share link | Resolves to `jeembo-music/fallen-baldscum-remix`, source ID 2398469850. The upstream extractor reports DRM protection and does not return an available unprotected format. The prior error classifier hid this reason. The service now returns `drm_protected` and explains the available next step. |
| Public SoundCloud control track | The earlier 143-second public track still passes original M4A and MP3 retrieval after the dependency change. This verifies a working unprotected track, not all SoundCloud material. |

Reports: [owner TikTok link](live-owner-tiktok-2026-11-11.json), [owner SoundCloud link](live-owner-soundcloud-2026-11-11.json), [SoundCloud regression check](live-soundcloud-transport-2026-11-11.json). Share tracking tokens, signed media URLs, cookie contents and personal screenshots are not published. Earlier successful and failed reports remain separate.

## Changes

- Install yt-dlp's official `curl-cffi` extra and update the frozen lock/export. The previous image omitted this dependency even though TikTok's extractor requests browser impersonation. curl-cffi 0.17.0 provides usable browser targets in the tested runtime. The installed yt-dlp version remains 2026.10.26.
- Let extractors request browser transport where they need it. Global impersonation is not forced onto YouTube or all downloads.
- Distinguish DRM protection, unavailable SoundCloud public API credentials, rate limiting, regional restrictions and unreadable source/challenge pages. Error messages and codes contain no raw upstream logs or credentials.
- Show the failed task's error code directly in the Download alert. Settings shows curl-cffi's version and whether browser transport targets actually load.
- Add a safe in-container diagnostic command. It uses the same validation and analysis path and emits versions, browser target availability, the accepted canonical permalink and sanitized outcomes. It does not download media or export cookies.
- Extend the container CI gate to run the runtime diagnostic. A package installed without usable native browser targets fails that gate. Browser tests check the visible DRM reason/code and runtime Settings; the expanded backend suite has 116 passing cases locally.

DRM-protected media remains unavailable through this service. A creator-provided official download or another available unprotected track is required. Private/cookie access and actual network blocks remain separate conditions.

## Update and recheck on Windows

From the existing repository on `feat/soundcloud-tiktok`:

```powershell
git pull --ff-only origin feat/soundcloud-tiktok
docker compose up -d --build
```

Refresh `http://localhost:8080`. In Settings, `curl-cffi` must show a version and Browser transport support must read Available. Retry the supplied TikTok share link using Original and Audio MP3. The SoundCloud example should now show `drm_protected`, while a public unprotected track can be tested separately.

If TikTok still fails, run the diagnostic in the **same worker container and network**:

```powershell
docker compose exec -T worker python -m service.diagnostics "https://www.tiktok.com/@jua209njo656/video/7705216175302659350"
```

For a local runtime check without source requests:

```powershell
docker compose exec -T worker python -m service.diagnostics --runtime-only
```

Do not treat a successful development-environment download or a Telegram bot's network as proof that every owner's network will behave identically. The precise owner TikTok failure remains open until the updated container's result is observed.
