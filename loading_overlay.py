# loading_overlay.py

from PyQt6.QtWidgets import QWidget, QGraphicsBlurEffect, QGraphicsScene, QGraphicsPixmapItem
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPixmap, QColor
import math

from utils import resource_path


class LoadingOverlayGemini(QWidget):
    # --- Konfiguration als Klassenkonstanten ---
    BLUR_RADIUS: int = 15
    TIMER_INTERVAL_MS: int = 30
    ANIMATION_SPEED: float = 0.1
    ANIMATION_AMPLITUDE: float = 0.2   # Skalierungs-Schwingbreite (1 ± amplitude)
    ANIMATION_BASE: float = 0.8        # Mindestskalierung

    STAR_CONFIG: list[dict] = [
        {"base_size": 120, "dx": -10, "dy":   0, "phase_offset": 0.0},
        {"base_size":  30, "dx":  60, "dy":  20, "phase_offset": 0.5},
        {"base_size":  60, "dx":  45, "dy": -30, "phase_offset": 1.0},
    ]

    def __init__(self, parent: QWidget, icon_path: str) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.icon = QPixmap(str(resource_path(icon_path)))
        self.phase: float = 0.0
        self.bg_pixmap: QPixmap | None = None

        # Timer erst in start() starten, nicht hier
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.setInterval(self.TIMER_INTERVAL_MS)

        self.hide()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._sync_size()
        self.update_background()
        self.show()
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()
        self.hide()

    # ------------------------------------------------------------------
    # Qt-Events
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        """Overlay an Parent-Größe anpassen, wenn Fenster skaliert wird."""
        self._sync_size()
        self.update_background()
        super().resizeEvent(event)

    def hideEvent(self, event) -> None:
        """Sicherstellen, dass der Timer auch beim Verstecken stoppt."""
        self.timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        """Timer sauber beenden, bevor das Widget zerstört wird."""
        self.timer.stop()
        super().closeEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() // 2
        cy = self.height() // 2

        # Geblurteter Hintergrund oder Fallback
        if self.bg_pixmap:
            scaled_bg = self.bg_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(0, 0, scaled_bg)
        else:
            painter.fillRect(self.rect(), QColor(255, 255, 255, 50))

        # Sterne animiert zeichnen
        for star in self.STAR_CONFIG:
            scale = self.ANIMATION_BASE + self.ANIMATION_AMPLITUDE * math.sin(
                self.phase + star["phase_offset"]
            )
            size = int(star["base_size"] * scale)
            pix = self.icon.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                cx + star["dx"] - pix.width() // 2,
                cy + star["dy"] - pix.height() // 2,
                pix,
            )

    # ------------------------------------------------------------------
    # Hilfsmethoden (privat)
    # ------------------------------------------------------------------

    def _animate(self) -> None:
        """Phase inkrementieren und Neuzeichnen anfordern."""
        self.phase = (self.phase + self.ANIMATION_SPEED) % (2 * math.pi)
        self.update()

    def _sync_size(self) -> None:
        """Overlay-Größe an Parent anpassen."""
        if self.parent():
            self.resize(self.parent().size())

    def update_background(self) -> None:
        """Geblurtetes Pixmap aus dem Parent-Label erzeugen (falls vorhanden)."""
        label = self.parent()

        if not (hasattr(label, "pixmap") and label.pixmap() and not label.pixmap().isNull()):
            self.bg_pixmap = None
            return

        orig: QPixmap = label.pixmap()

        # Kopie des Originals als Ausgangsbasis
        blurred = QPixmap(orig.size())
        blurred.fill(Qt.GlobalColor.transparent)
        with QPainter(blurred) as p:
            p.drawPixmap(0, 0, orig)

        # Blur-Effekt über QGraphicsScene anwenden
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(self.BLUR_RADIUS)

        item = QGraphicsPixmapItem(blurred)
        item.setGraphicsEffect(effect)

        scene = QGraphicsScene()
        scene.addItem(item)

        result = QPixmap(orig.size())
        result.fill(Qt.GlobalColor.transparent)
        with QPainter(result) as p:
            scene.render(p)

        self.bg_pixmap = result
