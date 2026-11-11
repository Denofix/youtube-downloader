import fcntl
import os
import signal
import subprocess
import sys
import time

from .store import Store


def disk_usage(root):
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:
            pass
    return total


def stop_process(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    except ProcessLookupError:
        process.wait()


def run_task(task, store, stopping=lambda: False):
    process = subprocess.Popen(
        [sys.executable, "-m", "service.runner", task["id"]],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    started, heartbeat, error = time.monotonic(), 0, None
    try:
        while process.poll() is None:
            if time.monotonic() - heartbeat > 1:
                store.heartbeat()
                heartbeat = time.monotonic()
            if store.get(task["id"])["cancel_requested"]:
                error = {"code": "cancelled", "message": "Task cancelled."}
                break
            if stopping():
                error = {
                    "code": "worker_interrupted",
                    "message": "The worker stopped. Retry this task.",
                }
                break
            if time.monotonic() - started > store.config.job_timeout:
                error = {
                    "code": "timeout",
                    "message": "The task exceeded the time limit. Try a smaller file or shorter clip.",
                }
                break
            if disk_usage(store.config.data_dir / "files") > store.config.max_storage_bytes:
                error = {
                    "code": "storage_full",
                    "message": "The storage limit was reached. Wait for old results to expire.",
                }
                break
            time.sleep(0.2)
    finally:
        stop_process(process)
    if store.get(task["id"])["state"] == "running":
        store.finish(
            task["id"],
            "failed",
            error=error
            or {
                "code": "worker_error",
                "message": "The processing tool stopped unexpectedly. Retry this task.",
            },
        )
    if store.get(task["id"])["state"] != "completed":
        store.discard_task_files(task["id"])


def main():
    store, stopping = Store(), False

    def shutdown(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    with (store.config.data_dir / "worker.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit("Another worker already uses this data directory.")
        store.recover()
        while not stopping:
            store.heartbeat()
            store.cleanup()
            task = store.claim()
            if task:
                run_task(task, store, lambda: stopping)
            else:
                time.sleep(0.5)


if __name__ == "__main__":
    main()
