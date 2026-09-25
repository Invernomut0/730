from pathlib import Path

from PIL import Image

from app.services.thumbnails import generate_thumbnail, thumbnail_path


def test_generates_and_reuses_bounded_png_thumbnail(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.png"
    Image.new("RGB", (1200, 800), color="white").save(source)
    destination = thumbnail_path(tmp_path, "a" * 64)

    assert generate_thumbnail(source, "image/png", destination) == destination
    with Image.open(destination) as preview:
        assert preview.format == "PNG"
        assert preview.width <= 360
        assert preview.height <= 480
    assert generate_thumbnail(source, "image/png", destination) == destination
