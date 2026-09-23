# APIImageGenerator.py
#
# Einstiegspunkt: lädt die Konfiguration, startet Qt und zeigt das Hauptfenster.
# Die Oberfläche steckt in ui/, die Programmlogik in core/.

import sys

from PyQt6.QtWidgets import QApplication

from core.config import AppConfig
from ui.ui import MainWindow, apply_windows_theme

APP_NAME = "API Image Generator"


def read_build_info() -> str:
    """Name, Version und Build-Zeit für Fenstertitel und Splash.

    build_version.py schreibt AUTOBUILD.py bei jedem Build. In einem frischen
    Checkout gibt es die Datei noch nicht — dann steht dort nur "dev".
    """
    try:
        from build_version import BUILD_INFO
    except ImportError:
        return f"{APP_NAME} \ndev"
    return BUILD_INFO


def main() -> int:
    config = AppConfig()

    app = QApplication(sys.argv)
    apply_windows_theme(app)

    window = MainWindow(config, read_build_info())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
