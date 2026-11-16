import pytest
from PIL import Image
from service import media
from service.api import Parameters


@pytest.mark.parametrize(
    "output", ["mp4", "webm", "mkv", "mov", "mp3", "m4a", "wav", "flac", "ogg", "gif"]
)
def test_convert_and_fully_decode(files, tmp_path, output):
    source = files / "sample.mp4"
    path, metadata = media.convert(
        source,
        media.probe(source),
        Parameters(output=output, duration=0.5, width=160).model_dump(),
        tmp_path,
    )
    assert path.stat().st_size > 0
    assert metadata["kind"] == (
        "animation" if output == "gif" else "audio" if output in media.AUDIO else "video"
    )
    if output in media.AUDIO:
        assert metadata["has_audio"]
    if output == "gif":
        with Image.open(path) as image:
            assert image.width <= 160 and image.n_frames > 1


@pytest.mark.parametrize("output", ["jpg", "png", "webp"])
def test_image_contents_and_transparency(files, tmp_path, output):
    source = files / "transparent.png"
    path, metadata = media.convert(
        source, media.probe(source), Parameters(output=output).model_dump(), tmp_path
    )
    assert metadata["width"] == 64 and metadata["height"] == 48
    with Image.open(path) as result:
        assert result.format == {"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[output]
        assert metadata["transparent"] is (output != "jpg")


def test_animation_is_preserved_in_video(files, tmp_path):
    source = files / "animated.gif"
    metadata = media.probe(source)
    assert metadata["kind"] == "animation"
    assert "png" not in {c["id"] for c in media.capabilities(metadata)}
    _, result = media.convert(source, metadata, Parameters(output="mp4").model_dump(), tmp_path)
    assert result["kind"] == "video"


def test_mislabeled_text_rejected(tmp_path):
    path = tmp_path / "fake.mp4"
    path.write_text("not video")
    with pytest.raises(media.ServiceError):
        media.probe(path)


def test_capabilities_follow_installed_encoders(monkeypatch):
    monkeypatch.setattr(media, "encoders", lambda: {"aac"})
    assert [c["id"] for c in media.capabilities({"kind": "video", "has_audio": True})] == ["m4a"]
