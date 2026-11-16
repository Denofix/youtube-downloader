# Download & Convert - Windows

[Українська](windows.uk.md)

Installation, configuration and use with **Docker Desktop Linux containers**. Run PowerShell commands **one at a time, from top to bottom**. Do not copy prompt markers such as `PS ...>` or `>>`. The interface supports **English / Українська**.

## 1. Install the prerequisites

1. Install [Git for Windows](https://git-scm.com/install/windows).
2. Check the [Docker Desktop requirements](https://docs.docker.com/desktop/setup/install/windows-install/): a supported 64-bit Windows version, virtualization enabled in BIOS/UEFI and at least 8 GB RAM. Open PowerShell **as administrator**, run `wsl --install` and restart. If WSL is already installed, run `wsl --update`.
3. Install and open [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/). Use the **WSL 2 engine** and **Linux containers**. Wait for the engine to start. If paused, select **Resume / Unpause**.
4. Open a new regular PowerShell window and verify:

```powershell
git --version
docker compose version
docker run --rm hello-world
```

Expect `Hello from Docker!`. Python, Node.js and FFmpeg are included in the application image; no separate installation is required.

## 2. Choose a folder and download the project

Choose **any folder you prefer** in File Explorer. Open it, click the address bar, type `powershell` and press Enter. PowerShell will open in your chosen folder. Then run:

```powershell
git clone --branch main https://github.com/Denofix/youtube-downloader.git
Set-Location .\youtube-downloader
Invoke-Item .
```

Git creates the `youtube-downloader` subfolder. Keep PowerShell in that project folder, alongside `compose.yaml` and `Dockerfile`. No editor is required. If using an existing terminal, navigate to your preferred parent folder before cloning; quote paths containing spaces. If the project is already downloaded, open its existing folder and use the update steps below.

## 3. Configure and start

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
Invoke-RestMethod http://localhost:8080/api/health
Start-Process "http://localhost:8080"
```

Wait for the first build to finish downloading dependencies. Both `api` and `worker` must run. The health response should show `status = ok` and `worker_online = True`; if the worker is still starting, repeat the health command after a few seconds. Open [http://localhost:8080](http://localhost:8080).

To change configuration, open `notepad .env`, save and run `docker compose up -d --build --wait` again.

| Setting | Default | Meaning |
| --- | --- | --- |
| `PORT` | `8080` | Local website port; for `8081`, use `http://localhost:8081` |
| `MAX_FILE_BYTES` | `536870912` | Up to 512 MiB per file |
| `MAX_STORAGE_BYTES` | `5368709120` | Up to 5 GiB of media storage |
| `RESULT_TTL_SECONDS` | `86400` | Files retained for 24 hours |
| `JOB_TIMEOUT_SECONDS` | `1800` | Up to 30 minutes per task |

Settings displays the server values; edit them in `.env`. Normal use does not require API keys. Source access depends on the publication and platform. By default, the service is reachable only on this computer.

## 4. Use the platform

Choose **English / Українська** in the top-right corner. Your browser remembers the choice.

| Page | What to do |
| --- | --- |
| **Download** | Paste one public YouTube, TikTok, Instagram or Pinterest publication link, or a SoundCloud track link. Click **Analyze link**, choose the format, quality or items and add the download to the queue. Multiple selected items also include a ZIP. |
| **Tasks** | Wait for **Completed**, download the result and open it. You can cancel, retry, check expiry or send a retained file to the converter. |
| **Convert** | Upload one local file, wait for inspection and choose an operation: video with sound to MP3, PNG to WebP, or video to a short GIF. Set the bitrate or GIF parameters and add the conversion to the queue. |
| **Settings** | Check worker status, tool versions, limits and storage usage. |

Start with a short video and a small image. Check video and sound, GIF movement and ZIP contents. MP3 requires an audio stream. Increasing bitrate does not recover lost quality. Batch uploads, channel/profile scanning and playlists are not supported yet.

## 5. Update, stop and restart

Open PowerShell **in the existing project folder**, keep Docker Desktop running and execute in this order:

```powershell
git fetch origin
git switch main
git pull --ff-only
docker compose up -d --build --wait
```

Press **Ctrl+F5**. Analyze the link again after source-related updates. Save any local Git changes before switching; do not discard them with `reset --hard`.

Run these commands separately when needed:

```powershell
docker compose stop
docker compose up -d --wait
docker compose logs --tail 80 api worker
```

They stop the services, restart them and show recent logs, respectively. History and files live in a persistent Docker volume. `docker compose down` keeps it; **`docker compose down -v` deletes the data**.

## 6. Troubleshooting

| Symptom | Action |
| --- | --- |
| `Docker Desktop is manually paused` | Resume / Unpause Docker Desktop, then start the stack again |
| `no configuration file provided` | Open the project root and check `Test-Path .\compose.yaml`; update Git before building |
| `unknown flag: --buildgit` | Paste commands separately; `--build` and `git fetch` belong to different commands |
| A path containing spaces fails | Quote the full path or open PowerShell from that folder in File Explorer |
| Port already in use | Choose a free `PORT` in `.env`, recreate the services and use the new address |
| Tasks stay queued | Check `worker_online`, the `worker` service and logs |
| The interface looks outdated | Wait for a successful build, then press Ctrl+F5 |

Keep the error text, `docker compose ps` output and recent logs for troubleshooting. [Repository](https://github.com/Denofix/youtube-downloader) · [Converter matrix](../media-service/converter-matrix.md) · [Operations and backups](../media-service/operations.md).
