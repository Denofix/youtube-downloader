"""Native Instagram product shapes with actual owned images/video and retained delivery."""

import io
import json
import time
import zipfile
from copy import deepcopy
from dataclasses import replace

import pytest
from conftest import work
from PIL import Image
from service import photos
from service.errors import ServiceError
from service.store import Store
from yt_dlp.extractor.instagram import InstagramIE, _id_to_pk
from yt_dlp.utils import ExtractorError

URL = "https://www.instagram.com/p/OwnedPost01/"


@pytest.fixture
def publication(monkeypatch, media_server):
    def image(code, filename, width, height):
        return {
            "pk": str(_id_to_pk(code)),
            "media_type": 1,
            "image_versions2": {
                "candidates": [
                    {
                        "url": media_server + "/" + filename + "?signed=SECRET",
                        "width": width,
                        "height": height,
                    }
                ]
            },
        }

    first = image("OwnedImg01", "sample.jpg", 50, 30)
    third = image("OwnedImg03", "transparent.png", 64, 48)
    second = image("OwnedVid02", "sample.jpg", 50, 30) | {
        "media_type": 2,
        "has_audio": True,
        "video_codec": "h264",
        "video_duration": 1.2,
        "video_versions": [
            {
                "id": "muxed",
                "url": media_server + "/sample.mp4?video=SECRET",
                "width": 160,
                "height": 90,
            }
        ],
    }
    state = {
        "calls": 0,
        "error": None,
        "mode": "mixed",
        "post": {
            "pk": str(_id_to_pk("OwnedPost01")),
            "media_type": 8,
            "caption": {"text": "Owned Instagram post / .. fixture"},
            "user": {"username": "owned.creator", "full_name": "Owned creator"},
            "carousel_media_count": 3,
            "carousel_media": [first, second, third],
        },
    }

    def extract(self, url):
        assert url == URL
        state["calls"] += 1
        if state["error"]:
            raise ExtractorError(state["error"], expected=True)
        data = deepcopy(state["post"])
        if state["mode"] == "single":
            data = {
                k: v for k, v in data.items() if k not in {"carousel_media", "carousel_media_count"}
            }
            data.update(deepcopy(first))
            data["pk"] = str(_id_to_pk("OwnedPost01"))
        elif state["mode"] == "single_video":
            data = {
                k: v for k, v in data.items() if k not in {"carousel_media", "carousel_media_count"}
            }
            data.update(deepcopy(second))
            data["pk"] = str(_id_to_pk("OwnedPost01"))
        elif state["mode"] == "photos":
            data["carousel_media"][1] = deepcopy(first) | {"pk": str(_id_to_pk("OwnedImg02"))}
        elif state["mode"] == "videos":
            data["carousel_media"] = [
                deepcopy(second) | {"pk": str(_id_to_pk(code))}
                for code in ("OwnedVid01", "OwnedVid02", "OwnedVid03")
            ]
        return self._extract_product(data, video_id="OwnedPost01", get_comments=False)

    monkeypatch.setattr(InstagramIE, "_real_initialize", lambda self: None)
    monkeypatch.setattr(InstagramIE, "_real_extract", extract)
    real_check = photos.check_media_url
    monkeypatch.setattr(
        photos,
        "check_media_url",
        lambda url, platform="TikTok": (
            url
            if isinstance(url, str) and url.startswith(media_server + "/")
            else real_check(url, platform)
        ),
    )
    return state


def analyze(client, store):
    response = client.post("/api/analyze", json={"url": URL + "?igsh=tracking"})
    assert response.status_code == 202
    task = work(store)
    assert task["state"] == "completed", task
    return task


def selection(task, positions, profile="original"):
    result = []
    for item in task["result"]["items"]:
        if item["position"] not in positions:
            continue
        entry = {"item_id": item["id"]}
        if item.get("kind") == "video":
            entry.update(
                {
                    "choice_id": next(c["id"] for c in item["choices"] if c["kind"] == "video"),
                    "profile": profile,
                }
            )
        result.append(entry)
    return result


