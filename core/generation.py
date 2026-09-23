# generation.py
#
# Ein kompletter Generierungsdurchlauf, ohne GUI:
#   Task anlegen -> auf das Ergebnis warten -> Bild herunterladen ->
#   Prompt daneben speichern -> C2PA-Daten entfernen.
#
# Die GUI ruft generate_image() in einem eigenen Thread auf (ui/workers.py)
# und bekommt Zwischenstände über report_status.

import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from core.c2pa_cleaner import PNG_SIGNATURE, has_c2pa_data, remove_c2pa_data
from core.kie_api import KieAPI, extract_image_url, read_task_state
from core.models_registry import ModelSpec

# Warten auf das Ergebnis
POLL_TIMEOUT_S = 600      # so lange wird höchstens auf ein Bild gewartet
POLL_INTERVAL_S = 3       # Pause zwischen zwei Statusabfragen
MAX_UNKNOWN_POLLS = 3     # so oft darf die Antwort keinen erkennbaren Status haben

# Dateianfang ("magic bytes") von JPEG; PNG_SIGNATURE kommt aus c2pa_cleaner
JPEG_SIGNATURE = b"\xff\xd8\xff"

StatusCallback = Callable[[str], None]


class GenerationError(Exception):
    """Die Generierung ist gescheitert; der Text ist für die Statusanzeige gedacht."""


def generate_image(
    api: KieAPI,
    model_spec: ModelSpec,
    prompt: str,
    reference_urls: list[str | None],
    param_values: dict[str, Any],
    callback_url: str,
    target_folder: Path,
    remove_c2pa: bool,
    download_attempts: int,
    download_timeout_s: float,
    report_status: StatusCallback,
) -> Path:
    """Erzeugt ein Bild und speichert es mit dem Prompt in target_folder.

    Returns:
        Pfad der gespeicherten Bilddatei.

    Raises:
        GenerationError, ApiError oder OSError, wenn etwas schiefgeht.
    """
    report_status("Bereite Referenzbilder vor ...")
    input_payload = build_input_payload(model_spec, prompt, reference_urls, param_values)

    report_status(f"Sende Generierungsanfrage ({model_spec.display_name}) ...")
    task_id = api.create_task(
        api_model=model_spec.api_model,
        callback_url=callback_url,
        input_payload=input_payload,
    )
    report_status(f"Task erstellt: {task_id}. Warte auf Ergebnis ...")

    image_url = wait_for_image_url(api, task_id, report_status)

    # Dateiname: Zeitstempel; Bild und Prompt (.txt) tragen denselben Namen.
    target_folder.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    requested_extension = file_extension_for(param_values)
    image_path = target_folder / f"{timestamp}.{requested_extension}"
    prompt_path = target_folder / f"{timestamp}.txt"

    download_with_retries(image_url, image_path, download_attempts, download_timeout_s, report_status)
    image_path = fix_file_extension(image_path)
    prompt_path.write_text(prompt, encoding="utf-8")

    if remove_c2pa:
        remove_c2pa_and_report(image_path, report_status)

    return image_path


def build_input_payload(
    model_spec: ModelSpec,
    prompt: str,
    reference_urls: list[str | None],
    param_values: dict[str, Any],
) -> dict[str, Any]:
    """Baut das "input"-Objekt des API-Aufrufs für das gewählte Modell."""
    payload: dict[str, Any] = {model_spec.prompt_field: prompt}

    # Leere Plätze überspringen, dann auf die Höchstzahl des Modells begrenzen.
    image_urls = [url for url in reference_urls if url]
    image_urls = image_urls[: model_spec.max_images]

    if image_urls:
        if model_spec.images_is_list:
            payload[model_spec.images_field] = image_urls
        else:
            # Das Modell erwartet eine einzelne URL als Text (z.B. Qwen, Qwen2).
            payload[model_spec.images_field] = image_urls[0]

    # Modell-spezifische Parameter aus dem Parameter-Bereich
    for name, value in param_values.items():
        payload[name] = value

    return payload


def wait_for_image_url(api: KieAPI, task_id: str, report_status: StatusCallback) -> str:
    """Fragt den Task-Status ab, bis ein Bild da ist, und gibt dessen URL zurück."""
    start = time.time()
    last_state = ""
    unknown_polls = 0

    while time.time() - start < POLL_TIMEOUT_S:
        status_data = api.get_task_status(task_id)
        state = read_task_state(status_data)

        if state.is_finished and state.is_success:
            image_url = extract_image_url(status_data)
            if not image_url:
                raise GenerationError(
                    "Erfolgsmeldung erhalten, aber keine Bild-URL gefunden. "
                    f"Antwort: {json.dumps(status_data)[:400]}"
                )
            return image_url

        if state.is_finished:
            raise GenerationError(state.message or "Generierung fehlgeschlagen")

        # Liefert die API mehrmals keinen erkennbaren Status, die Rohdaten
        # anzeigen — so wird sichtbar, was sie tatsächlich schickt.
        if state.raw_state == "unknown":
            unknown_polls += 1
            if unknown_polls >= MAX_UNKNOWN_POLLS:
                raise GenerationError(
                    "Unbekanntes Status-Antwortformat. "
                    f"Beispiel-Antwort: {json.dumps(status_data)[:400]}"
                )
        else:
            unknown_polls = 0

        if state.raw_state != last_state:
            report_status(f"Bild wird generiert [{state.raw_state}] ... {task_id}")
            last_state = state.raw_state
        time.sleep(POLL_INTERVAL_S)

    raise GenerationError("Timeout – Bild konnte nicht generiert werden")


