# imgbb.py

from __future__ import annotations

import base64
import logging
import os
import threading
from dataclasses import dataclass
from typing import Callable

import requests
from PyQt6.QtCore import QThread, pyqtSignal as Signal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Eigene Fehlerklassen – damit Aufrufer gezielt fangen können
# ---------------------------------------------------------------------------

class ImgBBError(Exception):
    """Basisklasse für alle ImgBB-Fehler."""


class ImgBBFileNotFoundError(ImgBBError):
    """Die zu uploadende Datei existiert nicht."""


class ImgBBNetworkError(ImgBBError):
    """Netzwerk- oder HTTP-Fehler beim Upload."""


class ImgBBApiError(ImgBBError):
    """ImgBB hat einen API-seitigen Fehler zurückgemeldet."""


# ---------------------------------------------------------------------------
# Result-Typ statt rohem dict
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UploadResult:
    display_url: str
    delete_url: str | None = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ImgBBClient:
    UPLOAD_ENDPOINT = "https://api.imgbb.com/1/upload"
    DEFAULT_TIMEOUT = 30  # Sekunden

    def __init__(self, api_key: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def upload_image(
        self,
        local_path: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> UploadResult:
        """Lädt ein Bild auf ImgBB hoch und gibt das Ergebnis zurück.

        Args:
            local_path:         Dateipfad des lokalen Bildes.
            progress_callback:  Optionaler Callback mit Fortschritt [0.0 - 1.0].

        Raises:
            ImgBBFileNotFoundError: Datei nicht gefunden.
            ImgBBNetworkError:      Netzwerk- oder HTTP-Fehler.
            ImgBBApiError:          API-seitiger Fehler.
        """
        if not os.path.isfile(local_path):
            raise ImgBBFileNotFoundError(f"Datei nicht gefunden: {local_path}")

        # Datei chunk-weise Base64-kodieren, um RAM-Verbrauch zu begrenzen
        encoded_string = self._encode_file(local_path)

        if progress_callback:
            progress_callback(0.1)  # Kodierung abgeschlossen

        data = {
            "key": self.api_key,
            "image": encoded_string,
        }

        try:
            response = requests.post(
                self.UPLOAD_ENDPOINT,
                data=data,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise ImgBBNetworkError("Upload-Timeout ueberschritten.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise ImgBBNetworkError(f"Verbindungsfehler: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise ImgBBNetworkError(f"Netzwerkfehler: {exc}") from exc

        if progress_callback:
            progress_callback(0.9)  # HTTP-Request abgeschlossen

        # HTTP-Fehler: Body auslesen fuer bessere Fehlermeldung
        if response.status_code != 200:
            try:
                body = response.json()
                detail = body.get("error", {}).get("message", response.text)
            except ValueError:
                detail = response.text
            raise ImgBBNetworkError(f"HTTP {response.status_code}: {detail}")

        result = response.json()
        if not result.get("success"):
            raise ImgBBApiError(f"ImgBB API-Fehler: {result}")

        return UploadResult(
            display_url=result["data"]["display_url"],
            delete_url=result["data"].get("delete_url"),
        )

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_file(path: str, chunk_size: int = 65_536) -> str:
        """Liest eine Datei chunk-weise ein und gibt Base64-kodierten String zurueck."""
        chunks: list[bytes] = []
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                chunks.append(chunk)
        return base64.b64encode(b"".join(chunks)).decode("utf-8")


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class ImgBBUploadWorker(QThread):
    """QThread, der einen ImgBB-Upload asynchron durchfuehrt.

    Signals:
        progress(float):  Fortschritt 0.0 - 1.0.
        finished(str):    Display-URL nach erfolgreichem Upload.
        error(str):       Fehlermeldung bei Misserfolg.
    """

    progress = Signal(float)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, client: ImgBBClient, local_path: str) -> None:
        super().__init__()
        self.client = client
        self.local_path = local_path
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Signalisiert dem Worker, den Upload abzubrechen."""
        self._cancel_event.set()

    def run(self) -> None:
        self.progress.emit(0.0)

        if self._cancel_event.is_set():
            return

        def _progress_callback(value: float) -> None:
            if not self._cancel_event.is_set():
                self.progress.emit(value)

        try:
            result = self.client.upload_image(
                self.local_path,
                progress_callback=_progress_callback,
            )

            if self._cancel_event.is_set():
                return

            self.progress.emit(1.0)
            self.finished.emit(result.display_url)

        except ImgBBFileNotFoundError as exc:
            logger.error("Datei nicht gefunden: %s", exc)
            self.error.emit(str(exc))
        except ImgBBNetworkError as exc:
            logger.error("Netzwerkfehler beim Upload: %s", exc)
            self.error.emit(str(exc))
        except ImgBBApiError as exc:
            logger.error("ImgBB API-Fehler: %s", exc)
            self.error.emit(str(exc))
        except Exception as exc:
            logger.exception("Unerwarteter Fehler beim Upload: %s", exc)
            self.error.emit(f"Unerwarteter Fehler: {exc}")
