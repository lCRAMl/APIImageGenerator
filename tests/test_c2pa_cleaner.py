import struct
import zlib

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
    path = tmp_path / "bild.webp"
    path.write_bytes(b"RIFF....WEBP")
    with pytest.raises(ValueError):
        remove_c2pa_data(path)
