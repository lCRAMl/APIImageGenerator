# paths.py
#
# Wo liegen die Dateien des Programms? Die Antwort hängt davon ab, ob es aus
# dem Quellcode läuft oder als PyInstaller-onefile-EXE gebündelt wurde.

import sys
from pathlib import Path

# Projektordner: eine Ebene über core/.
PROJECT_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE_NAME = "config.ini"


def is_frozen() -> bool:
    """True, wenn das Programm als PyInstaller-EXE läuft."""
    return getattr(sys, "frozen", False)


def resource_path(relative_path: str) -> Path:
    """Pfad zu einer mitgelieferten Ressource (z.B. "assets/gemini_icon.ico").

    Im Quellcode liegt sie im Projektordner. In der EXE entpackt PyInstaller
    die Ressourcen in einen temporären Ordner (sys._MEIPASS).
    """
    if is_frozen():
        return Path(sys._MEIPASS) / relative_path
    return PROJECT_DIR / relative_path


def config_file_path() -> Path:
    """Pfad zur config.ini.

    Im Quellcode liegt sie im Projektordner. Die EXE liegt in output/ und
    liest dieselbe config.ini eine Ebene darüber, also ebenfalls im
    Projektordner.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent.parent / CONFIG_FILE_NAME
    return PROJECT_DIR / CONFIG_FILE_NAME
