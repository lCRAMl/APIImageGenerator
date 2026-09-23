import pytest
from qt_splash import SplashScreen

from core.build_info import BuildInfo
from core.config import AppConfig
from ui.splash import build_splash_config, show_splash, splash_video_path


def test_splash_video_is_found_in_splash_project():
    path = splash_video_path()
    assert path.parts[-3:] == ("assets", "splashvid", "splash_ChloeGraceMoretz_90percent.webp")
    assert path.exists(), "qt_splash muss editierbar aus dem SplashScreenPython-Projekt installiert sein"
    assert path.with_name("splash_ChloeGraceMoretz_90percent.track.json").exists()


def test_splash_config_from_config_ini(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text(
        "[Splash]\nfont_family = Arial\nfont_size_pt = 16\ntext_color = #112233\noutline_color = white\n",
        encoding="utf-8",
    )
    splash_config = build_splash_config(AppConfig(path))
    assert splash_config.font_family == "Arial"
    assert splash_config.font_size_pt == 16
    assert splash_config.text_color == "#112233"
    assert splash_config.outline_color == "white"


def test_empty_font_family_means_system_font(tmp_path):
    splash_config = build_splash_config(AppConfig(tmp_path / "config.ini"))
    assert splash_config.font_family is None


def test_invalid_color_is_rejected(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[Splash]\ntext_color = keine-farbe\n", encoding="utf-8")
    with pytest.raises(ValueError):
        build_splash_config(AppConfig(path))


@pytest.mark.parametrize("build_info, has_link", [
    (BuildInfo("API Image Generator", "v2.8.4", "2026-09-22 21:01:30", "afaa3f8",
               "https://github.com/lCRAMl/APIImageGenerator/commit/afaa3f8"), True),
    (BuildInfo("API Image Generator", "dev", "", "", ""), False),
    (BuildInfo("API Image Generator", "v1", "t", "x", "unknown-commit-url"), False),
])
def test_show_splash(qtbot, tmp_path, build_info, has_link):
    from PyQt6.QtWidgets import QWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    show_splash(parent, build_splash_config(AppConfig(tmp_path / "config.ini")), build_info)

    splashes = parent.findChildren(SplashScreen)
    assert len(splashes) == 1
    assert (splashes[0]._link is not None) == has_link
    splashes[0].close()
