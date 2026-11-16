# Download & Convert - Linux

[Українська](linux.uk.md)

Installation, configuration and use. Commands target **Ubuntu 24.04 LTS**, Desktop, Server or VMware. For other distributions, follow the [official Docker Engine installation](https://docs.docker.com/engine/install/) and install the Compose plugin, then continue from section 2. Run commands **one at a time, from top to bottom**; do not copy the `$` prompt marker.

## 1. Prepare Ubuntu

If Docker and `docker compose` already work, keep your existing installation. On a clean Ubuntu system, install the Ubuntu repository packages:

```bash
sudo apt update
sudo apt install -y git curl software-properties-common
sudo add-apt-repository -y universe
sudo apt update
sudo apt install -y docker.io docker-compose-v2 docker-buildx
sudo systemctl enable --now docker
git --version
sudo docker compose version
sudo docker run --rm hello-world
```

Expect `Hello from Docker!`. Packages: [docker.io](https://packages.ubuntu.com/noble/docker.io), [docker-compose-v2](https://packages.ubuntu.com/noble/docker-compose-v2), [docker-buildx](https://packages.ubuntu.com/noble/docker-buildx). Alternatively, follow [Docker's repository instructions](https://docs.docker.com/engine/install/ubuntu/). Do not mix installation methods on an existing server.

Docker commands here use `sudo`; password characters are not displayed. Run Git as your normal user. Python, Node.js and FFmpeg are included in the application image.

## 2. Choose a folder and download the project

Choose **any parent folder you prefer**. Open a terminal there using the file manager's **Open in Terminal**, or navigate there with `cd`. Then run:

```bash
git clone --branch main https://github.com/Denofix/youtube-downloader.git
cd youtube-downloader
ls compose.yaml Dockerfile
```

Git creates the `youtube-downloader` subfolder. Run all following commands from that project folder. Quote paths containing spaces. If the project is already downloaded, open its existing folder and use the update steps below. On Ubuntu Desktop, `xdg-open .` opens the folder; a server needs no graphical interface.

## 3. Configure and start

```bash
[ -f .env ] || cp .env.example .env
sudo docker compose config --quiet
sudo docker compose up -d --build --wait
sudo docker compose ps
curl -fsS http://127.0.0.1:8080/api/health
```

Wait for the first build to finish. Both `api` and `worker` must run. The health response should contain `"status":"ok"` and `"worker_online":true`; if the worker is still starting, repeat the command after a few seconds. In a browser **on this Ubuntu machine**, open [http://localhost:8080](http://localhost:8080).

To change configuration, use `nano .env`, save and run `sudo docker compose up -d --build --wait` again.

| Setting | Default | Meaning |
| --- | --- | --- |
| `PORT` | `8080` | Local website port; for `8081`, use `http://localhost:8081` |
| `MAX_FILE_BYTES` | `536870912` | Up to 512 MiB per file |
| `MAX_STORAGE_BYTES` | `5368709120` | Up to 5 GiB of media storage |
| `RESULT_TTL_SECONDS` | `86400` | Files retained for 24 hours |
| `JOB_TIMEOUT_SECONDS` | `1800` | Up to 30 minutes per task |

Settings displays the server values; edit them in `.env`. Normal use does not require API keys. Source access depends on the publication and platform. By default, the service listens only on `127.0.0.1`.

## 4. Access a VM or server from another computer

If SSH is not already available, prepare it **on Ubuntu**:

```bash
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
whoami
hostname -I
```

In PowerShell or a terminal **on your main computer**, replace `USER` and `UBUNTU_IP` with the Ubuntu username and a reachable Ubuntu IP address:

```text
ssh -N -L 18080:127.0.0.1:8080 USER@UBUNTU_IP
```

Leave that terminal open and visit [http://localhost:18080](http://localhost:18080). The main computer must be able to reach Ubuntu's SSH service. If `PORT` was changed, replace the final `8080` in the command. The main computer and VM have different `localhost` addresses. Direct access to the VM's IP on port 8080 is unavailable with the default loopback binding.

## 5. Use the platform

Choose **English / Українська** in the top-right corner. Your browser remembers the choice.

| Page | What to do |
| --- | --- |
| **Download** | Paste one public YouTube, TikTok, Instagram or Pinterest publication link, or a SoundCloud track link. Click **Analyze link**, choose the format, quality or items and add the download to the queue. Multiple selected items also include a ZIP. |
| **Tasks** | Wait for **Completed**, download and open the result. You can cancel, retry, check expiry or convert a retained file. |
| **Convert** | Upload one local file, wait for inspection, choose an operation and set the bitrate or GIF parameters. Add it to the queue. Examples: video with sound to MP3, PNG to WebP, video to a short GIF. |
| **Settings** | Check worker status, tool versions, limits and storage usage. |

Start with a short video and a small image. Check video and sound, GIF movement and ZIP contents. MP3 requires an audio stream. Increasing bitrate does not recover lost quality. Batch uploads, channel/profile scanning and playlists are not supported yet.

## 6. Update, stop and restart

Open a terminal **in the existing project folder** and run in this order:

```bash
git fetch origin
git switch main
git pull --ff-only
sudo docker compose up -d --build --wait
```

Press **Ctrl+F5**. Analyze the link again after source-related updates. Save any local Git changes before switching; `reset --hard` is not needed for normal updates.

Run these commands separately when needed:

```bash
sudo docker compose stop
sudo docker compose up -d --wait
sudo docker compose logs --tail 80 api worker
```

They stop the services, restart them and show recent logs, respectively. History and files live in a persistent Docker volume. `docker compose down` keeps it; **`docker compose down -v` deletes the data**.

## 7. Troubleshooting

| Symptom | Action |
| --- | --- |
| Docker `permission denied` | Run Docker commands with `sudo`, as shown above |
| `Cannot connect to the Docker daemon` | Check `sudo systemctl status docker`; start it with `sudo systemctl start docker` |
| `no configuration file provided` | Open the repository root containing `compose.yaml`; update Git first |
| Port already in use | Choose a free `PORT` in `.env`, recreate the services and use the new address |
| Tasks stay queued | Check `worker_online`, the `worker` service and logs |
| The main computer cannot open the site | Check the SSH tunnel and use `localhost:18080` on the main computer |
| The interface looks outdated | Wait for a successful build, then press Ctrl+F5 |

Keep the error text, `sudo docker compose ps` output and recent logs for troubleshooting. [Repository](https://github.com/Denofix/youtube-downloader) · [Converter matrix](../media-service/converter-matrix.md) · [Operations and backups](../media-service/operations.md).
