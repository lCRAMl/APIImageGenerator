import pytest
from PyQt6.QtWidgets import QCheckBox

from core.build_info import BuildInfo
from core.config import AppConfig
from core.models_registry import MODELS
from ui.ui import MainWindow

BUILD_INFO = BuildInfo("Test", "v0", "", "", "")


@pytest.fixture
def config(tmp_path):
    archive = tmp_path / "archiv"
    (archive / "Beta").mkdir(parents=True)
    (archive / "Alpha").mkdir()
    path = tmp_path / "config.ini"
    path.write_text(
        f"[Paths]\narchive_path = {archive}\n"
        "[API]\nnanobanana_api_key = key\nimgbb_api_key = key\n"
        # Unerreichbare Adresse: die Credits-Abfrage scheitert sofort, ohne Netz.
        "[URLs]\ncredits_url = http://127.0.0.1:9/credit\n",
        encoding="utf-8",
    )
    return AppConfig(path)


@pytest.fixture
def window(qtbot, config):
    main_window = MainWindow(config, BUILD_INFO)
    qtbot.addWidget(main_window)
    yield main_window
    if main_window.credits_worker is not None:
        main_window.credits_worker.wait()


def test_folders_are_listed_without_preselection(window):
    names = [window.folder_dropdown.itemText(i) for i in range(window.folder_dropdown.count())]
    assert sorted(names) == ["Alpha", "Beta"]
    assert window.folder_dropdown.currentIndex() == -1
    assert window.generate_btn.isEnabled()


def test_missing_archive_disables_generation(qtbot, tmp_path):
    path = tmp_path / "config.ini"
    path.write_text(f"[Paths]\narchive_path = {tmp_path / 'gibt-es-nicht'}\n", encoding="utf-8")
    main_window = MainWindow(AppConfig(path), BUILD_INFO)
    qtbot.addWidget(main_window)
    assert not main_window.folder_dropdown.isEnabled()
    assert not main_window.generate_btn.isEnabled()


@pytest.mark.parametrize("spec", MODELS, ids=[spec.display_name for spec in MODELS])
def test_param_values_match_model_spec(window, spec):
    window.model_dropdown.setCurrentText(spec.display_name)
    values = window._read_param_values()

    for param in spec.params:
        if param.kind == "string" and not param.default:
            continue  # leere Textfelder werden nicht mitgeschickt
        assert param.name in values
        if param.default is not None:
            expected = str(param.default) if param.kind == "enum" else param.default
            assert values[param.name] == expected

    # Nur so viele Miniaturen wie das Modell Referenzbilder annimmt
    enabled = [card.isEnabled() for card in window.reference_cards]
    assert enabled == [index < spec.max_images for index in range(len(enabled))]


def test_bool_params_carry_their_own_label(window):
    window.model_dropdown.setCurrentText("Wan 2.7 - Image")
    checkbox = window.param_widgets["thinking_mode"]
    assert isinstance(checkbox, QCheckBox)
    checkbox.setChecked(True)
    assert window._read_param_values()["thinking_mode"] is True


def test_generate_without_folder_does_not_start_worker(window):
    window.start_generation()
    assert window.worker is None
    assert not window._running
    assert window.status.text() == "Bitte zuerst einen Ordner wählen."


def test_toggling_c2pa_is_saved(window, config):
    window.remove_c2pa_checkbox.setChecked(False)
    assert AppConfig(config.config_path).remove_c2pa_data is False
