# referencethumb.py

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QFileDialog
from PyQt6.QtCore import pyqtSignal as Signal, Qt
from PyQt6.QtGui import QPixmap, QPainter, QPen

from utility.imgbb import ImgBBClient, ImgBBUploadWorker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hilfklassen
# ---------------------------------------------------------------------------

class ClickableLabel(QLabel):
    """QLabel, das Mausklicks als Qt-konformes Signal weitergibt."""
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CloseButton(QPushButton):
    """Kleiner X-Button, der über einem Widget schwebt."""

    SIZE = 14
    PADDING = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 30, 30, 50);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 7px;
            }
            QPushButton:hover {
                background-color: rgba(220, 50, 50, 220);
                border-color: rgba(255, 255, 255, 80);
            }
        """)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(Qt.GlobalColor.white, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        pad = self.PADDING
        w, h = self.width(), self.height()
        painter.drawLine(pad, pad, w - pad, h - pad)
        painter.drawLine(w - pad, pad, pad, h - pad)


# ---------------------------------------------------------------------------
# Hauptklasse
# ---------------------------------------------------------------------------

class ReferenceThumb(QWidget):
    """Einzelnes Thumbnail-Widget mit Upload-Fortschritt und Clear-Button."""

    cleared = Signal(int)
    uploaded = Signal(int, str)
    upload_failed = Signal(int, str)

    # --- Layout-Konstanten ---
    THUMB_SIZE = 100
    WIDGET_HEIGHT = 110
    PROGRESS_HEIGHT = 2

    # --- Style ---
    _EMPTY_STYLE = "border:1px dashed #555; font-size:30px;"
    _COLOR_PROGRESS = "#4caf50"
    _COLOR_UPLOADING = "#00bfff"
    _COLOR_ERROR = "#ff0000"

    def __init__(self, index: int, imgbb_api_key: str) -> None:
        super().__init__()
        self.index = index
        self.imgbb_api_key = imgbb_api_key
        self.upload_url: str | None = None

        self._worker: ImgBBUploadWorker | None = None
        self._uploading = False

        self.setFixedSize(self.THUMB_SIZE, self.WIDGET_HEIGHT)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Thumbnail-Label (ClickableLabel statt Lambda-Hack)
        self.image = ClickableLabel("🗋", self)
        self.image.setFixedSize(self.THUMB_SIZE, self.THUMB_SIZE)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setStyleSheet(self._EMPTY_STYLE)
        self.image.clicked.connect(self.load_image_dialog)

        # Fortschrittsbalken
        self.progress = QLabel(self)
        self.progress.setGeometry(0, self.THUMB_SIZE, 0, self.PROGRESS_HEIGHT)
        self.progress.setStyleSheet(f"background-color: {self._COLOR_PROGRESS};")

        # X-Button
        self.close_btn = CloseButton(self.image)
        self.close_btn.move(self.image.width() - self.close_btn.width() - 2, 2)
        self.close_btn.clicked.connect(self.clear)
        self.close_btn.hide()

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def set_image(self, path: str) -> None:
        """Lädt ein Bild aus einem Dateipfad und startet den Upload."""
        if self._uploading:
            self._cancel_worker()

        pix = QPixmap(path).scaled(
            self.THUMB_SIZE, self.THUMB_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image.setPixmap(pix)
        self.image.setStyleSheet("")
        self.close_btn.show()
        self._upload_to_imgbb(path)

    def clear(self) -> None:
        """Setzt das Thumbnail zurück und bricht einen laufenden Upload ab."""
        self._cancel_worker()
        self.image.clear()
        self.image.setText("🗋")
        self.image.setStyleSheet(self._EMPTY_STYLE)
        self._reset_progress()
        self.close_btn.hide()
        self.upload_url = None
        self.cleared.emit(self.index)

    def set_progress(self, value: float, color: str = _COLOR_PROGRESS) -> None:
        """Setzt den Fortschrittsbalken. value wird auf [0.0, 1.0] geclampt."""
        value = max(0.0, min(1.0, value))
        width = int(self.THUMB_SIZE * value)
        self.progress.setGeometry(0, self.THUMB_SIZE, width, self.PROGRESS_HEIGHT)
        self.progress.setStyleSheet(f"background-color:{color};")

    # ------------------------------------------------------------------
    # Upload-Logik
    # ------------------------------------------------------------------

    def load_image_dialog(self) -> None:
        file, _ = QFileDialog.getOpenFileName(
            self, "Bild auswählen", "", "Images (*.png *.jpg *.jpeg)"
        )
        if file:
            self.set_image(file)

    def _upload_to_imgbb(self, path: str) -> None:
        if not self.imgbb_api_key:
            logger.debug("Kein ImgBB-API-Key gesetzt – Upload wird übersprungen.")
            return

        self._uploading = True
        client = ImgBBClient(self.imgbb_api_key)
        self._worker = ImgBBUploadWorker(client, path)
        self._worker.progress.connect(lambda v: self.set_progress(v, self._COLOR_UPLOADING))
        self._worker.finished.connect(self._on_upload_finished)
        self._worker.error.connect(self._on_upload_failed)
        self._worker.start()

    def _cancel_worker(self) -> None:
        """Trennt Signals des laufenden Workers, damit keine veralteten Callbacks feuern."""
        if self._worker is not None:
            try:
                self._worker.progress.disconnect()
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass  # bereits getrennt
            self._worker = None
        self._uploading = False

    def _reset_progress(self) -> None:
        self.progress.setGeometry(0, self.THUMB_SIZE, 0, self.PROGRESS_HEIGHT)
        self.progress.setStyleSheet(f"background-color: {self._COLOR_PROGRESS};")

    # ------------------------------------------------------------------
    # Upload-Callbacks
    # ------------------------------------------------------------------

    def _on_upload_finished(self, url: str) -> None:
        self._uploading = False
        self.upload_url = url
        self.set_progress(1.0, self._COLOR_PROGRESS)
        self.uploaded.emit(self.index, url)

    def _on_upload_failed(self, error: str) -> None:
        self._uploading = False
        self.set_progress(1.0, self._COLOR_ERROR)
        logger.error("Upload Thumb %d fehlgeschlagen: %s", self.index, error)
        self.image.setText("Upload\nfailed")
        self.upload_failed.emit(self.index, error)
