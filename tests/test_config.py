from pathlib import Path

from core.config import AppConfig


def test_missing_file_is_created_with_defaults(tmp_path):
    path = tmp_path / "config.ini"
    config = AppConfig(path)
    assert path.exists()
    assert config.max_retries == AppConfig.DEFAULT_MAX_RETRIES
    assert config.remove_c2pa_data is True


def test_values_are_read(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text(
        "[Paths]\narchive_path = C:\\Archiv\n"
        "[API]\nnanobanana_api_key = abc\nimgbb_api_key = def\n"
        "[Options]\nremove_c2pa_data = False\nauto_retry = True\nretry_delay_s = 7\nmax_retries = 4\n"
        "[Download]\ndownload_attempts = 2\ndownload_timeout_s = 30\n",
        encoding="utf-8",
    )
    config = AppConfig(path)
    assert config.archive_path == Path("C:\\Archiv")
    assert config.nanobanana_api_key == "abc"
    assert config.remove_c2pa_data is False
    assert config.auto_retry is True
    assert (config.retry_delay_s, config.max_retries) == (7, 4)
    assert (config.download_attempts, config.download_timeout_s) == (2, 30)


def test_invalid_values_fall_back_to_defaults(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text(
        "[Options]\nremove_c2pa_data = vielleicht\nauto_retry = ja-nein\n"
        "retry_delay_s = 0\nmax_retries = drei\n",
        encoding="utf-8",
    )
    config = AppConfig(path)
    assert config.remove_c2pa_data == AppConfig.DEFAULT_REMOVE_C2PA_DATA
    assert config.auto_retry == AppConfig.DEFAULT_AUTO_RETRY
    assert config.retry_delay_s == AppConfig.DEFAULT_RETRY_DELAY_S
    assert config.max_retries == AppConfig.DEFAULT_MAX_RETRIES


def test_missing_entries_are_added_to_file(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[API]\nnanobanana_api_key = abc\n", encoding="utf-8")
    AppConfig(path)
    text = path.read_text(encoding="utf-8")
    assert "max_retries" in text
    assert "nanobanana_api_key = abc" in text


def test_save_round_trip(tmp_path):
    path = tmp_path / "config.ini"
    config = AppConfig(path)
    config.auto_retry = True
    config.save()
    assert AppConfig(path).auto_retry is True


def test_splash_settings(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text(
        "[Splash]\nfont_family = Segoe UI\nfont_size_pt = 14\ntext_color = #ff0000\noutline_color = black\n",
        encoding="utf-8",
    )
    config = AppConfig(path)
    assert config.splash_font_family == "Segoe UI"
    assert config.splash_font_size_pt == 14
    assert (config.splash_text_color, config.splash_outline_color) == ("#ff0000", "black")


def test_splash_defaults_are_written(tmp_path):
    path = tmp_path / "config.ini"
    AppConfig(path)
    text = path.read_text(encoding="utf-8")
    assert "[Splash]" in text
    assert "font_size_pt = 20" in text
