> Historical audit/handoff from the interrupted first session. Implementation has since been restored on `feat/media-platform`; see the root README and support matrix for current status. Historical test results below are not substituted for fresh checks.

# Legacy downloader audit

Audited on 11 November 2026 at commit [30f0e41abd27c091c71342c19b0f277ca64e7f9d](https://github.com/Denofix/youtube-downloader/tree/30f0e41abd27c091c71342c19b0f277ca64e7f9d).

This branch preserves the audit and requirements. It does **not** contain the locally prepared web-service implementation; the execution environment became unavailable before that implementation could be pushed. See [handoff](implementation-handoff.md).

## Repository baseline

Eleven files: one CustomTkinter entry point (`main.py`), icons/screenshots, README, requirements and Nord_Fillin's MIT license. No web frontend, API, durable queue, worker, automated test suite or CI existed at the audited commit.

## Confirmed findings

| Finding | Evidence or reproduction | Effect |
| --- | --- | --- |
| Windows-only FFmpeg discovery | `get_ffmpeg_path()` checks only `resource_path("ffmpeg.exe")`; the extracted function returned `None` while `/usr/bin/ffmpeg` was installed | Linux source execution cannot pass the download precheck; Windows needs the expected executable |
| Current-directory resource paths | Unbundled `resource_path` uses `os.path.abspath(".")` | Starting from another directory can lose assets/FFmpeg |
| Windows-only folder opening | `os.startfile(DOWNLOAD_FOLDER)` | Not portable |
| Static quality list | 360p, 480p, 720p, 1080p | Offered choices may not exist for the source |
| Unrestricted quality fallback | The video selector ends in `/best` without a height restriction | A fallback need not respect the user's selected quality cap |
| Deferred exception reference | `except Exception as e` followed by a scheduled `lambda: str(e)` | Controlled delayed execution raised `NameError: name 'e' is not defined`, hiding the original failure |
| UTF-16 requirements | BOM `FF FE`; decoded successfully as UTF-16 | Confirmed encoding, not proof that pip itself fails |
| Runtime/build dependency mix | Runtime GUI/media packages mixed with PyInstaller, altgraph, pefile and pywin32-ctypes | Windows packaging coupled to runtime |
| Old extractor baseline / missing explicit JS setup | Legacy pin `yt-dlp==2026.6.9`, bare yt-dlp, no runtime configuration | Version gap and incomplete current YouTube setup; not a proven universal failure cause |
| Shared files and daemon threads | One title-based directory, background widget reads, delayed button disabling | No durable queue, cancellation, isolation, restart recovery or expiry; duplicate actions/collisions are possible |
| No result/content verification | Separate preview/download extraction; success displayed after `ydl.download` | Selection is not tied to analysis; tool success alone does not establish a valid output |

## What was actually reproduced

- Creating a Tk root raised `TclError: no display name and no $DISPLAY environment variable`. The entire legacy GUI was not interactively tested. Its GUI-independent discovery function and Python callback defect were reproduced separately.
- The older test URL `BaW_jenozKc` returned unavailable.
- A different public 19-second video, `jNQXAC9IVRw`, returned metadata and 17 formats with current yt-dlp after using the environment's system CA trust store.
- Default certifi trust encountered the environment's network proxy certificate. Using system CAs kept TLS verification enabled. This environment observation does not establish the cause on the owner's Windows machine.
- Live service attempts for exact formats `160+140` and MP3 extraction failed. Follow-up direct extraction produced two 195-byte files; ffprobe rejected both and FFmpeg could not merge them. The precise upstream/network cause was not established. Live YouTube file downloading was **not verified**.
- A local API was started. Browser navigation was blocked by an installed extension (`ERR_BLOCKED_BY_CLIENT`); headless Chromium could not create its required Unix socket inside the command environment. No fabricated UI screenshot was produced.

## Official guidance reviewed

The current [yt-dlp dependency documentation](https://github.com/yt-dlp/yt-dlp#dependencies) and [EJS setup guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS) were checked. Full YouTube support uses yt-dlp-ejs and a supported JavaScript runtime; Deno is recommended/default, while Node needs explicit enablement. The proposed service uses `yt-dlp[default]`, Node 24 and `js_runtimes={"node": {}}`, plus FFmpeg/ffprobe from PATH. Solver dependencies are installed rather than remotely fetched per request.

The original failure cannot be assigned one definitive cause without the original error, installed versions and a reproducible link. Confirmed code defects, environment restrictions and source failures remain distinct.
