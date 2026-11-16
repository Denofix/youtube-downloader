import hashlib
import io
import json
import time
import zipfile
from copy import deepcopy
from urllib.error import HTTPError

import pytest
from conftest import work
from PIL import Image
from service import photos, sources
from service.errors import ServiceError
from yt_dlp.extractor.tiktok import TikTokIE

URL = "https://www.tiktok.com/@test.creator/photo/7100000000000000001"


@pytest.fixture
def photo_post(files, media_server, monkeypatch):
    Image.new("RGB", (80, 60), "navy").save(files / "photo.webp")
    entries = [("sample.jpg", 50, 30), ("transparent.png", 64, 48), ("photo.webp", 80, 60)]
    post = {
        "id": "7100000000000000001",
        "desc": "Owned / photos .. test",
        "author": {"uniqueId": "test.creator"},
        "imagePost": {
            "images": [
                {
                    "imageWidth": w,
                    "imageHeight": h,
                    "imageURL": {"urlList": [media_server + "/" + name + "?signed=SECRET"]},
                }
                for name, w, h in entries
            ]
        },
    }
    monkeypatch.setattr(TikTokIE, "_extract_web_data_and_status", lambda *args: (deepcopy(post), 0))
    real_check = photos.check_media_url
    monkeypatch.setattr(
        photos,
        "check_media_url",
        lambda u: u if isinstance(u, str) and u.startswith(media_server + "/") else real_check(u),
    )
    return post


def analyze(client, store):
    queued = client.post("/api/analyze", json={"url": URL})
    assert queued.status_code == 202
    task = work(store)
    assert task["state"] == "completed", task
    return task


def test_photo_urls_and_share_redirect_are_supported(monkeypatch):
    assert sources.validate_url(URL + "/?share=1") == URL

    class Redirect:
        def open(self, request, timeout):
            raise HTTPError(request.full_url, 302, "Found", {"Location": URL}, io.BytesIO())

    monkeypatch.setattr(sources, "build_opener", lambda *args: Redirect())
    assert sources.resolve_url("https://vt.tiktok.com/Photos/") == URL


def test_photo_snapshot_selected_files_zip_and_restart(client, store, photo_post, files):
    task = analyze(client, store)
    public = client.get("/api/tasks/" + task["id"]).json()
    encoded = json.dumps(public)
    assert "SECRET" not in encoded and "_images" not in encoded and "urlList" not in encoded
    assert public["result"]["kind"] == "photos" and public["result"]["item_count"] == 3
    for item in public["result"]["items"]:
        response = client.get("/api/assets/" + item["preview_asset_id"] + "/preview")
        assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
        with Image.open(io.BytesIO(response.content)) as image:
            assert max(image.size) <= 320
    queued = client.post(
        "/api/photo-downloads", json={"analysis_id": task["id"], "item_ids": ["photo_3", "photo_1"]}
    )
    assert queued.status_code == 202
    from service.store import Store

    finished = work(Store(store.config))
    assert finished["state"] == "completed", finished
    delivered = finished["result"]["files"]
    assert [p["item_id"] for p in delivered] == ["photo_1", "photo_3"]
    expected = [(files / "sample.jpg").read_bytes(), (files / "photo.webp").read_bytes()]
    for item, content in zip(delivered, expected):
        assert client.get("/api/assets/" + item["asset_id"] + "/file").content == content
    archive = client.get("/api/assets/" + finished["result"]["archive_asset_id"] + "/file")
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
        assert z.testzip() is None
        assert z.namelist() == [p["name"] for p in delivered]
        assert [z.read(name) for name in z.namelist()] == expected
        assert all("/" not in name and "\\" not in name for name in z.namelist())
        assert all(p.compress_type == zipfile.ZIP_STORED for p in z.infolist())
    assert (
        client.post(
            "/api/conversions",
            json={
                "asset_id": finished["result"]["archive_asset_id"],
                "parameters": {"output": "png"},
            },
        ).status_code
        == 400
    )