def file_extension_for(param_values: dict[str, Any]) -> str:
    """Dateiendung laut gewähltem output_format; ohne Angabe "png"."""
    extension = param_values.get("output_format") or "png"
    if extension == "jpeg":
        return "jpg"
    return extension


def fix_file_extension(image_path: Path) -> Path:
    """Benennt die Datei um, wenn ihr Inhalt nicht zur Endung passt.

    Modelle ohne output_format-Parameter liefern teils JPEG, obwohl die Datei
    dann als .png angelegt wurde. Mit falscher Endung schlägt auch die
    C2PA-Entfernung fehl, weil sie das Format an der Endung erkennt.
    """
    with open(image_path, "rb") as file:
        header = file.read(12)

    if header.startswith(PNG_SIGNATURE):
        actual_suffix = ".png"
    elif header.startswith(JPEG_SIGNATURE):
        actual_suffix = ".jpg"
    elif header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        actual_suffix = ".webp"
    else:
        return image_path  # unbekanntes Format: so lassen, wie es ist

    current_suffix = image_path.suffix.lower()
    if current_suffix == ".jpeg":
        current_suffix = ".jpg"
    if current_suffix == actual_suffix:
        return image_path

    renamed_path = image_path.with_suffix(actual_suffix)
    os.replace(image_path, renamed_path)
    return renamed_path


def remove_c2pa_and_report(image_path: Path, report_status: StatusCallback) -> None:
    """Entfernt C2PA-Daten; ein Fehler dabei bricht die Generierung nicht ab."""
    report_status("Prüfe auf C2PA-Daten ...")
    try:
        if has_c2pa_data(image_path):
            remove_c2pa_data(image_path)
            report_status("C2PA-Daten gefunden und entfernt.")
        else:
            report_status("Keine C2PA-Daten gefunden.")
    except Exception as exc:
        report_status(f"C2PA-Prüfung fehlgeschlagen: {exc}")


# ======================================================================
# Download
# ======================================================================

def download_with_retries(
    url: str,
    target: Path,
    attempts: int,
    timeout_s: float,
    report_status: StatusCallback,
) -> None:
    """Lädt url nach target herunter, mit bis zu `attempts` Versuchen."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        report_status(f"Lade Bild herunter (Versuch {attempt}/{attempts}) ...")
        try:
            download_file(url, target, timeout_s)
            return
        except Exception as exc:
            last_error = exc
    raise GenerationError(f"Download nach {attempts} Versuchen fehlgeschlagen: {last_error}")


def download_file(url: str, target: Path, timeout_s: float) -> None:
    """Lädt url nach target herunter.

    timeout_s begrenzt die Gesamtdauer des Downloads (inkl. DNS,
    Verbindungsaufbau und langsam tröpfelnder Übertragung) — der timeout von
    requests gilt nur pro Socket-Operation. Der Download läuft deshalb in einem
    eigenen Thread in eine .part-Datei; wird er nicht rechtzeitig fertig, wird
    er abgebrochen und die Teil-Datei verworfen.
    """
    part_path = target.with_name(f"{target.name}.{uuid.uuid4().hex[:8]}.part")
    cancel = threading.Event()
    lock = threading.Lock()
    result: dict[str, Any] = {"done": False, "error": None}

    def download() -> None:
        try:
            with requests.get(url, timeout=timeout_s, stream=True) as response:
                response.raise_for_status()
                with open(part_path, "wb") as file:
                    for chunk in response.iter_content(8192):
                        if cancel.is_set():
                            break
                        file.write(chunk)
        except Exception as exc:
            result["error"] = exc
        with lock:
            if cancel.is_set() or result["error"]:
                part_path.unlink(missing_ok=True)
            else:
                result["done"] = True

    thread = threading.Thread(target=download, daemon=True)
    thread.start()
    thread.join(timeout_s)

    with lock:
        if not result["done"]:
            cancel.set()

    if not result["done"]:
        if result["error"]:
            raise result["error"]
        raise TimeoutError(f"Zeitüberschreitung nach {timeout_s:g} s")

    os.replace(part_path, target)
