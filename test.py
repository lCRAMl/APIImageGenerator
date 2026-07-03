from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QPainterPath, QFont, QColor, QPen
import sys


class OutlinedText(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(500,200)

    def paintEvent(self,event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        font = QFont("Arial",48,QFont.Weight.Bold)

        path = QPainterPath()
        path.addText(
            50,
            100,
            font,
            "Qt6"
        )

        # Kontur
        painter.setPen(
            QPen(
                QColor("black"),
                4
            )
        )

        # Füllung
        painter.setBrush(
            QColor("white")
        )

        painter.drawPath(path)


app=QApplication(sys.argv)

window=OutlinedText()
window.show()

sys.exit(app.exec())