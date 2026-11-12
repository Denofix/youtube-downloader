"""Owned Pinterest native-API fixture for browser delivery checks; never production."""

import functools
import http.server
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image
from service import photos, runner
from service.store import Store
from yt_dlp.extractor.pinterest import PinterestIE
from yt_dlp.utils import ExtractorError


def main():
    with tempfile.TemporaryDirectory(prefix="pinterest-browser-fixture-") as temporary:
        root = Path(temporary)
        Image.new("RGB", (80, 60), "orange").save(root / "owned.jpg")
        frames = [Image.new("RGB", (64, 48), c) for c in ("orange", "navy", "yellow")]
        frames[0].save(
            root / "owned.gif", save_all=True, append_images=frames[1:], duration=120, loop=0
        )
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
                str(root / "owned.mp4"),
            ],
            check=True,
        )

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Handler, directory=str(root))
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def call(self, resource, pin_id, options):
            if pin_id not in {"123456789", "223456789", "323456789"}:
                raise ExtractorError("This fixture only serves the owned pins", expected=True)
            animated = pin_id == "223456789"
            data = {
                "id": pin_id,
                "privacy": "public",
                "title": "Owned Pinterest "
                + ("animation" if animated else "video" if pin_id == "323456789" else "image")
                + " (local fixture) — "
                + "LongPinTitle" * 25,
                "images": {
                    "orig": {
                        "url": base + ("/owned.gif" if animated else "/owned.jpg"),
                        "width": 64 if animated else 80,
                        "height": 48 if animated else 60,
                    }
                },
            }
            if pin_id == "323456789":
                data["videos"] = {
                    "video_list": {
                        "V_720P": {
                            "url": base + "/owned.mp4",
                            "width": 160,
                            "height": 90,
                            "duration": 1200,
                        }
                    }
                }
            if animated:
                data["embed"] = {"type": "gif", "src": base + "/owned.gif"}
            return {"status": "success", "data": data}

        real_check = photos.check_media_url
        photos.check_media_url = lambda url, platform="TikTok": (
            url
            if isinstance(url, str) and url.startswith(base + "/")
            else real_check(url, platform)
        )
        PinterestIE._real_initialize = lambda self: None
        PinterestIE._call_api = call
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
            thread.join()


if __name__ == "__main__":
    main()
