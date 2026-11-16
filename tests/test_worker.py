import subprocess
import sys
from dataclasses import replace

from service import worker
from service.store import Store


def sleeping_tool(monkeypatch):
    actual, processes = subprocess.Popen, []

    def start(*args, **kwargs):
        process = actual([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(worker.subprocess, "Popen", start)
    return processes


def test_cancel_kills_process_and_cleans_partial_files(store, monkeypatch):
    store.create("analyze", "Cancel", {})
    task = store.claim()
    directory = store.config.data_dir / "files" / task["id"]
    directory.mkdir()
    (directory / "partial.part").write_text("partial")
    store.cancel(task["id"])
    processes = sleeping_tool(monkeypatch)
    worker.run_task(task, store)
    assert processes[0].poll() is not None
    assert store.get(task["id"])["state"] == "cancelled" and not directory.exists()


def test_timeout_kills_tool(config, monkeypatch):
    store = Store(replace(config, job_timeout=0))
    store.create("analyze", "Timeout", {})
    task = store.claim()
    processes = sleeping_tool(monkeypatch)
    worker.run_task(task, store)
    assert processes[0].poll() is not None
    assert store.get(task["id"])["error"]["code"] == "timeout"
