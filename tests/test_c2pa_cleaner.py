import shutil
import struct
import zlib
from pathlib import Path

import pytest

from core.c2pa_cleaner import PNG_SIGNATURE, remove_c2pa_data


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def jpeg_segment(marker: int, data: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(data) + 2) + data


PNG_WITHOUT_C2PA = (
    PNG_SIGNATURE
    + png_chunk(b"IHDR", b"\x00" * 13)
    + png_chunk(b"IDAT", b"bilddaten")
    + png_chunk(b"IEND", b"")
)

JPEG_WITHOUT_C2PA = (
    b"\xff\xd8"
    + jpeg_segment(0xE0, b"JFIF\x00")
    + jpeg_segment(0xDA, b"\x00" * 4) + b"scandaten"
    + b"\xff\xd9"
)


def test_png_cabx_chunk_is_removed(tmp_path):
    with_c2pa = (
        PNG_SIGNATURE
        + png_chunk(b"IHDR", b"\x00" * 13)
        + png_chunk(b"caBX", b"jumbf-manifest")
        + png_chunk(b"IDAT", b"bilddaten")
        + png_chunk(b"IEND", b"")
    )
    path = tmp_path / "bild.png"
    path.write_bytes(with_c2pa)

    assert remove_c2pa_data(path) is True
    assert path.read_bytes() == PNG_WITHOUT_C2PA


def test_jpeg_app11_segment_is_removed(tmp_path):
    with_c2pa = (
        b"\xff\xd8"
        + jpeg_segment(0xE0, b"JFIF\x00")
        + jpeg_segment(0xEB, b"JP jumbf c2pa")
        + jpeg_segment(0xDA, b"\x00" * 4) + b"scandaten"
        + b"\xff\xd9"
    )
    path = tmp_path / "bild.jpg"
    path.write_bytes(with_c2pa)

    assert remove_c2pa_data(path) is True
    assert path.read_bytes() == JPEG_WITHOUT_C2PA


def test_file_without_c2pa_is_left_untouched(tmp_path):
    path = tmp_path / "bild.png"
    path.write_bytes(PNG_WITHOUT_C2PA)
    assert remove_c2pa_data(path) is False
    assert path.read_bytes() == PNG_WITHOUT_C2PA


def test_wrong_content_for_extension_raises(tmp_path):
    path = tmp_path / "bild.png"
    path.write_bytes(JPEG_WITHOUT_C2PA)
    with pytest.raises(ValueError):
        remove_c2pa_data(path)


def test_unsupported_format_raises(tmp_path):
    path = tmp_path / "bild.gif"
    path.write_bytes(b"GIF89a")
    with pytest.raises(ValueError):
        remove_c2pa_data(path)


# ----------------------------------------------------------------------
# WebP
# ----------------------------------------------------------------------

def riff_chunk(fourcc: bytes, payload: bytes) -> bytes:
    padding = b"\x00" if len(payload) % 2 else b""
    return fourcc + struct.pack("<I", len(payload)) + payload + padding


def webp(*chunks: bytes) -> bytes:
    body = b"WEBP" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def test_webp_c2pa_chunk_is_removed_and_riff_size_fixed(tmp_path):
    image = riff_chunk(b"VP8 ", b"bilddaten")             # ungerade Länge: mit Füllbyte
    exif = riff_chunk(b"EXIF", b"exif")
    path = tmp_path / "bild.webp"
    path.write_bytes(webp(image, riff_chunk(b"C2PA", b"jumbf-manifest!"), exif))

    assert remove_c2pa_data(path) is True
    assert path.read_bytes() == webp(image, exif)


def test_webp_without_c2pa_is_left_untouched(tmp_path):
    original = webp(riff_chunk(b"VP8 ", b"bilddaten"))
    path = tmp_path / "bild.webp"
    path.write_bytes(original)
    assert remove_c2pa_data(path) is False
    assert path.read_bytes() == original


def test_truncated_webp_keeps_the_rest(tmp_path):
    manifest = riff_chunk(b"C2PA", b"manifest")
    complete = webp(manifest, riff_chunk(b"VP8 ", b"bild"))
    truncated = complete[:-3]                               # letzter Chunk abgeschnitten
    path = tmp_path / "bild.webp"
    path.write_bytes(truncated)

    assert remove_c2pa_data(path) is True

    # Kopf mit um das Manifest verringerter Größe, danach der angefangene
    # Bild-Chunk unverändert.
    declared_size = struct.unpack("<I", complete[4:8])[0]
    expected = (b"RIFF" + struct.pack("<I", declared_size - len(manifest)) + b"WEBP"
                + truncated[12 + len(manifest):])
    assert path.read_bytes() == expected


def test_invalid_webp_raises(tmp_path):
    path = tmp_path / "bild.webp"
    path.write_bytes(PNG_WITHOUT_C2PA)
    with pytest.raises(ValueError):
        remove_c2pa_data(path)


# ----------------------------------------------------------------------
# Echte, mit der c2pa-Bibliothek signierte Dateien (tests/fixtures/c2pa)
# ----------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures" / "c2pa"


@pytest.mark.parametrize("extension", ["webp", "png", "jpg"])
def test_real_signed_file_is_cleaned_bit_exact(tmp_path, extension):
    from core.c2pa_cleaner import has_c2pa_data

    path = tmp_path / f"bild.{extension}"
    shutil.copy(FIXTURES / f"signed.{extension}", path)
    assert has_c2pa_data(path)

    assert remove_c2pa_data(path) is True
    assert not has_c2pa_data(path)
    assert path.read_bytes() == (FIXTURES / f"plain.{extension}").read_bytes()
