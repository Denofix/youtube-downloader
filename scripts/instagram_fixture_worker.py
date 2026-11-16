"""Owned HTTP video fixture behind the real Instagram/API/worker pipeline; test only."""

import functools
import http.server
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from service import runner
from service.store import Store
from yt_dlp.extractor.instagram import InstagramIE
from yt_dlp.utils import ExtractorError


def main():
    with tempfile.TemporaryDirectory(prefix="instagram-browser-fixture-") as temporary:
        root = Path(temporary)
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
        threading.Thread(target=server.serve_forever, daemon=True).start()
        source = f"http://127.0.0.1:{server.server_port}/owned.mp4"

        def extract(self, url):
            if url == "https://www.instagram.com/p/NeedsAccess/":
                raise ExtractorError(
                    "The webpage request was redirected to the login page /srv/owner-session.txt",
                    expected=True,
                )
            if url != "https://www.instagram.com/reel/OwnedIG01/":
                raise ExtractorError("This fixture accepts only the owned test post", expected=True)
            return {
                "id": "OwnedIG01",
                "title": "Owned Instagram video (local fixture) — " + "LongVideoTitle" * 25,
                "uploader": "Owned creator",
                "duration": 1.2,
                "formats": [
                    {
                        "format_id": "owned-h264",
                        "url": source,
                        "ext": "mp4",
                        "vcodec": "h264",
                        "acodec": "aac",
                        "width": 160,
                        "height": 90,
                        "fps": 12,
                    }
                ],
            }

        InstagramIE._real_initialize = lambda self: None
        InstagramIE._real_extract = extract
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
