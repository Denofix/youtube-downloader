"""Content-based compatibility checks against actual files, codecs, pixels and sound."""

import shutil

import pytest
from conftest import work
from conversion_fixtures import MATRIX, build_fixtures, check_result
from PIL import Image
from service import media
from service.api import Parameters
from test_api_and_queue import inspect


@pytest.fixture(scope="session")
def conversion_files(tmp_path_factory):
    return build_fixtures(tmp_path_factory.mktemp("conversion-matrix"))


@pytest.mark.parametrize("name,output", MATRIX, ids=[f"{name}-to-{out}" for name, out in MATRIX])
def test_actual_conversion_matrix(conversion_files, tmp_path, name, output):
    source = conversion_files / name
    metadata = media.probe(source)
    target, result = media.convert(
        source, metadata, Parameters(output=output, duration=0.3, width=160).model_dump(), tmp_path
    )
    check_result(source, target, metadata, result, output)


@pytest.mark.parametrize(
    "name", ["silent.mp4", "portrait.mp4", "odd.mkv", "animated.gif", "image.png"]
)
def test_no_audio_operations_without_audio(conversion_files, name):
    metadata = media.probe(conversion_files / name)
    assert not metadata["has_audio"]
    assert not set(media.AUDIO).intersection(c["id"] for c in media.capabilities(metadata))
    with pytest.raises(media.ServiceError, match="not supported"):
        media.validate_conversion(metadata, Parameters(output="mp3").model_dump())


def test_content_detection_ignores_extension_and_handles_unicode(conversion_files, tmp_path):
    source = tmp_path / "тест відео - incorrectly named.jpg"
    shutil.copyfile(conversion_files / "video.mp4", source)
    assert media.probe(source)["kind"] == "video"
    target, result = media.convert(
        source, media.probe(source), Parameters(output="mp3").model_dump(), tmp_path
    )
    assert result["audio_codec"] == "mp3" and target.stat().st_size > 0


def test_metadata_exposes_display_size_and_animation_duration(conversion_files):
    for name, size in (("oriented.jpg", (48, 64)), ("rotated.mov", (90, 160))):
        metadata = media.probe(conversion_files / name)
        assert (metadata["display_width"], metadata["display_height"]) == size
    gif = media.probe(conversion_files / "animated.gif")
    assert gif["frames"] == 3 and gif["duration"] == pytest.approx(0.36)


def test_non_gif_animation_has_clear_failure(conversion_files):
    with pytest.raises(media.ServiceError) as error:
        media.probe(conversion_files / "animated.webp")
    assert error.value.code == "unsupported_animation"


def test_truncated_pixels_are_not_published_as_valid_image(conversion_files, tmp_path):
    source = tmp_path / "truncated.jpg"
    data = (conversion_files / "image.jpg").read_bytes()
    # Header remains readable, but actual JPEG entropy data is incomplete.
    source.write_bytes(data[:-50])
    with Image.open(source) as image:
        assert image.size == (64, 48)
    with pytest.raises(media.ServiceError) as error:
        media.verify(source)
    assert error.value.code == "invalid_image"


def test_matrix_through_upload_queue_http_and_reuse(client, store, conversion_files):
    asset = inspect(client, store, conversion_files / "rotated.mov")
    assert (asset["metadata"]["display_width"], asset["metadata"]["display_height"]) == (90, 160)
    response = client.post(
        "/api/conversions", json={"asset_id": asset["id"], "parameters": {"output": "mp4"}}
    )
    assert response.status_code == 202
    finished = work(store)
    assert finished["state"] == "completed", finished
    result_id = finished["result"]["asset_id"]
    result = client.get(f"/api/assets/{result_id}").json()
    assert (result["metadata"]["width"], result["metadata"]["height"]) == (90, 160)
    assert client.get(f"/api/assets/{result_id}/file").content
    response = client.post(
        "/api/conversions", json={"asset_id": result_id, "parameters": {"output": "mp3"}}
    )
    assert response.status_code == 202
    assert work(store)["state"] == "completed"
