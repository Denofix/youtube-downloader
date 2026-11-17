"""Generate owned, tiny media examples for the public UI preview (no user/source data)."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw
from service import media

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend/demo-public"
DIRECTORY = PUBLIC / "demo-assets"


def ffmpeg(*args):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-threads",
            "2",
            "-filter_threads",
            "1",
            *map(str, args),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "frontend/public/favicon.svg", PUBLIC / "favicon.svg")
    video = DIRECTORY / "sample-video.mp4"
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x180:rate=12",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=44100",
        "-t",
        "2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        video,
    )
    ffmpeg(
        "-i",
        video,
        "-vf",
        "scale=160:90",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        DIRECTORY / "sample-video-small.mp4",
    )
    ffmpeg(
        "-i",
        video,
        "-c:v",
        "libx264",
        "-crf",
        "25",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        DIRECTORY / "sample-converted.mp4",
    )
    ffmpeg("-i", video, "-vn", "-c:a", "libmp3lame", "-b:a", "192k", DIRECTORY / "sample-audio.mp3")
    ffmpeg(
        "-i",
        video,
        "-vf",
        "fps=8,scale=320:-1,split[a][b];[a]palettegen[p];[b][p]paletteuse",
        "-loop",
        "0",
        DIRECTORY / "sample-animation.gif",
    )
    ffmpeg(
        "-i",
        DIRECTORY / "sample-animation.gif",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        DIRECTORY / "sample-animation.mp4",
    )
    ffmpeg("-i", video, "-frames:v", "1", DIRECTORY / "sample-poster.jpg")
    for number, color in ((1, "#fb7712"), (2, "#47a9a0")):
        image = Image.new("RGBA", (320, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((15, 15, 305, 185), radius=32, fill=color)
        draw.ellipse((70, 45, 190, 165), fill="#1a2637")
        draw.rectangle((170, 72, 270, 128), fill="#f5eddd")
        image.save(DIRECTORY / f"sample-image-{number}.png")
        image.save(DIRECTORY / f"sample-image-{number}.webp", lossless=True)
        white = Image.new("RGB", image.size, "white")
        white.paste(image, mask=image.getchannel("A"))
        white.save(DIRECTORY / f"sample-image-{number}.jpg", quality=90)
    with zipfile.ZipFile(DIRECTORY / "sample-photos.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(DIRECTORY / "sample-image-1.png", "01-sample.png")
        archive.write(DIRECTORY / "sample-image-2.jpg", "02-sample.jpg")
    files = {
        "video": "sample-video.mp4",
        "video_low": "sample-video-small.mp4",
        "converted_mp4": "sample-converted.mp4",
        "mp3": "sample-audio.mp3",
        "gif": "sample-animation.gif",
        "gif_mp4": "sample-animation.mp4",
        "poster": "sample-poster.jpg",
        **{
            f"image{number}_{fmt}": f"sample-image-{number}.{fmt}"
            for number in (1, 2)
            for fmt in ("png", "jpg", "webp")
        },
        "photos_zip": "sample-photos.zip",
    }
    manifest = {}
    for number, (key, filename) in enumerate(files.items(), 1):
        path = DIRECTORY / filename
        metadata = (
            media.verify(path)
            if path.suffix != ".zip"
            else {"kind": "archive", "format": "zip", "has_audio": False}
        )
        outputs = (
            ("mp4", "gif", "mp3")
            if key in {"video", "video_low", "converted_mp4"}
            else ("mp4", "gif")
            if key in {"gif", "gif_mp4"}
            else ("mp3",)
            if key == "mp3"
            else ("png", "jpg", "webp")
            if key.startswith("image")
            else ()
        )
        manifest[key] = {
            "id": f"{number:032x}",
            "name": filename,
            "url": "/demo-assets/" + filename,
            "size": path.stat().st_size,
            "metadata": {
                k: v
                for k, v in metadata.items()
                if v is not None
                and k
                in {
                    "kind",
                    "format",
                    "duration",
                    "width",
                    "height",
                    "display_width",
                    "display_height",
                    "video_codec",
                    "audio_codec",
                    "transparent",
                    "has_audio",
                }
            },
            "operations": [
                {"id": fmt, "label": "Prepared sample: " + fmt.upper(), "transcoding": True}
                for fmt in outputs
            ],
        }
    content = 'import type { Asset } from "./api";\n\nexport const sampleAssets: Record<string, Omit<Asset, "expires_at"> & { url: string }> = '
    content += json.dumps(manifest, indent=2) + ";\n"
    (ROOT / "frontend/src/demo-assets.ts").write_text(content)
    print(
        f"Verified {len(manifest)} static sample assets ({sum(x['size'] for x in manifest.values())} bytes)."
    )


if __name__ == "__main__":
    main()
