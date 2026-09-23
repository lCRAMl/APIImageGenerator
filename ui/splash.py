# splash.py
#
# Der Splash hinter dem ℹ-Knopf. Er kommt aus dem Paket qt_splash
# (Projekt SplashScreenPython), das wie qt_controls_pyrs per pip installiert
# ist — für die Entwicklung editierbar:  pip install -e ..\SplashScreenPython
#
# Das Video liegt im SplashScreenPython-Projekt unter assets\splashvid\.
# AUTOBUILD.py packt es in die EXE; dort liegt es unter assets/splashvid/.

from pathlib import Path

import qt_splash
from PyQt6.QtWidgets import QWidget
from qt_splash import SplashConfig, SplashLink, SplashScreen

from core.build_info import BuildInfo
from core.config import AppConfig
from core.paths import is_frozen, resource_path

SPLASH_VIDEO_NAME = "splash_ChloeGraceMoretz_90percent.webp"
# Neben dem Video liegt die Tracking-Datei: ihr folgt der Text im Splash.
SPLASH_TRACKING_NAME = "splash_ChloeGraceMoretz_90percent.track.json"

# Projektordner von SplashScreenPython. Das Paket ist aus dessen src-Ordner
# installiert: SplashScreenPython/src/qt_splash/__init__.py
SPLASH_PROJECT_DIR = Path(qt_splash.__file__).resolve().parents[2]
SPLASH_VIDEO_DIR = SPLASH_PROJECT_DIR / "assets" / "splashvid"

# Ordner des Videos innerhalb der EXE
BUNDLED_VIDEO_DIR = "assets/splashvid"


def splash_video_path() -> Path:
    if is_frozen():
        return resource_path(f"{BUNDLED_VIDEO_DIR}/{SPLASH_VIDEO_NAME}")
    return SPLASH_VIDEO_DIR / SPLASH_VIDEO_NAME


def build_splash_config(config: AppConfig) -> SplashConfig:
    """Schrift und Farben aus dem Abschnitt [Splash] der config.ini.

    Raises:
        ValueError: wenn ein Wert ungültig ist (z.B. eine unbekannte Farbe).
    """
    return SplashConfig(
        font_family=config.splash_font_family or None,  # None = Systemschrift
        font_size_pt=config.splash_font_size_pt,
        text_color=config.splash_text_color,
        outline_color=config.splash_outline_color,
    )


def show_splash(parent: QWidget, splash_config: SplashConfig, build_info: BuildInfo) -> None:
    """Zeigt den Splash mittig über parent; ein Klick schließt ihn."""
    lines = [build_info.build_time] if build_info.build_time else []

    # Ohne Build (Start aus dem Quellcode) gibt es keinen Commit-Link.
    link = None
    if build_info.commit_url.startswith(("http://", "https://")):
        link = SplashLink(f"Commit {build_info.commit}", build_info.commit_url)

    splash = SplashScreen(
        build_info.app_name,
        version=build_info.version,
        lines=lines,
        link=link,
        animation=splash_video_path(),
        config=splash_config,
        parent=parent,
    )
    splash.show_centered(parent)
