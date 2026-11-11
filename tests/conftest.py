import functools
import http.server
import subprocess
import threading
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from service.api import create_app
from service.config import Settings
from service.runner import execute
from service.store import Store


@pytest.fixture
def config(tmp_path):
    return replace(Settings(), data_dir=tmp_path / "state", allowed_hosts=("localhost",))


@pytest.fixture
def store(config):
    return Store(config)


@pytest.fixture
def client(config):
    with TestClient(create_app(config), base_url="http://localhost") as client:
        yield client


def work(store):
    task = store.claim()
    assert task is not None
    execute(task, store)
    return store.get(task["id"])


@pytest.fixture(scope="session")
def files(tmp_path_factory):
    directory = tmp_path_factory.mktemp("media")
    base = ["ffmpeg", "-v", "error", "-nostdin", "-y"]
    subprocess.run(
        base
        + [
            "-f",
            "lavfi",
            "-i",
            "color=c=orange:s=160x90:r=12",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100",
            "-t",
            "1.2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(directory / "sample.mp4"),
        ],
        check=True,
    )
    subprocess.run(
        base
        + [
            "-i",
            str(directory / "sample.mp4"),
            "-an",
            "-c:v",
            "copy",
            str(directory / "video.mp4"),
        ],
        check=True,
    )
    subprocess.run(
        base
        + [
            "-i",
            str(directory / "sample.mp4"),
            "-vn",
            "-c:a",
            "copy",
            str(directory / "audio.m4a"),
        ],
        check=True,
    )
    Image.new("RGBA", (64, 48), (255, 0, 0, 80)).save(directory / "transparent.png")
    Image.new("RGB", (50, 30), "orange").save(directory / "sample.jpg")
    frames = [Image.new("RGB", (64, 48), color) for color in ("orange", "navy", "yellow")]
    frames[0].save(
        directory / "animated.gif", save_all=True, append_images=frames[1:], duration=120, loop=0
    )
    return directory


@pytest.fixture
def media_server(files):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(files))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
