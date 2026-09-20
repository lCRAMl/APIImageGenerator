# toggleswitch.py
#
# Animierter Schiebeschalter als Ersatz für QCheckBox.
#
# Basiert auf "AnimatedToggle" aus dem Paket qtwidgets
# (MIT License, Copyright (c) 2019 Martin Fitzpatrick,
#  http://github.com/learnpyqt/python-qtwidgets).
#
# Das Paket selbst ist hier nicht verwendbar: sein __init__.py zieht PySide2
# herein, das es für Python 3.13 nicht mehr gibt. Diese Fassung ist deshalb
# eigenständig und auf PyQt6 portiert; zusätzlich zeichnet sie die Beschriftung
# gleich mit und holt ihre Farben aus der Palette (Hell/Dunkel-Modus).

from __future__ import annotations

from PyQt6.QtCore import (
    QAbstractAnimation, QEasingCurve, QPointF, QPropertyAnimation, QRectF,
    QSequentialAnimationGroup, QSize, Qt, pyqtProperty
)
from PyQt6.QtGui import QBrush, QColor, QPainter, QPalette, QPen
from PyQt6.QtWidgets import QCheckBox


class AnimatedToggle(QCheckBox):
    """Schiebeschalter mit gleitendem Knopf und kurzem Puls beim Umschalten.

    Nach außen bleibt es eine QCheckBox: `isChecked()`, `setChecked()` und das
    `toggled`-Signal funktionieren unverändert.
    """

    TRACK_W  = 42     # Breite der Schiene
    TRACK_H  = 20     # Höhe der Schiene
    GAP      = 8      # Abstand zwischen Schiene und Beschriftung
    SLIDE_MS = 200
    PULSE_MS = 350

    _TRANSPARENT_PEN = QPen(Qt.GlobalColor.transparent)

    def __init__(self, text: str = "", parent=None) -> None:
        self._handle_position = 0.0
        self._pulse_radius = 0.0
        super().__init__(text, parent)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._slide = QPropertyAnimation(self, b"handle_position", self)
        self._slide.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._slide.setDuration(self.SLIDE_MS)

        self._pulse = QPropertyAnimation(self, b"pulse_radius", self)
        self._pulse.setDuration(self.PULSE_MS)
        self._pulse.setStartValue(self.TRACK_H * 0.5)
        self._pulse.setEndValue(self.TRACK_H * 0.95)

        self._group = QSequentialAnimationGroup(self)
        self._group.addAnimation(self._slide)
        self._group.addAnimation(self._pulse)

        self.toggled.connect(self._on_toggled)
        self._handle_position = 1.0 if self.isChecked() else 0.0

    # ==============================
    # Geometrie
    # ==============================

    def sizeHint(self) -> QSize:
        metrics = self.fontMetrics()
        width = self.TRACK_W
        if self.text():
            width += self.GAP + metrics.horizontalAdvance(self.text())
        return QSize(width, max(self.TRACK_H + 4, metrics.height()))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def hitButton(self, pos) -> bool:
        # Auch ein Klick auf die Beschriftung schaltet um.
        return self.rect().contains(pos)

    # ==============================
    # Animation
    # ==============================

    def _on_toggled(self, checked: bool) -> None:
        self._group.stop()
        self._slide.setStartValue(self._handle_position)
        self._slide.setEndValue(1.0 if checked else 0.0)
        self._group.start()

    @pyqtProperty(float)
    def handle_position(self) -> float:
        return self._handle_position

    @handle_position.setter
    def handle_position(self, value: float) -> None:
        self._handle_position = value
        self.update()

    @pyqtProperty(float)
    def pulse_radius(self) -> float:
        return self._pulse_radius

    @pulse_radius.setter
    def pulse_radius(self, value: float) -> None:
        self._pulse_radius = value
        self.update()

    # ==============================
    # Darstellung
    # ==============================

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        """Schienenfarbe, Knopffarbe und Textfarbe für den aktuellen Zustand."""
        group = (
            QPalette.ColorGroup.Normal if self.isEnabled()
            else QPalette.ColorGroup.Disabled
        )
        palette = self.palette()
        accent = palette.color(group, QPalette.ColorRole.Highlight)
        text = palette.color(group, QPalette.ColorRole.WindowText)

        if self.isChecked():
            return accent.lighter(130), accent, text
        return palette.color(group, QPalette.ColorRole.Mid), QColor("#f0f0f0"), text

    def paintEvent(self, event) -> None:
        bar_color, handle_color, text_color = self._colors()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self._TRANSPARENT_PEN)

        track = QRectF(0, 0, self.TRACK_W, self.TRACK_H)
        track.moveCenter(QPointF(self.TRACK_W / 2, self.height() / 2))

        radius = self.TRACK_H / 2
        handle_radius = radius - 2
        trail = self.TRACK_W - 2 * radius
        center = QPointF(
            track.x() + radius + trail * self._handle_position,
            track.center().y(),
        )

        # Puls beim Umschalten
        if self._pulse.state() == QAbstractAnimation.State.Running:
            pulse = QColor(handle_color)
            pulse.setAlpha(70)
            painter.setBrush(QBrush(pulse))
            painter.drawEllipse(center, self._pulse_radius, self._pulse_radius)

        painter.setBrush(QBrush(bar_color))
        painter.drawRoundedRect(track, radius, radius)

        painter.setBrush(QBrush(handle_color))
        if not self.isChecked():
            painter.setPen(QPen(QColor("#9a9a9a")))
        painter.drawEllipse(center, handle_radius, handle_radius)

        if self.text():
            painter.setPen(QPen(text_color))
            label = QRectF(
                self.TRACK_W + self.GAP, 0,
                max(self.width() - self.TRACK_W - self.GAP, 0), self.height(),
            )
            painter.drawText(
                label,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                self.text(),
            )

        painter.end()
