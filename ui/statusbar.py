# statusbar.py

from __future__ import annotations

from PyQt6.QtCore import (
    QAbstractAnimation, QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRect, Qt, QTimer
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget
)


class StatusBar(QFrame):
    """Statuszeile, die lange Meldungen kurz aufklappt.

    Das Widget liegt bewusst nicht im Layout, sondern schwebt über dem Fenster
    und wächst nach oben über die Bildvorschau. Dadurch kann eine lange
    Fehlermeldung die Fensteraufteilung nicht mehr auseinanderziehen.

    Nach `HOLD_MS` klappt die Anzeige wieder auf eine Zeile zusammen. Passt der
    Text dann nicht mehr hinein, erscheinen rechts zwei kleine Scroll-Pfeile;
    ein Klick auf die Zeile klappt sie erneut auf.
    """

    LINE_HEIGHT = 20     # Höhe einer Textzeile
    MAX_LINES   = 8      # darüber hinaus wird auch aufgeklappt gescrollt
    HOLD_MS     = 8000   # so lange bleibt eine lange Meldung offen
    ANIM_MS     = 180

    def __init__(self, slot: QWidget, parent: QWidget) -> None:
        super().__init__(parent)
        self._slot = slot          # Platzhalter im Layout, gibt Position und Breite vor
        self._expanded = False

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(True)   # deckt die Bildvorschau ab

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._label)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.viewport().setAutoFillBackground(False)

        self._up   = self._make_arrow(Qt.ArrowType.UpArrow, -1)
        self._down = self._make_arrow(Qt.ArrowType.DownArrow, 1)

        arrows = QVBoxLayout()
        arrows.setContentsMargins(0, 0, 0, 0)
        arrows.setSpacing(0)
        arrows.addWidget(self._up)
        arrows.addWidget(self._down)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self._scroll, 1)
        row.addLayout(arrows)

        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self.collapse)

        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(self.ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.finished.connect(self._update_arrows)

        # Der Platzhalter aendert seine Breite auch ohne Fenstergroesse-Aenderung,
        # z.B. wenn die Credits-Zahl laenger wird. Sonst bliebe die Leiste zu
        # breit und wuerde das Credits-Label ueberdecken.
        self._slot.installEventFilter(self)

        self._update_arrows()

    # ==============================
    # Öffentliche API (wie bei QLabel)
    # ==============================

    def setText(self, text: str) -> None:
        self._label.setText(text)
        self.setToolTip(text)      # vollständige Meldung beim Überfahren
        self._scroll.verticalScrollBar().setValue(0)

        if self._needed_height() > self._collapsed_height():
            self.expand()
        else:
            self.collapse()

    def text(self) -> str:
        return self._label.text()

    def expand(self) -> None:
        """Klappt die Meldung auf und startet die Haltezeit."""
        self._expanded = True
        self._animate_to(min(self._needed_height(), self.MAX_LINES * self.LINE_HEIGHT))
        self._hold_timer.start(self.HOLD_MS)

    def collapse(self) -> None:
        """Klappt wieder auf eine Zeile zusammen."""
        self._hold_timer.stop()
        self._expanded = False
        self._scroll.verticalScrollBar().setValue(0)
        self._animate_to(self._collapsed_height())

    def sync_geometry(self) -> None:
        """Richtet die Anzeige neu über dem Platzhalter aus (nach Größenänderung)."""
        height = (
            min(self._needed_height(), self.MAX_LINES * self.LINE_HEIGHT)
            if self._expanded
            else self._collapsed_height()
        )
        target = self._target_rect(height)
        if self._anim.state() == QAbstractAnimation.State.Running:
            self._anim.setEndValue(target)   # laufende Animation umlenken
        else:
            self.setGeometry(target)
        self._update_arrows()
        self.raise_()

    # ==============================
    # Interne Hilfsmethoden
    # ==============================

    def _make_arrow(self, arrow: Qt.ArrowType, direction: int) -> QToolButton:
        btn = QToolButton(self)
        btn.setArrowType(arrow)
        btn.setFixedSize(16, 10)
        btn.setAutoRepeat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Meldung scrollen")
        btn.clicked.connect(lambda: self._scroll_lines(direction))
        return btn

    def _scroll_lines(self, direction: int) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.value() + direction * self.LINE_HEIGHT)

    def _collapsed_height(self) -> int:
        return max(self._slot.height(), self.LINE_HEIGHT)

    def _needed_height(self) -> int:
        """Höhe, die der aktuelle Text in voller Breite braucht."""
        width = self._scroll.viewport().width() or self._slot.width()
        return max(self._label.heightForWidth(max(width, 50)), self.LINE_HEIGHT)

    def _target_rect(self, height: int) -> QRect:
        """Rechteck über dem Platzhalter — die Unterkante bleibt immer gleich."""
        parent = self.parentWidget()
        if parent is None:
            return self.geometry()
        top_left = self._slot.mapTo(parent, QPoint(0, 0))
        bottom = top_left.y() + self._slot.height()
        return QRect(top_left.x(), bottom - height, self._slot.width(), height)

    def _animate_to(self, height: int) -> None:
        target = self._target_rect(height)
        self._anim.stop()
        self.raise_()

        if not self.isVisible() or self.geometry() == target:
            self.setGeometry(target)
            self._update_arrows()
            return

        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(target)
        self._anim.start()

    def _update_arrows(self) -> None:
        overflow = self._needed_height() > self.height()
        self._up.setVisible(overflow)
        self._down.setVisible(overflow)

    # ==============================
    # Events
    # ==============================

    def mousePressEvent(self, event) -> None:
        # Klick auf die zusammengeklappte Zeile zeigt die ganze Meldung.
        if not self._expanded and self._needed_height() > self.height():
            self.expand()
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_arrows()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._slot and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.Show,
        ):
            self.sync_geometry()
        return super().eventFilter(obj, event)
