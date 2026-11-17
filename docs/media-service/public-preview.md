# Public interface preview

The preview is a separate static build of the existing Vue application. Its intended domain is **https://download-convert.flareledger.fun**; the apex domain and existing applications keep their routing.

## Scope

- Prepared video and photo selection, static MP4/MP3/GIF/image/ZIP results, conversion examples, simulated task states and browser-local history.
- English and Ukrainian localization, including a permanent preview notice.
- No processing API, worker, SQLite server database, file uploads, external-media extraction, authentication, production availability guarantee or server retention timer.
- No AI/LLM feature runs inside either build.
- The full owner-operated service still uses Docker Compose (API + worker + shared persistent volume).

Task transitions are simulated. Their timing is not an encoding or download benchmark. The listed media sizes, codecs and dimensions describe actual bundled files. Custom URLs receive a preview-only error; the file input is disabled. The settings page explains the preview rather than displaying fictional worker or storage metrics.

## Build and deployment

```bash
cd frontend
npm ci
npm run build:demo
```

Vercel project root: `frontend`; framework: Vite; output: `dist`; Node: 24.x. `frontend/vercel.json` selects the demo build. `npm run build` remains the ordinary self-hosted frontend build and does not copy the demo media directory. The preview uses the same UI with a mode-specific browser adapter, not a public connection to the owner's service. No backend credentials or environment secrets are needed.

The prepared assets are generated locally with `PYTHONPATH=backend uv run python scripts/build_demo_assets.py` (FFmpeg and Pillow required), verified through the service's media verifier, and committed for reproducible hosting without Python/FFmpeg on Vercel. Generated geometric images, test patterns and tones contain no third-party posts or user data. The generated TypeScript manifest records actual bytes and verified metadata.

## Verification

CI builds both modes. `scripts/check_demo_ui.py` uses a real Chromium browser to check sample-file bytes, ZIP contents, a transparent WebP, history persistence, blocked custom links/uploads, cancel/retry, EN/UK and 320–1440 px layouts. It rejects processing-API or external network requests. The ordinary backend, frontend, browser and Docker checks continue separately. Successful CI artifacts include real interface screenshots; these are screenshots of prepared examples, not evidence of live cloud media processing.

Before announcing a new deployment, check its Vercel READY state, source commit, HTTPS/custom-domain response and downloadable static asset. GitHub CI and a Vercel deployment are different checks. The preview URL is a maintained portfolio preview, not a versioned product release.

## Verified deployment - 17 November 2026

The initial preview was built from commit `342abac6067866ab82dea5f3110db6a216852b28` and uploaded as static files through the Vercel API. The connected Vercel account could not link this repository because the GitHub integration was not installed; automatic deployments after push are therefore not configured. The Vite settings above describe the source build, not an enabled Git integration.

Vercel reported READY; `download-convert.flareledger.fun` was verified with no DNS conflict. Unauthenticated HTTPS requests returned 200 for the page, JavaScript bundle and sample MP4; their SHA-256 hashes matched the local build. No existing apex/project domain was reassigned. The managed wildcard DNS already covered the subdomain, so no manual DNS record edit was required. The real Chromium preview check passed in [CI run 44123552577](https://github.com/Denofix/youtube-downloader/actions/runs/44123552577), alongside the full self-hosted checks. This is an interface preview; it is not evidence of a hosted media-processing worker or a production service release.
