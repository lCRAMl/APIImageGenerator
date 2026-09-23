# APIImageGenerator.py
#
# Einstiegspunkt: lädt die Konfiguration, startet Qt und zeigt das Hauptfenster.
# Die Oberfläche steckt in ui/, die Programmlogik in core/.

import sys

from PyQt6.QtWidgets import QApplication

from core.build_info import load_build_info
from core.config import AppConfig
from ui.ui import MainWindow, apply_windows_theme


def main() -> int:
    config = AppConfig()

    app = QApplication(sys.argv)
    apply_windows_theme(app)

    window = MainWindow(config, load_build_info())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
