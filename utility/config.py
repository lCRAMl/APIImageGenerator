# config.py

from __future__ import annotations

import logging
import sys
from pathlib import Path
import configparser

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Wird geworfen, wenn die Konfigurationsdatei nicht gelesen oder geschrieben werden kann."""


class AppConfig:
    CONFIG_NAME = "..//config.ini"

    SECTION_PATHS = "Paths"
    SECTION_API = "API"
    SECTION_URLS = "URLs"
    SECTION_OPTIONS = "Options"

    # ==============================
    # Default-Werte
    # ==============================
    DEFAULT_ARCHIVE_PATH: Path = Path.home() / "Pictures" / "Instagram"
    DEFAULT_NANOBANANA_KEY: str = ""
    DEFAULT_IMGBB_KEY: str = ""
    DEFAULT_REMOVE_C2PA_DATA: bool = True

    # Dummy-Defaults für URLs. Beim ersten Start werden diese in die config.ini
    # geschrieben und sollen vom Nutzer manuell angepasst werden.
    DEFAULT_GENERATE_URL: str = "https://api.kie.ai/api/v1/jobs/createTask"
    DEFAULT_STATUS_URL:   str = "https://api.kie.ai/api/v1/jobs/recordInfo"
    DEFAULT_CREDITS_URL:  str = "https://api.kie.ai/api/v1/chat/credit"
    DEFAULT_CALLBACK_URL: str = "https://example.com/callback"

    def __init__(self) -> None:
        self.config = configparser.ConfigParser()
        self.config_path = self._get_config_path()

        # Felder mit Defaults vorbelegen
        self.archive_path: Path = self.DEFAULT_ARCHIVE_PATH
        self.nanobanana_api_key: str = self.DEFAULT_NANOBANANA_KEY
        self.imgbb_api_key: str = self.DEFAULT_IMGBB_KEY

        self.generate_url: str = self.DEFAULT_GENERATE_URL
        self.status_url:   str = self.DEFAULT_STATUS_URL
        self.credits_url:  str = self.DEFAULT_CREDITS_URL
        self.callback_url: str = self.DEFAULT_CALLBACK_URL

        self.remove_c2pa_data: bool = self.DEFAULT_REMOVE_C2PA_DATA

        self._load_or_create()

    # ==============================
    # Öffentliche API
    # ==============================

    def save(self) -> None:
        """Schreibt die aktuelle Konfiguration in die .ini-Datei.

        Raises:
            ConfigError: Wenn die Datei nicht geschrieben werden kann.
        """
        # Veraltete Sektionen entfernen (z.B. alte [Prompt]-Sektion aus früheren Versionen)
        for legacy in ("Prompt",):
            if self.config.has_section(legacy):
                self.config.remove_section(legacy)

        self.config[self.SECTION_PATHS] = {
            "archive_path": str(self.archive_path),
        }
        self.config[self.SECTION_API] = {
            # Hinweis: Keys werden im Klartext gespeichert.
            # Für produktive Umgebungen keyring oder eine verschlüsselte Lösung verwenden.
            "nanobanana_api_key": self.nanobanana_api_key,
            "imgbb_api_key":      self.imgbb_api_key,
        }
        self.config[self.SECTION_URLS] = {
            "generate_url": self.generate_url,
            "status_url":   self.status_url,
            "credits_url":  self.credits_url,
            "callback_url": self.callback_url,
        }
        self.config[self.SECTION_OPTIONS] = {
            "remove_c2pa_data": str(self.remove_c2pa_data),
        }

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                self.config.write(f)
            logger.debug("Config gespeichert: %s", self.config_path)
        except OSError as exc:
            raise ConfigError(
                f"Konfiguration konnte nicht gespeichert werden: {self.config_path}"
            ) from exc

    def __repr__(self) -> str:
        return (
            f"AppConfig("
            f"config_path={self.config_path!r}, "
            f"archive_path={self.archive_path!r}, "
            f"generate_url={self.generate_url!r})"
        )

    # ==============================
    # Interne Hilfsmethoden
    # ==============================

    def _load_or_create(self) -> None:
        """Lädt eine vorhandene Config oder legt eine neue mit Defaults an."""
        if not self.config_path.exists():
            logger.info("Keine Config gefunden – neue Datei wird angelegt: %s", self.config_path)
            self.save()
            return

        try:
            self.config.read(self.config_path, encoding="utf-8")
        except configparser.Error as exc:
            logger.warning(
                "Config konnte nicht gelesen werden, Defaults werden verwendet: %s", exc
            )
            return

        self._parse_paths()
        self._parse_api()
        self._parse_urls()
        self._parse_options()

    def _parse_paths(self) -> None:
        raw_path = self.config.get(
            self.SECTION_PATHS, "archive_path", fallback=str(self.DEFAULT_ARCHIVE_PATH)
        )
        candidate = Path(raw_path)
        if candidate.exists() and not candidate.is_dir():
            logger.warning(
                "archive_path '%s' ist kein Verzeichnis – Default wird verwendet.", candidate
            )
            self.archive_path = self.DEFAULT_ARCHIVE_PATH
        else:
            self.archive_path = candidate

    def _parse_api(self) -> None:
        self.nanobanana_api_key = self.config.get(
            self.SECTION_API, "nanobanana_api_key", fallback=self.DEFAULT_NANOBANANA_KEY
        )
        self.imgbb_api_key = self.config.get(
            self.SECTION_API, "imgbb_api_key", fallback=self.DEFAULT_IMGBB_KEY
        )

    def _parse_urls(self) -> None:
        self.generate_url = self.config.get(
            self.SECTION_URLS, "generate_url", fallback=self.DEFAULT_GENERATE_URL
        )
        self.status_url = self.config.get(
            self.SECTION_URLS, "status_url", fallback=self.DEFAULT_STATUS_URL
        )
        self.credits_url = self.config.get(
            self.SECTION_URLS, "credits_url", fallback=self.DEFAULT_CREDITS_URL
        )
        self.callback_url = self.config.get(
            self.SECTION_URLS, "callback_url", fallback=self.DEFAULT_CALLBACK_URL
        )

    def _parse_options(self) -> None:
        self.remove_c2pa_data = self.config.getboolean(
            self.SECTION_OPTIONS, "remove_c2pa_data", fallback=self.DEFAULT_REMOVE_C2PA_DATA
        )

    @staticmethod
    def _get_config_path() -> Path:
        """Gibt den Pfad zur config.ini zurück (neben Executable oder Quellcode)."""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent / AppConfig.CONFIG_NAME
        return Path(__file__).resolve().parent / AppConfig.CONFIG_NAME
