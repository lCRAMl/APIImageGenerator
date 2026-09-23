# workers.py
#
# Hintergrund-Threads des Hauptfensters. Sie rufen nur die Programmlogik aus
# core/ auf und melden das Ergebnis per Qt-Signal zurück, damit das Fenster
# während Netzwerkzugriffen bedienbar bleibt.

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal as Signal

from core.generation import generate_image
from core.kie_api import KieAPI
from core.models_registry import ModelSpec


class GenerationWorker(QThread):
    """Führt einen Generierungsversuch aus (core.generation.generate_image)."""

    status = Signal(str)      # Zwischenstand für die Statusanzeige
    succeeded = Signal(str)   # Pfad der gespeicherten Bilddatei
    failed = Signal(str)      # Fehlermeldung

    def __init__(
        self,
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
    ) -> None:
        super().__init__()
        self.api = api
        self.model_spec = model_spec
        self.prompt = prompt
        self.reference_urls = reference_urls
        self.param_values = param_values
        self.callback_url = callback_url
        self.target_folder = target_folder
        self.remove_c2pa = remove_c2pa
        self.download_attempts = download_attempts
        self.download_timeout_s = download_timeout_s

    def run(self) -> None:
        try:
            image_path = generate_image(
                api=self.api,
                model_spec=self.model_spec,
                prompt=self.prompt,
                reference_urls=self.reference_urls,
                param_values=self.param_values,
                callback_url=self.callback_url,
                target_folder=self.target_folder,
                remove_c2pa=self.remove_c2pa,
                download_attempts=self.download_attempts,
                download_timeout_s=self.download_timeout_s,
                report_status=self.status.emit,
            )
        except Exception as exc:
            # Jeder Fehler landet in der Statusanzeige, keiner beendet das Programm.
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(str(image_path))


class CreditsWorker(QThread):
    """Fragt das Guthaben ab; -1.0 heißt "unbekannt"."""

    result = Signal(float)

    def __init__(self, api: KieAPI) -> None:
        super().__init__()
        self.api = api

    def run(self) -> None:
        try:
            self.result.emit(self.api.get_account_credits())
        except Exception:
            self.result.emit(-1.0)
