"""Owned Instagram publication fixtures; excluded from the production image."""

import functools
import http.server
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from service import photos, runner
from service.store import Store
from yt_dlp.extractor.instagram import InstagramIE, _id_to_pk
from yt_dlp.utils import ExtractorError


def main():
    with tempfile.TemporaryDirectory(prefix="instagram-gallery-fixture-") as temporary:
        root = Path(temporary)
        Image.new("RGB", (80, 60), "orange").save(root / "one.jpg")
        Image.new("RGBA", (64, 48), (50, 100, 250, 120)).save(root / "three.png")
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=orange:s=160x90:r=12",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440",
                "-t",
                "1.2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(root / "two.mp4"),
            ],
            check=True,
        )

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Handler, directory=str(root))
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"

        def image(code, name, width, height):
            return {
                "pk": str(_id_to_pk(code)),
                "media_type": 1,
                "image_versions2": {
                    "candidates": [{"url": base + "/" + name, "width": width, "height": height}]
                },
            }

        def extract(self, url):
            code = urlsplit(url).path.rstrip("/").split("/")[-1]
            if code not in {"OwnedPost01", "OwnedPhoto01", "OwnedPhotos01"}:
                raise ExtractorError("Only owned fixture posts are available here", expected=True)
            first = image("OwnedImg01", "one.jpg", 80, 60)
            video = image("OwnedVid02", "one.jpg", 80, 60) | {
                "media_type": 2,
                "has_audio": True,
                "video_codec": "h264",
                "video_duration": 1.2,
                "video_versions": [
                    {"id": "owned-h264", "url": base + "/two.mp4", "width": 160, "height": 90}
                ],
            }
            third = image("OwnedImg03", "three.png", 64, 48)
            post = {
                "pk": str(_id_to_pk(code)),
                "caption": {
                    "text": "Owned Instagram post (local fixture) — " + "LongPostTitle" * 25
                },
                "user": {"username": "owned.creator", "full_name": "Owned creator"},
            }
            if code == "OwnedPhoto01":
                post.update(first | {"pk": str(_id_to_pk(code))})
            else:
                if code == "OwnedPhotos01":
                    video = first | {"pk": str(_id_to_pk("OwnedImg02"))}
                post.update(
                    {
                        "media_type": 8,
                        "carousel_media_count": 3,
                        "carousel_media": [first, video, third],
                    }
                )
            return self._extract_product(post, video_id=code, get_comments=False)

        InstagramIE._real_initialize = lambda self: None
        InstagramIE._real_extract = extract
        real_check = photos.check_media_url
        photos.check_media_url = lambda url, platform="TikTok": (
            url
            if isinstance(url, str) and url.startswith(base + "/")
            else real_check(url, platform)
        )
        store = Store()
        try:
            while True:
                store.heartbeat()
                task = store.claim()
                if task:
                    runner.execute(task, store)
                else:
                    time.sleep(0.1)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
