# build_info.py
#
# Name, Version und Commit des Programms für Fenstertitel und Splash.
# AUTOBUILD.py schreibt die Werte bei jedem Build nach build_version.py.
# In einem frischen Checkout gibt es die Datei noch nicht — dann "dev".

from dataclasses import dataclass

APP_NAME = "API Image Generator"


@dataclass(frozen=True)
class BuildInfo:
    app_name: str
    version: str      # z.B. "v2.8.4-0-gafaa3f8"
    build_time: str   # z.B. "2026-09-22 21:01:30"; leer ohne Build
    commit: str       # Kurz-Hash; leer ohne Build
    commit_url: str   # Link auf den Commit; leer ohne Build

    @property
    def window_title(self) -> str:
        """Name, Version und Build-Zeit, je eine Zeile."""
        if not self.build_time:
            return f"{self.app_name} \n{self.version}"
        return f"{self.app_name} \n{self.version} \n{self.build_time}"


def load_build_info() -> BuildInfo:
    try:
        import build_version
    except ImportError:
        return BuildInfo(APP_NAME, "dev", "", "", "")

    return BuildInfo(
        app_name=build_version.APP_NAME,
        version=build_version.VERSION,
        build_time=build_version.BUILD_TIME,
        commit=build_version.COMMIT,
        commit_url=build_version.COMMIT_URL,
    )