def test_single_photo_can_be_converted_without_zip(client, store, photo_post):
    analysis = analyze(client, store)
    client.post(
        "/api/photo-downloads", json={"analysis_id": analysis["id"], "item_ids": ["photo_2"]}
    )
    result = work(store)
    assert result["state"] == "completed", result
    assert "archive_asset_id" not in result["result"]
    item = result["result"]["files"][0]
    assert (
        client.post(
            "/api/conversions", json={"asset_id": item["asset_id"], "parameters": {"output": "jpg"}}
        ).status_code
        == 202
    )
    converted = work(store)
    assert converted["state"] == "completed", converted
    with Image.open(
        io.BytesIO(client.get("/api/assets/" + converted["result"]["asset_id"] + "/file").content)
    ) as image:
        assert image.format == "JPEG" and image.size == (64, 48)


@pytest.mark.parametrize(
    "selection", [[], ["photo_0"], ["photo_99"], ["photo_1", "photo_1"], ["../photo_1"]]
)
def test_selection_is_bound_and_unique(client, store, photo_post, selection):
    analysis = analyze(client, store)
    assert client.post(
        "/api/photo-downloads", json={"analysis_id": analysis["id"], "item_ids": selection}
    ).status_code in {400, 422}
    assert store.claim() is None


def test_expiry_protects_only_queued_photo_inputs(client, store, photo_post):
    analysis = analyze(client, store)
    items = analysis["result"]["items"]
    kept = store.asset(items[0]["source_asset_id"])["path"]
    discarded = store.asset(items[1]["source_asset_id"])["path"]
    client.post(
        "/api/photo-downloads", json={"analysis_id": analysis["id"], "item_ids": ["photo_1"]}
    )
    with store.connect() as db:
        db.execute("UPDATE assets SET expires_at=?", (time.time() - 1,))
    store.cleanup()
    assert kept.exists() and not discarded.exists()
    result = work(store)
    assert result["state"] == "completed", result
    file_id = result["result"]["files"][0]["asset_id"]
    store.cleanup()
    assert not kept.exists() and client.get("/api/assets/" + file_id + "/file").status_code == 200


def test_expired_analysis_and_sources_require_new_analysis(client, store, photo_post):
    analysis = analyze(client, store)
    with store.connect() as db:
        db.execute("UPDATE tasks SET expires_at=? WHERE id=?", (time.time() - 1, analysis["id"]))
    response = client.post(
        "/api/photo-downloads", json={"analysis_id": analysis["id"], "item_ids": ["photo_1"]}
    )
    assert response.status_code == 400 and response.json()["detail"]["code"] == "analysis_expired"


def test_changed_cached_photo_does_not_publish_partial_results(client, store, photo_post):
    analysis = analyze(client, store)
    target = store.asset(analysis["result"]["items"][1]["source_asset_id"])["path"]
    target.write_bytes(b"corrupted")
    queued = client.post(
        "/api/photo-downloads",
        json={"analysis_id": analysis["id"], "item_ids": ["photo_1", "photo_2"]},
    ).json()
    result = work(store)
    assert result["state"] == "failed" and result["error"]["code"] == "photo_snapshot_changed"
    assert result["result"] is None
    assert not (store.config.data_dir / "files" / queued["id"]).exists()
    with store.connect() as db:
        assert (
            db.execute("SELECT count(*) FROM assets WHERE task_id=?", (queued["id"],)).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    "change,code",
    [
        ("dimensions", "quality_mismatch"),
        ("too_many", "photo_limit"),
        ("pixel_limit", "image_limit"),
        ("watermark", "photo_source_unavailable"),
        ("missing", "photo_source_unavailable"),
    ],
)
def test_invalid_source_rejects_the_whole_analysis(client, store, photo_post, change, code):
    images = photo_post["imagePost"]["images"]
    if change == "dimensions":
        images[1]["imageWidth"] = 65
    if change == "too_many":
        images.extend(deepcopy(images[0]) for _ in range(photos.MAX_ITEMS))
    if change == "pixel_limit":
        images[0]["imageWidth"] = 1000000
    if change == "watermark":
        images[0]["hasWatermark"] = True
    if change == "missing":
        images[0]["imageURL"]["urlList"] = []
    client.post("/api/analyze", json={"url": URL})
    result = work(store)
    assert result["state"] == "failed", result
    assert result["error"]["code"] == code
    assert not (store.config.data_dir / "files" / result["id"]).exists()
    assert "SECRET" not in json.dumps(client.get("/api/tasks").json())


