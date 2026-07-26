import sys
from pathlib import Path
from typing import Union

from c2pa import Reader

PathLike = Union[str, Path]

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_c2pa_data(media_path: PathLike) -> None:
    print(f"Reading {media_path}")
    try:
        reader = Reader(str(media_path))
        manifest_json = reader.json()
        print(manifest_json)
        reader.close()

    except Exception as e:
        print(f"Error reading C2PA data from {media_path}: {e}")


def has_c2pa_data(media_path: PathLike) -> bool:
    """Prüft, ob eine Datei C2PA-Metadaten (ein Manifest) enthält.

    Nutzt Reader.try_create, das None zurückgibt statt eine Exception zu
    werfen, wenn kein Manifest/JUMBF-Datenblock gefunden wurde.

    Returns:
        True, wenn C2PA-Daten gefunden wurden, sonst False.
    """
    try:
        reader = Reader.try_create(str(media_path))
    except Exception as e:
        print(f"Fehler beim Prüfen auf C2PA-Daten in {media_path}: {e}")
        return False

    if reader is None:
        return False

    reader.close()
    return True


def remove_c2pa_data(media_path: PathLike) -> bool:
    """Entfernt C2PA-Daten vollständig und unwiderruflich aus einer Datei.

    Die C2PA-Manifest-Box (JUMBF) wird nicht überschrieben oder unkenntlich
    gemacht, sondern als Segment/Chunk auf Byte-Ebene aus der Datei entfernt
    - das Ergebnis ist bit-identisch zu einer Datei, die nie C2PA-Daten
    enthalten hat. Alle übrigen Bilddaten und Metadaten bleiben unverändert.

    Unterstützt JPEG (APP11/JUMBF-Segmente) und PNG (caBX-Chunk).

    Returns:
        True, wenn C2PA-Daten gefunden und entfernt wurden.
        False, wenn die Datei ohnehin keine C2PA-Daten enthielt.

    Raises:
        ValueError: Wenn das Dateiformat nicht unterstützt wird oder die
            Datei kein gültiges JPEG/PNG ist.
    """
    path = Path(media_path)
    suffix = path.suffix.lower()

    data = path.read_bytes()

    if suffix in (".jpg", ".jpeg"):
        new_data, removed = _strip_jpeg_app11(data)
    elif suffix == ".png":
        new_data, removed = _strip_png_cabx(data)
    else:
        raise ValueError(f"Nicht unterstütztes Dateiformat für C2PA-Entfernung: {suffix}")

    if not removed:
        return False

    tmp_path = path.with_name(path.name + ".c2patmp")
    tmp_path.write_bytes(new_data)
    tmp_path.replace(path)
    return True


def _strip_jpeg_app11(data: bytes) -> tuple[bytes, bool]:
    """Entfernt alle APP11-Segmente (JUMBF/C2PA) aus JPEG-Rohdaten."""
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        raise ValueError("Keine gültige JPEG-Datei (SOI-Marker fehlt).")

    out = bytearray(data[:2])
    i = 2
    n = len(data)
    removed = False

    while i < n:
        if data[i] != 0xFF:
            # Kein Marker mehr erwartet - Rest unverändert übernehmen
            out += data[i:]
            break

        # FF-Fill-Bytes überspringen
        j = i + 1
        while j < n and data[j] == 0xFF:
            j += 1
        if j >= n:
            out += data[i:]
            break

        marker = data[j]
        header_end = j + 1

        if marker == 0xD9:  # EOI
            out += data[i:]
            break

        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            # Standalone-Marker ohne Längenfeld (TEM, RSTn)
            out += data[i:header_end]
            i = header_end
            continue

        if header_end + 2 > n:
            out += data[i:]
            break

        seg_len = (data[header_end] << 8) | data[header_end + 1]
        seg_end = header_end + seg_len

        if marker == 0xDA:  # SOS - danach folgen Scan-Daten, unverändert übernehmen
            out += data[i:]
            break

        if marker == 0xEB:  # APP11 - JUMBF / C2PA
            removed = True
        else:
            out += data[i:seg_end]

        i = seg_end

    return bytes(out), removed


def _strip_png_cabx(data: bytes) -> tuple[bytes, bool]:
    """Entfernt alle caBX-Chunks (C2PA) aus PNG-Rohdaten."""
    if data[:8] != PNG_SIGNATURE:
        raise ValueError("Keine gültige PNG-Datei (Signatur fehlt).")

    out = bytearray(data[:8])
    i = 8
    n = len(data)
    removed = False

    while i + 8 <= n:
        length = int.from_bytes(data[i:i + 4], "big")
        chunk_type = data[i + 4:i + 8]
        chunk_end = i + 8 + length + 4  # Header + Daten + CRC

        if chunk_end > n:
            # Abgeschnittene/kaputte Datei - Rest unverändert übernehmen
            out += data[i:]
            break

        if chunk_type == b"caBX":
            removed = True
        else:
            out += data[i:chunk_end]

        i = chunk_end

    return bytes(out), removed


if __name__ == '__main__':
    if len(sys.argv) < 2:
        media_path = "Z:\\Instagram\\Ava Addams\\ai\\2026-07-26_05-47-36.jpg"
    else:
        media_path = sys.argv[1]

    if has_c2pa_data(media_path):
        print(f"{media_path} enthält C2PA-Daten.")
        read_c2pa_data(media_path)
        if remove_c2pa_data(media_path):
            print("C2PA-Daten entfernt.")
        if has_c2pa_data(media_path):
            print("WARNUNG: C2PA-Daten konnten nicht vollständig entfernt werden.")
        else:
            print("Verifiziert: keine C2PA-Daten mehr vorhanden.")
    else:
        print(f"{media_path} enthält keine C2PA-Daten.")
