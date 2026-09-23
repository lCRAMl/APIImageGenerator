from pathlib import Path

import pytest

from core import generation
from core.generation import (
    GenerationError, build_input_payload, file_extension_for, fix_file_extension, generate_image,
)
from core.models_registry import ModelSpec

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16


# ----------------------------------------------------------------------
# build_input_payload
# ----------------------------------------------------------------------

def test_payload_with_image_list_skips_empty_slots_and_limits_count():
    spec = ModelSpec("M", "m", images_field="image_urls", max_images=2)
    payload = build_input_payload(spec, "ein Hund", [None, "u1", None, "u2", "u3"], {"seed": 5})
    assert payload == {"prompt": "ein Hund", "image_urls": ["u1", "u2"], "seed": 5}


def test_payload_with_single_image_field():
    spec = ModelSpec("Q", "q", images_field="image_url", images_is_list=False, max_images=1)
    payload = build_input_payload(spec, "p", ["u1"], {})
    assert payload == {"prompt": "p", "image_url": "u1"}


def test_payload_without_images():
    spec = ModelSpec("M", "m")
    assert build_input_payload(spec, "p", [None, None], {}) == {"prompt": "p"}


def test_payload_for_model_without_image_support():
    spec = ModelSpec("M", "m", max_images=0)
    assert build_input_payload(spec, "p", ["u1"], {}) == {"prompt": "p"}


# ----------------------------------------------------------------------
# Dateiendung
# ----------------------------------------------------------------------

def test_file_extension_for():
    assert file_extension_for({}) == "png"
    assert file_extension_for({"output_format": "jpeg"}) == "jpg"
    assert file_extension_for({"output_format": "jpg"}) == "jpg"


def test_fix_file_extension_renames_jpeg_saved_as_png(tmp_path):
    path = tmp_path / "bild.png"
    path.write_bytes(JPEG_BYTES)
    fixed = fix_file_extension(path)
    assert fixed == tmp_path / "bild.jpg"
    assert fixed.read_bytes() == JPEG_BYTES
    assert not path.exists()


def test_fix_file_extension_keeps_matching_name(tmp_path):
    for name, data in (("a.png", PNG_BYTES), ("b.jpg", JPEG_BYTES), ("c.jpeg", JPEG_BYTES)):
        path = tmp_path / name
        path.write_bytes(data)
        assert fix_file_extension(path) == path


def test_fix_file_extension_keeps_unknown_format(tmp_path):
    path = tmp_path / "x.png"
    path.write_bytes(b"GIF89a....")
    assert fix_file_extension(path) == path


# ----------------------------------------------------------------------
# generate_image mit nachgebauter API
# ----------------------------------------------------------------------

class FakeApi:
    def __init__(self, states):
        self.states = list(states)
        self.created = None

    def create_task(self, api_model, callback_url, input_payload):
        self.created = (api_model, callback_url, input_payload)
        return "task-1"

    def get_task_status(self, task_id):
        return self.states.pop(0)


@pytest.fixture
def no_waiting(monkeypatch):
    monkeypatch.setattr(generation, "POLL_INTERVAL_S", 0)


@pytest.fixture
def fake_download(monkeypatch):
    """Ersetzt den Download: schreibt das Bild direkt in die Zieldatei."""
    content = {"bytes": PNG_BYTES}

    def download(url, target, timeout_s):
        Path(target).write_bytes(content["bytes"])

    monkeypatch.setattr(generation, "download_file", download)
    return content


def run_generation(api, target_folder, param_values=None):
    messages = []
    spec = ModelSpec("Test", "test-model", max_images=3)
    image_path = generate_image(
        api=api,
        model_spec=spec,
        prompt="ein Hund",
        reference_urls=["https://ref/1.png", None],
        param_values=param_values or {},
        callback_url="https://cb",
        target_folder=target_folder,
        remove_c2pa=False,
        download_attempts=2,
        download_timeout_s=5,
        report_status=messages.append,
    )
    return image_path, messages


def test_generate_image_saves_image_and_prompt(tmp_path, no_waiting, fake_download):
    api = FakeApi([
        {"state": "waiting"},
        {"state": "success", "resultJson": '{"resultUrls": ["https://out/1.png"]}'},
    ])
    target = tmp_path / "Ordner" / "ai"

    image_path, messages = run_generation(api, target)

    assert image_path.parent == target
    assert image_path.suffix == ".png"
    assert image_path.read_bytes() == PNG_BYTES
    assert image_path.with_suffix(".txt").read_text(encoding="utf-8") == "ein Hund"
    assert api.created == ("test-model", "https://cb", {"prompt": "ein Hund", "image_urls": ["https://ref/1.png"]})
    assert messages[0] == "Bereite Referenzbilder vor ..."
    assert "Bild wird generiert [waiting] ... task-1" in messages


def test_generate_image_fixes_extension_of_jpeg(tmp_path, no_waiting, fake_download):
    fake_download["bytes"] = JPEG_BYTES
    api = FakeApi([{"state": "success", "resultUrls": ["https://out/1"]}])
    image_path, _ = run_generation(api, tmp_path)
    assert image_path.suffix == ".jpg"


def test_generate_image_reports_api_failure(tmp_path, no_waiting, fake_download):
    api = FakeApi([{"state": "fail", "failMsg": "Inhalt abgelehnt"}])
    with pytest.raises(GenerationError, match="Inhalt abgelehnt"):
        run_generation(api, tmp_path)


def test_generate_image_stops_after_repeated_unknown_status(tmp_path, no_waiting, fake_download):
    api = FakeApi([{"x": 1}, {"x": 2}, {"x": 3}])
    with pytest.raises(GenerationError, match="Unbekanntes Status-Antwortformat"):
        run_generation(api, tmp_path)


def test_generate_image_download_retries_then_fails(tmp_path, no_waiting, monkeypatch):
    calls = []

    def failing_download(url, target, timeout_s):
        calls.append(url)
        raise TimeoutError("zu langsam")

    monkeypatch.setattr(generation, "download_file", failing_download)
    api = FakeApi([{"state": "success", "resultUrls": ["https://out/1.png"]}])
    with pytest.raises(GenerationError, match="Download nach 2 Versuchen fehlgeschlagen: zu langsam"):
        run_generation(api, tmp_path)
    assert len(calls) == 2