@pytest.mark.parametrize(
    "url",
    [
        "http://p16.tiktokcdn.com/photo.jpg",
        "https://p16.tiktokcdn.com.evil.example/x",
        "https://evil.example/tiktokcdn.com/x",
        "https://user:password@p16.tiktokcdn.com/x",
        "https://p16.tiktokcdn.com:444/x",
        "https://127.0.0.1/x",
        "file:///etc/passwd",
        "https://p16.tiktokcdn.com/\nx",
    ],
)
def test_photo_media_hosts_are_restricted(url):
    with pytest.raises(ServiceError):
        photos.check_media_url(url)


def test_photo_redirect_is_checked_before_following(tmp_path, monkeypatch):
    calls = []

    class Redirect:
        def open(self, request, timeout):
            calls.append(request.full_url)
            raise HTTPError(
                request.full_url,
                302,
                "Found",
                {"Location": "http://169.254.169.254/private"},
                io.BytesIO(),
            )

    monkeypatch.setattr(photos, "build_opener", lambda *args: Redirect())
    with pytest.raises(ServiceError):
        photos.fetch_image(["https://p16.tiktokcdn.com/image"], tmp_path / "image", 1024)
    assert len(calls) == 1


def test_original_snapshot_hash_is_real(client, store, photo_post):
    result = analyze(client, store)
    for item in result["result"]["items"]:
        original = store.asset(item["source_asset_id"])
        assert hashlib.sha256(original["path"].read_bytes()).hexdigest() == item["sha256"]


def test_source_byte_limit_discards_partial_analysis(client, store, photo_post):
    from dataclasses import replace

    from service.store import Store

    client.post("/api/analyze", json={"url": URL})
    result = work(Store(replace(store.config, max_file_bytes=100)))
    assert result["state"] == "failed" and result["error"]["code"] == "file_limit"
    assert not (store.config.data_dir / "files" / result["id"]).exists()


def test_combined_photo_limit_discards_registered_earlier_items(client, store, photo_post, files):
    from dataclasses import replace

    from service.store import Store

    Image.new("RGB", (400, 400), "orange").save(files / "large.jpg")
    assert (files / "large.jpg").stat().st_size < 5000
    images = photo_post["imagePost"]["images"]
    template = deepcopy(images[0])
    template.update({"imageWidth": 400, "imageHeight": 400})
    template["imageURL"]["urlList"] = [
        template["imageURL"]["urlList"][0].replace("sample.jpg", "large.jpg")
    ]
    images[:] = [deepcopy(template), deepcopy(template)]
    client.post("/api/analyze", json={"url": URL})
    result = work(Store(replace(store.config, max_file_bytes=5000)))
    assert result["state"] == "failed" and result["error"]["code"] == "file_limit"
    with store.connect() as db:
        assert (
            db.execute("SELECT count(*) FROM assets WHERE task_id=?", (result["id"],)).fetchone()[0]
            == 0
        )


def test_undeclared_stream_cannot_exceed_photo_limit(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        code = 200
        headers = {}

    class Opener:
        def open(self, *args, **kwargs):
            return Response(b"x" * 1000)

    monkeypatch.setattr(photos, "build_opener", lambda *args: Opener())
    target = tmp_path / "image"
    with pytest.raises(ServiceError) as error:
        photos.fetch_image(["https://p16.tiktokcdn.com/image"], target, 100)
    assert error.value.code == "file_limit" and not target.exists()
