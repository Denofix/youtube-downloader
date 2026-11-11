import time
from dataclasses import replace

from conftest import work
from service import sources
from service.api import create_app
from service.store import Store


def inspect(client, store, path):
    task = client.post(
        "/api/uploads", content=path.read_bytes(), headers={"X-Filename": path.name}
    ).json()
    finished = work(store)
    assert finished["state"] == "completed", finished
    assert finished["id"] == task["id"]
    return client.get("/api/assets/" + finished["result"]["asset_id"]).json()


def test_uploaded_video_to_delivered_mp3(client, store, files):
    asset = inspect(client, store, files / "sample.mp4")
    response = client.post(
        "/api/conversions",
        json={"asset_id": asset["id"], "parameters": {"output": "mp3", "bitrate": 192}},
    )
    assert response.status_code == 202
    finished = work(store)
    assert finished["state"] == "completed", finished
    asset_id = finished["result"]["asset_id"]
    result = client.get("/api/assets/" + asset_id).json()
    assert result["metadata"]["kind"] == "audio" and result["metadata"]["audio_codec"] == "mp3"
    assert client.get(f"/api/assets/{asset_id}/file").content.startswith(b"ID3")
    tasks = client.get("/api/tasks").json()
    assert len(tasks) == 2 and "payload" not in tasks[0]
    assert create_app(store.config).state.store.get(finished["id"])["state"] == "completed"


def test_silent_video_cannot_convert_to_audio(client, store, files):
    asset = inspect(client, store, files / "video.mp4")
    assert "mp3" not in {p["id"] for p in asset["operations"]}
    assert (
        client.post(
            "/api/conversions", json={"asset_id": asset["id"], "parameters": {"output": "mp3"}}
        ).status_code
        == 400
    )


def test_format_belongs_to_completed_analysis(client, store, monkeypatch):
    monkeypatch.setattr(
        sources,
        "analyze",
        lambda *a: {
            "title": "Test",
            "choices": [{"id": "option_0", "has_audio": True, "operation": "download"}],
        },
    )
    task = client.post("/api/analyze", json={"url": "https://youtu.be/BaW_jenozKc"}).json()
    assert (
        client.post(
            "/api/downloads", json={"analysis_id": task["id"], "choice_id": "option_0"}
        ).status_code
        == 400
    )
    work(store)
    response = client.post(
        "/api/downloads", json={"analysis_id": task["id"], "choice_id": "option_2"}
    )
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_format"


def test_cancel_retry_recovery_and_claim(client, store):
    queued = store.create("analyze", "Test", {"url": "https://youtu.be/BaW_jenozKc"})
    assert store.claim()["id"] == queued["id"]
    assert Store(store.config).claim() is None
    client.post(f"/api/tasks/{queued['id']}/cancel")
    assert not store.finish(queued["id"], "completed", result={})
    assert store.get(queued["id"])["state"] == "cancelled"
    retry = client.post(f"/api/tasks/{queued['id']}/retry")
    assert retry.status_code == 202
    store.claim()
    store.recover()
    assert store.get(retry.json()["id"])["error"]["code"] == "worker_interrupted"
    other = store.create("analyze", "Queued", {})
    client.post(f"/api/tasks/{other['id']}/cancel")
    assert store.claim() is None


def test_limits_and_validation(client, config):
    from fastapi.testclient import TestClient

    with TestClient(
        create_app(replace(config, max_file_bytes=4)), base_url="http://localhost"
    ) as limited:
        assert limited.post("/api/uploads", content=b"oversized").status_code == 413
    assert not list((config.data_dir / "files").rglob("input"))
    assert client.post("/api/uploads", content=b"").status_code == 400
    for parameters in (
        {"output": "gif", "duration": 99},
        {"output": "gif", "start": "NaN"},
        {"output": "mp3", "command": "arbitrary"},
    ):
        assert (
            client.post(
                "/api/conversions", json={"asset_id": "a" * 32, "parameters": parameters}
            ).status_code
            == 422
        )
    assert client.post("/api/analyze", json={"url": "http://127.0.0.1"}).status_code == 400
    assert (
        client.post("/api/analyze", json={"url": "https://pinterest.com/pin/123"}).json()["detail"][
            "code"
        ]
        == "platform_planned"
    )
    assert (
        client.post(
            "/api/analyze",
            json={"url": "https://youtu.be/BaW_jenozKc"},
            headers={"Origin": "https://foreign.example"},
        ).status_code
        == 403
    )


def test_expiry_protects_running_input(client, store, files):
    asset = inspect(client, store, files / "transparent.png")
    path = store.asset(asset["id"])["path"]
    task = store.create("convert", "Convert", {"asset_id": asset["id"]})
    with store.connect() as db:
        db.execute("UPDATE assets SET expires_at=? WHERE id=?", (time.time() - 5, asset["id"]))
    assert client.get(f"/api/assets/{asset['id']}/file").status_code == 410
    store.cleanup()
    assert path.exists()
    store.cancel(task["id"])
    store.cleanup()
    assert not path.exists()


def test_bad_upload_has_controlled_failure(client, store):
    client.post("/api/uploads", content=b"not media", headers={"X-Filename": "fake.mp4"})
    task = work(store)
    assert task["state"] == "failed" and task["error"]["code"] == "media_tool_error"


def test_paths_and_duplicates_are_isolated(client, store, files):
    first = inspect(client, store, files / "sample.jpg")
    second = inspect(client, store, files / "sample.jpg")
    assert first["id"] != second["id"]
    assert store.asset(first["id"])["path"].parent != store.asset(second["id"])["path"].parent
    assert "path" not in first
    assert client.get("/api/assets/" + "0" * 32).status_code == 410


def test_worker_heartbeat_is_visible(client, store):
    assert not client.get("/api/health").json()["worker_online"]
    store.heartbeat()
    assert client.get("/api/health").json()["worker_online"]