def deliver(client, store, task, positions, profile="original"):
    body = {"analysis_id": task["id"], "selections": selection(task, positions, profile)}
    response = client.post("/api/post-downloads", json=body)
    assert response.status_code == 202, response.text
    return work(store)


@pytest.mark.parametrize("mode", ["single", "photos"])
def test_instagram_original_photo_selection_and_conversion(client, store, files, publication, mode):
    publication["mode"] = mode
    task = analyze(client, store)
    assert task["result"]["kind"] == "photos"
    encoded = json.dumps(client.get(f"/api/tasks/{task['id']}").json())
    assert "SECRET" not in encoded and "_images" not in encoded
    ids = ["photo_1"] if mode == "single" else ["photo_3", "photo_1"]
    response = client.post(
        "/api/photo-downloads", json={"analysis_id": task["id"], "item_ids": ids}
    )
    assert response.status_code == 202
    result = work(Store(store.config))
    assert result["state"] == "completed", result
    returned = result["result"]["files"]
    assert [f["position"] for f in returned] == ([1] if mode == "single" else [1, 3])
    assert (
        client.get(f"/api/assets/{returned[0]['asset_id']}/file").content
        == (files / "sample.jpg").read_bytes()
    )
    if mode == "photos":
        archive = client.get(f"/api/assets/{result['result']['archive_asset_id']}/file")
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
            assert z.namelist() == [f["name"] for f in returned]
            assert z.read(z.namelist()[1]) == (files / "transparent.png").read_bytes()
    response = client.post(
        "/api/conversions",
        json={"asset_id": returned[0]["asset_id"], "parameters": {"output": "png"}},
    )
    assert response.status_code == 202 and work(store)["state"] == "completed"
    assert publication["calls"] == 1


@pytest.mark.parametrize("profile", ["original", "mp3", "compatible"])
def test_mixed_post_real_files_source_order_zip_and_no_url_leak(
    client, store, files, publication, profile
):
    task = analyze(client, store)
    assert task["result"]["kind"] == "gallery"
    assert [i["kind"] for i in task["result"]["items"]] == ["image", "video", "image"]
    public = json.dumps(client.get(f"/api/tasks/{task['id']}").json())
    assert "SECRET" not in public and "_entries" not in public and "127.0.0.1" not in public
    body = {
        "analysis_id": task["id"],
        "selections": list(reversed(selection(task, [1, 2], profile))),
    }
    assert client.post("/api/post-downloads", json=body).status_code == 202
    result = work(Store(store.config))
    assert result["state"] == "completed", result
    returned = result["result"]["files"]
    assert [f["position"] for f in returned] == [1, 2]
    assert returned[1]["kind"] == ("audio" if profile == "mp3" else "video")
    with zipfile.ZipFile(
        io.BytesIO(client.get(f"/api/assets/{result['result']['archive_asset_id']}/file").content)
    ) as z:
        assert z.testzip() is None and z.namelist() == [f["name"] for f in returned]
        assert all("/" not in name and "\\" not in name for name in z.namelist())
        assert z.read(returned[0]["name"]) == (files / "sample.jpg").read_bytes()
        for item in returned:
            assert (
                z.read(item["name"]) == client.get(f"/api/assets/{item['asset_id']}/file").content
            )
            assert client.get(f"/api/assets/{item['preview_asset_id']}/preview").status_code == 200
    metadata = store.asset(returned[1]["asset_id"])["metadata"]
    if profile != "mp3":
        assert (metadata["width"], metadata["height"]) == (160, 90)
    assert metadata["has_audio"] and publication["calls"] == 2


def test_selected_images_from_mixed_post_use_the_retained_snapshot(client, store, publication):
    task = analyze(client, store)
    publication["error"] = "login required"
    result = deliver(client, store, task, [3, 1])
    assert result["state"] == "completed", result
    assert [f["position"] for f in result["result"]["files"]] == [1, 3]
    assert publication["calls"] == 1


def test_multiple_carousel_videos_refresh_metadata_once(client, store, publication):
    publication["mode"] = "videos"
    task = analyze(client, store)
    result = deliver(client, store, task, [3, 1])
    assert result["state"] == "completed", result
    assert [f["position"] for f in result["result"]["files"]] == [1, 3]
    assert all(f["kind"] == "video" for f in result["result"]["files"])
    assert publication["calls"] == 2


