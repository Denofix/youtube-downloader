"""Browser-test worker for owned images; never included in the production image."""

import functools
import http.server
import tempfile
import threading
import time
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageDraw
from service import photos, runner
from service.errors import ServiceError
from service.store import Store
from yt_dlp.extractor.tiktok import TikTokIE

URL = "https://www.tiktok.com/@ui.fixture/video/7100000000000000001"


def main():
    with tempfile.TemporaryDirectory(prefix="photo-browser-fixture-") as temporary:
        root = Path(temporary)
        specifications = [
            ("1.jpg", (320, 640), "#f97316"),
            ("2.png", (640, 480), "#1d4ed8"),
            ("3.webp", (500, 500), "#16a34a"),
        ]
        for name, size, color in specifications:
            image = Image.new("RGB", size, color)
            ImageDraw.Draw(image).text(
                (24, 35), f"Photo {name[0]} - owned local fixture", fill="white", font_size=18
            )
            image.save(root / name)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Handler, directory=str(root))
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:" + str(server.server_port)
        post = {
            "id": "7100000000000000001",
            "desc": "Owned carousel (local fixture) — " + "LongPhotoTitle" * 25,
            "author": {"uniqueId": "ui.fixture"},
            "imagePost": {
                "images": [
                    {
                        "imageWidth": size[0],
                        "imageHeight": size[1],
                        "imageURL": {"urlList": [base + "/" + name]},
                    }
                    for name, size, color in specifications
                ]
            },
        }

        def data(self, url, post_id):
            if url != URL:
                raise ServiceError(
                    "invalid_fixture", "This fixture accepts only the owned test post."
                )
            return deepcopy(post), 0

        TikTokIE._extract_web_data_and_status = data
        real_check = photos.check_media_url
        photos.check_media_url = lambda url: url if url.startswith(base + "/") else real_check(url)
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
