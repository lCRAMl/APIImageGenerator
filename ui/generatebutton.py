# generatebutton.py

from __future__ import annotations

import math

from PyQt6.QtCore import QPropertyAnimation, QRectF, Qt, pyqtProperty
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPalette, QPen
from PyQt6.QtWidgets import QPushButton


class GenerateButton(QPushButton):
    """Startknopf, der während der Generierung animiert weiterläuft.

    Im Ruhezustand ein ganz normaler QPushButton. Während `start_busy()` aktiv
    ist, zeichnet er sich selbst: ein Leuchtbalken wandert am unteren Rand hin
    und her, der Rahmen pulsiert in der Akzentfarbe und die Punkte hinter der
    Beschriftung laufen mit.
    """

    RADIUS   = 6      # Eckenradius
    BAR_H    = 4      # Höhe des Leuchtbalkens
    BAR_W    = 0.30   # Breite des Balkens, Anteil der Buttonbreite
    SWEEP_MS = 1400   # Dauer eines vollen Hin-und-Her

    def __init__(self, text: str = "", parent=None) -> None:
        self._phase = 0.0
        super().__init__(text, parent)

        self._busy = False
        self._busy_label = "Generating"

        self._anim = QPropertyAnimation(self, b"phase", self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(self.SWEEP_MS)
        self._anim.setLoopCount(-1)

    # ==============================
    # Öffentliche API
    # ==============================

    def start_busy(self, label: str = "Generating") -> None:
        """Schaltet auf die laufende Animation um."""
        self._busy_label = label
        if not self._busy:
            self._busy = True
            self._anim.start()
        self.update()

    def stop_busy(self) -> None:
        """Zurück zum normalen Button."""
        if self._busy:
            self._busy = False
            self._anim.stop()
        self.update()

    def is_busy(self) -> bool:
        return self._busy

    @pyqtProperty(float)
    def phase(self) -> float:
        return self._phase

    @phase.setter
    def phase(self, value: float) -> None:
        self._phase = value
        self.update()

    # ==============================
    # Darstellung
    # ==============================

    def paintEvent(self, event) -> None:
        if not self._busy:
            super().paintEvent(event)
            return

        palette = self.palette()
        accent = palette.color(QPalette.ColorGroup.Normal, QPalette.ColorRole.Highlight)
        # Auch im gesperrten Zustand gut lesbar bleiben:
        text_color = palette.color(QPalette.ColorGroup.Normal, QPalette.ColorRole.ButtonText)
        base = palette.color(QPalette.ColorGroup.Normal, QPalette.ColorRole.Button)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        shape = QPainterPath()
        shape.addRoundedRect(rect, self.RADIUS, self.RADIUS)

        painter.fillPath(shape, QBrush(base))

        # Rahmen pulsiert sanft in der Akzentfarbe
        glow = QColor(accent)
        glow.setAlpha(int(110 + 90 * (0.5 - 0.5 * math.cos(2 * math.pi * self._phase))))
        painter.setPen(QPen(glow, 1.5))
        painter.drawPath(shape)

        # Leuchtbalken am unteren Rand, wandert hin und her
        painter.setClipPath(shape)
        swing = 0.5 - 0.5 * math.cos(2 * math.pi * self._phase)
        bar_w = rect.width() * self.BAR_W
        bar_x = rect.x() + (rect.width() - bar_w) * swing
        bar = QRectF(bar_x, rect.bottom() - self.BAR_H, bar_w, self.BAR_H)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(accent))
        painter.drawRoundedRect(bar, self.BAR_H / 2, self.BAR_H / 2)
        painter.setClipping(False)

        dots = "." * (1 + int(self._phase * 3) % 3)
        painter.setPen(QPen(text_color))
        painter.setFont(self.font())
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignCenter),
            f"{self._busy_label}{dots}",
        )

        painter.end()