@pytest.mark.parametrize("profile", ["original", "mp3"])
def test_native_progressive_video_audio_declaration_matches_on_refresh(
    client, store, publication, profile
):
    publication["mode"] = "single_video"
    task = analyze(client, store)
    assert task["result"]["kind"] == "video"
    choice = task["result"]["choices"][0]
    assert choice["has_audio"] and choice["audio_codec"] == "unknown"
    assert (
        client.post(
            "/api/downloads",
            json={"analysis_id": task["id"], "choice_id": choice["id"], "profile": profile},
        ).status_code
        == 202
    )
    result = work(store)
    assert result["state"] == "completed", result
    assert store.asset(result["result"]["asset_id"])["metadata"]["has_audio"]


@pytest.mark.parametrize("change", ["parent", "order", "identity", "kind", "quality", "audio"])
def test_gallery_refresh_rejects_source_changes_atomically(client, store, publication, change):
    task = analyze(client, store)
    post = publication["post"]
    if change == "parent":
        post["pk"] = str(_id_to_pk("ChangedPost"))
    elif change == "order":
        post["carousel_media"].reverse()
    elif change == "identity":
        post["carousel_media"][1]["pk"] = str(_id_to_pk("ChangedItem"))
    elif change == "kind":
        post["carousel_media"][1]["media_type"] = 1
    elif change == "quality":
        post["carousel_media"][1]["video_versions"][0]["width"] = 720
    elif change == "audio":
        post["carousel_media"][1]["has_audio"] = False
    result = deliver(client, store, task, [1, 2])
    assert result["state"] == "failed", result
    assert result["error"]["code"] in {"source_changed", "format_unavailable"}
    assert not list((store.config.data_dir / "files" / result["id"]).rglob("*"))
    with store.connect() as db:
        assert (
            db.execute("select count(*) from assets where task_id=?", (result["id"],)).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize("which", ["image", "poster"])
def test_changed_retained_post_image_is_not_published(client, store, publication, which):
    task = analyze(client, store)
    item = task["result"]["items"][0 if which == "image" else 1]
    snapshot = item if which == "image" else item["poster"]
    store.asset(snapshot["source_asset_id"])["path"].write_bytes(b"changed")
    result = deliver(client, store, task, [1, 2])
    assert result["state"] == "failed" and result["error"]["code"] == "photo_snapshot_changed"
    assert not list((store.config.data_dir / "files" / result["id"]).rglob("*"))


@pytest.mark.parametrize(
    "selections,code",
    [
        ([], 422),
        ([{"item_id": "media_1"}, {"item_id": "media_1"}], 400),
        ([{"item_id": "media_99"}], 400),
        ([{"item_id": "media_1", "profile": "mp3"}], 400),
        ([{"item_id": "media_1", "choice_id": "option_0"}], 400),
        ([{"item_id": "media_2"}], 400),
        ([{"item_id": "media_2", "choice_id": "option_999"}], 400),
        ([{"item_id": "media_2", "choice_id": "option_0", "bitrate": 999}], 422),
        ([{"item_id": "media_2", "choice_id": "option_0", "url": "http://127.0.0.1"}], 422),
    ],
)
def test_post_selection_is_server_owned(client, store, publication, selections, code):
    task = analyze(client, store)
    assert (
        client.post(
            "/api/post-downloads", json={"analysis_id": task["id"], "selections": selections}
        ).status_code
        == code
    )
    assert publication["calls"] == 1


def test_pending_gallery_inputs_survive_cleanup_until_cancelled(client, store, publication):
    task = analyze(client, store)
    response = client.post(
        "/api/post-downloads",
        json={"analysis_id": task["id"], "selections": selection(task, [1, 2])},
    )
    assert response.status_code == 202
    queued = store.get(response.json()["id"])
    paths = [store.asset(i)["path"] for i in queued["payload"]["asset_ids"]]
    with store.connect() as db:
        db.execute("update assets set expires_at=?", (time.time() - 5,))
    store.cleanup()
    assert all(p.exists() for p in paths)
    result = work(Store(store.config))
    assert result["state"] == "completed", result


def test_expired_analysis_or_input_requests_a_new_analysis(client, store, publication):
    task = analyze(client, store)
    item = task["result"]["items"][0]
    with store.connect() as db:
        db.execute(
            "update assets set expires_at=? where id=?", (time.time() - 5, item["source_asset_id"])
        )
    response = client.post(
        "/api/post-downloads", json={"analysis_id": task["id"], "selections": selection(task, [1])}
    )
    assert response.status_code == 400 and response.json()["detail"]["code"] == "analysis_expired"


def test_gallery_combined_archive_limit_discards_partial_files(client, store, publication):
    task = analyze(client, store)
    total = sum(i["size"] for i in task["result"]["items"] if i["kind"] == "image")
    store.config = replace(store.config, max_file_bytes=total + 1024)
    result = deliver(client, store, task, [1, 3])
    assert result["state"] == "failed" and result["error"]["code"] == "file_limit"
    assert not list((store.config.data_dir / "files" / result["id"]).rglob("*"))


def test_missing_remote_image_dimensions_are_measured_from_the_real_file(
    client, store, publication
):
    first = publication["post"]["carousel_media"][0]["image_versions2"]["candidates"][0]
    first.pop("width")
    first.pop("height")
    task = analyze(client, store)
    item = task["result"]["items"][0]
    assert (item["width"], item["height"]) == (50, 30)
    assert deliver(client, store, task, [1])["state"] == "completed"


def test_unknown_dimensions_still_enforce_the_actual_pixel_limit(
    client, store, publication, monkeypatch
):
    publication["mode"] = "single"
    first = publication["post"]["carousel_media"][0]["image_versions2"]["candidates"][0]
    first.pop("width")
    first.pop("height")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    client.post("/api/analyze", json={"url": URL})
    task = work(store)
    assert task["state"] == "failed" and task["error"]["code"] == "image_limit"
    assert not list((store.config.data_dir / "files" / task["id"]).rglob("*"))


@pytest.mark.parametrize("bad", ["count", "limit", "type", "duplicates", "pixels", "host"])
def test_incomplete_or_unsupported_posts_fail_before_publication(client, store, publication, bad):
    post = publication["post"]
    if bad == "count":
        post["carousel_media_count"] = 4
    elif bad == "limit":
        post["carousel_media"] *= 14
    elif bad == "type":
        post["carousel_media"][0]["media_type"] = 9
    elif bad == "duplicates":
        post["carousel_media"][1]["pk"] = post["carousel_media"][0]["pk"]
    elif bad == "pixels":
        post["carousel_media"][0]["image_versions2"]["candidates"][0]["width"] = 1000000
    elif bad == "host":
        post["carousel_media"][0]["image_versions2"]["candidates"][0]["url"] = (
            "https://evil.example/image.jpg"
        )
    client.post("/api/analyze", json={"url": URL})
    task = work(store)
    assert task["state"] == "failed", task
    assert not list((store.config.data_dir / "files" / task["id"]).rglob("*"))


@pytest.mark.parametrize(
    "url,platform,accepted",
    [
        ("https://scontent.cdninstagram.com/i.jpg", "Instagram", True),
        ("https://scontent.xx.fbcdn.net/i.jpg", "Instagram", True),
        ("https://scontent.cdninstagram.com/i.jpg", "TikTok", False),
        ("https://p.tiktokcdn.com/i.jpg", "Instagram", False),
        ("https://cdninstagram.com.evil.example/i.jpg", "Instagram", False),
        ("https://user:secret@scontent.cdninstagram.com/i.jpg", "Instagram", False),
        ("http://scontent.cdninstagram.com/i.jpg", "Instagram", False),
    ],
)
def test_photo_transport_is_platform_scoped(url, platform, accepted):
    if accepted:
        assert photos.check_media_url(url, platform) == url
    else:
        with pytest.raises(ServiceError):
            photos.check_media_url(url, platform)
