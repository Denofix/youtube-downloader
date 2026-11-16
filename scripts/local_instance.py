"""Disposable API + worker for integration checks; never touches the owner's data."""

import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import httpx


@contextmanager
def running_instance(worker_script: Path | None = None):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="download-convert-check-") as temporary:
        env = os.environ | {
            "DATA_DIR": temporary,
            "PYTHONPATH": str(root / "backend"),
            "ALLOWED_HOSTS": "localhost,127.0.0.1",
        }
        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "service.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        worker = None
        base = "http://127.0.0.1:" + str(port)
        try:
            with httpx.Client(base_url=base, trust_env=False, timeout=1) as client:
                for _ in range(50):
                    try:
                        if client.get("/api/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("The disposable API did not start.")
            worker = subprocess.Popen(
                [sys.executable, str(worker_script)]
                if worker_script
                else [sys.executable, "-m", "service.worker"],
                cwd=root,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            yield base
        finally:
            for process in (worker, api):
                if process is None:
                    continue
                process.terminate()
                try:
                    process.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
