# ui.py
#
# Das Hauptfenster: Einstellungen und Prompt links, Bildvorschau rechts.
# Die eigentliche Arbeit (API, Download, C2PA) steckt in core/; das Fenster
# sammelt die Eingaben, startet den GenerationWorker und zeigt das Ergebnis.

import os
import winreg
from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QSpinBox,
    QStyleFactory, QVBoxLayout, QWidget,
)
from qt_controls_pyrs import StatusBar, flash_taskbar
from qt_splash import SplashConfig

from core.build_info import BuildInfo
from core.config import AppConfig, ConfigError
from core.kie_api import KieAPI
from core.models_registry import MODELS, ParamSpec, get_model_by_display_name
from core.paths import resource_path
from ui.controls import (
    Dropdown, FolderDropdown, GenerateAiButton, OptionCheckBox, ParamDropdown,
    PromptBox, ReferenceCard,
)
from ui.loading_overlay import LoadingOverlayGemini
from ui.splash import build_splash_config, show_splash
from ui.workers import CreditsWorker, GenerationWorker

# Beschriftung des Generate-Knopfes während eines Durchgangs: erst Cancel;
# nach einem Klick darauf wird nur noch der laufende Auftrag abgewartet.
CANCEL_TEXT = "⊗ Cancel"
FINISHING_TEXT = "Finishing …"

# Abstand von der Kante der linken Spalte bis zum sichtbaren Rahmen des
# ruhenden Generate-Knopfes. Knöpfe, Auswahlfelder und das Prompt-Feld halten
# ihn selbst frei (für ihren Schein); alles andere bekommt ihn als Rand im
# Layout. So ragt links wie rechts nichts über den Knopf hinaus.
EDGE = GenerateAiButton.ROOM

# Deckkraft des Rahmens um den Parameter-Bereich, 0 bis 255. Die
# Auswahlfelder stehen bei 0.5, also 128 — der Rahmen hier ist blasser.
PARAM_FRAME_ALPHA = 77

# Anzahl der Referenzbild-Miniaturen
REFERENCE_SLOTS = 6


# ==========================
# Farbschema
# ==========================

def apply_windows_theme(app: QApplication) -> None:
    """Übernimmt den dunklen Modus von Windows, falls er eingeschaltet ist."""
    if not is_windows_dark_mode():
        return
    app.setStyle(QStyleFactory.create("Fusion"))
    apply_dark_palette(app)


def is_windows_dark_mode() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except OSError:
        return False


def apply_dark_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText,      Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base,            QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText,     Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text,            Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button,          QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ButtonText,      Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(90, 140, 255))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button,     QColor(35, 35, 35))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(120, 120, 120))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor(120, 120, 120))
    app.setPalette(palette)


# ==========================
# Hauptfenster
# ==========================

class MainWindow(QWidget):
    def __init__(self, config: AppConfig, build_info: BuildInfo) -> None:
        super().__init__()

        self.config = config
        self.archive_dir = config.archive_path
        self.build_info = build_info

        self.api = KieAPI(
            api_key=config.nanobanana_api_key or "",
            generate_url=config.generate_url,
            status_url=config.status_url,
            credits_url=config.credits_url,
        )
        self.imgbb_api_key = config.imgbb_api_key or ""
        self.callback_url  = config.callback_url
        self.last_image_path: str | None = None

        # Widgets des Parameter-Bereichs (Parametername -> Widget)
        self.param_widgets: dict[str, QWidget] = {}

        # Hintergrund-Threads; None, solange noch keiner gestartet wurde
        self.worker: GenerationWorker | None = None
        self.credits_worker: CreditsWorker | None = None

        self.setWindowTitle(build_info.window_title)
        self.resize(1600, 900)
        self.setWindowIcon(QIcon(str(resource_path("assets/gemini_icon.ico"))))

        # =====================================================
        # LAYOUTS
        # =====================================================
        root_layout  = QHBoxLayout(self)
        left_layout  = QVBoxLayout()
        right_layout = QVBoxLayout()

        # ---------- Prompt ----------
        # Im Layout steht nur ein Platzhalter; das Feld selbst schwebt darüber
        # (wie die Statuszeile). Nur so kann es sich über die Einstellungen
        # ausfahren, ohne sie zu verschieben.
        self.prompt_slot = QWidget()
        self.prompt_slot.setMinimumHeight(180)
        self.prompt_slot.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        left_layout.addWidget(self.prompt_slot, 1)

        self.prompt = PromptBox(self.prompt_slot, self)
        self.prompt.setPlaceholderText("Prompt eingeben ...")
        # Wie weit es ausfahren darf, steht erst fest, wenn der Generate-Knopf
        # gebaut ist: set_expand_stop() weiter unten.

        # ---------- Ordnerauswahl + Info-Knopf ----------
        self.folder_dropdown = FolderDropdown()
        self.folder_dropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        dropdown_font = QFont()
        dropdown_font.setPointSize(14)
        self.folder_dropdown.setFont(dropdown_font)

        self.info_btn = GenerateAiButton("ℹ", busy_text="ℹ")
        self.info_btn.setFixedSize(70, 70)
        self.info_btn.setFont(QFont("", 14, QFont.Weight.Bold))
        self.info_btn.setToolTip("Info / About")
        self.info_btn.clicked.connect(self._show_splash)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        folder_row.addWidget(self.folder_dropdown)
        folder_row.addWidget(self.info_btn)
        left_layout.addLayout(folder_row)

        # ---------- Modellauswahl ----------
        model_row = QHBoxLayout()
        self.model_dropdown = Dropdown()
        for spec in MODELS:
            self.model_dropdown.addItem(spec.display_name)
        self.model_dropdown.currentTextChanged.connect(self._on_model_changed)
        model_row.addWidget(self.model_dropdown, 1)
        left_layout.addLayout(model_row)

        # ---------- Dynamischer Parameter-Bereich ----------
        self.param_frame = QFrame()
        # Rahmen ohne eigenes Widget: Qt zeichnet ihn nach dem Stylesheet.
        # Oben offen (border-top: none), damit der Bereich unter dem Modellfeld
        # beginnt, und blasser als die Rahmen der Auswahlfelder (dort 0.5 von
        # Weiß). Der Selektor mit # trifft nur diesen Rahmen, nicht die Felder
        # darin — sonst bekäme jede Beschriftung einen eigenen Rahmen.
        ink = self.palette().color(QPalette.ColorRole.ButtonText)
        self.param_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.param_frame.setObjectName("param_frame")
        self.param_frame.setStyleSheet(
            f"#param_frame {{ border: 1px solid "
            f"rgba({ink.red()}, {ink.green()}, {ink.blue()}, {PARAM_FRAME_ALPHA}); "
            f"border-top: none; }}"
        )
        self.param_layout = QFormLayout(self.param_frame)
        self.param_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.param_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.param_layout.setSpacing(6)
        param_row = QHBoxLayout()
        param_row.setContentsMargins(EDGE, 0, EDGE, 0)
        param_row.addWidget(self.param_frame)
        left_layout.addLayout(param_row)

        # ---------- Referenzbilder ----------
        # Die erste Karte bündig mit dem linken, die letzte mit dem rechten
        # Rand des Generate-Knopfes; dazwischen gleich große Abstände.
        thumb_row = QHBoxLayout()
        thumb_row.setContentsMargins(EDGE, 0, EDGE, 0)
        self.reference_cards: list[ReferenceCard] = []
        # ImgBB-URL je Miniatur; None, solange dort kein Bild hochgeladen ist
        self.reference_urls: list[str | None] = [None] * REFERENCE_SLOTS

        for index in range(REFERENCE_SLOTS):
            if index > 0:
                thumb_row.addStretch(1)
            # Der Dateidialog geht gleich im Archivordner auf.
            card = ReferenceCard(index, self.imgbb_api_key, start_dir=str(self.archive_dir))
            card.cleared.connect(self._on_reference_cleared)
            card.uploaded.connect(self._on_reference_uploaded)
            card.upload_failed.connect(self._on_reference_upload_failed)
            self.reference_cards.append(card)
            thumb_row.addWidget(card)

        left_layout.addLayout(thumb_row)

        # ---------- Schalter ----------
        self.remove_c2pa_checkbox = OptionCheckBox("C2PA-Daten nach Download entfernen")
        self.remove_c2pa_checkbox.setChecked(config.remove_c2pa_data)
        self.remove_c2pa_checkbox.toggled.connect(self._on_remove_c2pa_toggled)
        # In Klammern steht, wie oft höchstens wiederholt wird (max_retries).
        self.auto_retry_checkbox = OptionCheckBox(f"Autoretry ({config.max_retries})")
        self.auto_retry_checkbox.setChecked(config.auto_retry)
        self.auto_retry_checkbox.setToolTip(
            f"Wiederholt die Generierung nach einem Fehler bis zu {config.max_retries}-mal "
            "(max_retries in der config.ini). ⊗ Cancel beendet die Wiederholungen nur "
            "für den laufenden Durchgang, der Haken bleibt."
        )
        self.auto_retry_checkbox.toggled.connect(self._on_auto_retry_toggled)

        # Mittig über dem Generate-Knopf: links und rechts gleich viel Platz.
        options_row = QHBoxLayout()
        options_row.setSpacing(20)
        options_row.addStretch(1)
        options_row.addWidget(self.remove_c2pa_checkbox)
        options_row.addWidget(self.auto_retry_checkbox)
        options_row.addStretch(1)
        left_layout.addLayout(options_row)

        # ---------- Generate-Knopf ----------
        self.generate_btn = GenerateAiButton("✨ Generate AI", busy_text=CANCEL_TEXT)
        self.generate_btn.setFont(QFont("", 14, QFont.Weight.Bold))
        left_layout.addWidget(self.generate_btn)

        # Ausgefahren reicht das Prompt-Feld bis an die Oberkante des Knopfes:
        # die Einstellungen sind zugedeckt, der Knopf bleibt bedienbar.
        self.prompt.set_expand_stop(self.generate_btn)

        # ---------- Bildvorschau ----------
        # Ein Klick öffnet das zuletzt erzeugte Bild im Standardprogramm.
        self.image_label = QLabel("🗋")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(900, 900)
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_label.setStyleSheet("border:1px solid #333; font-size:40px;")
        self.image_label.mousePressEvent = self._on_image_clicked
        right_layout.addWidget(self.image_label)

        # ---------- Statuszeile ----------
        status_row = QHBoxLayout()
        self.status_slot = QWidget()
        self.status_slot.setFixedHeight(20)
        self.status_slot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.credits_label = QLabel("💰 --")
        self.credits_label.setFixedHeight(20)
        self.credits_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.credits_label.setStyleSheet("color:#8fd18f; font-size:11px;")

        status_row.addWidget(self.status_slot)
        status_row.addWidget(self.credits_label)
        right_layout.addLayout(status_row)

        # =====================================================
        # FINAL LAYOUT
        # =====================================================
        root_layout.addLayout(left_layout, 1)
        root_layout.addLayout(right_layout, 1)

        # Statusanzeige schwebt über dem Platzhalter und klappt bei langen
        # Meldungen nach oben auf, statt das Fenster zu vergrößern.
        self.status = StatusBar(self.status_slot, self)
        self.status.setText("Idle")

        # =====================================================
        # ZUSTAND EINES DURCHGANGS
        # =====================================================
        self.generate_btn.clicked.connect(self._on_generate_clicked)

        # 1 = erster Versuch, 2 = erste Wiederholung, ...
        self._generation_attempt = 1
        # Läuft ein Durchgang (auch in der Wartezeit vor einer Wiederholung)?
        # Und wurde für ihn Cancel gedrückt?
        self._running = False
        self._cancelled = False
        # Wartezeit zwischen zwei automatischen Versuchen
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._run_generation)

        self.loading_overlay = LoadingOverlayGemini(self.image_label, "assets/gemini_symbol.png")

        # Parameter-Bereich für das vorausgewählte Modell aufbauen
        self._on_model_changed(self.model_dropdown.currentText())

        self.load_archive_folders()
        QTimer.singleShot(300, self.refresh_credits_async)

    # ------------------------------------------------------------------
    # Dynamischer Parameter-Bereich
    # ------------------------------------------------------------------

    def _clear_param_layout(self) -> None:
        while self.param_layout.rowCount() > 0:
            self.param_layout.removeRow(0)
        self.param_widgets.clear()

    def _on_model_changed(self, display_name: str) -> None:
        """Baut den Parameter-Bereich für das ausgewählte Modell neu auf."""
        spec = get_model_by_display_name(display_name)
        if not spec:
            return

        self._clear_param_layout()

        for param in spec.params:
            widget = self._build_param_widget(param)
            self.param_widgets[param.name] = widget
            # Kästchen bringen ihre Beschriftung selbst mit, rechts daneben.
            label = "" if isinstance(widget, QCheckBox) else param.label
            self.param_layout.addRow(label, widget)

        # Miniaturen, die das Modell nicht nutzen kann, sperren
        for index, card in enumerate(self.reference_cards):
            card.setEnabled(index < spec.max_images)

    @staticmethod
    def _build_param_widget(param: ParamSpec) -> QWidget:
        """Erzeugt für einen ParamSpec das passende Eingabefeld."""
        if param.kind == "enum":
            dropdown = ParamDropdown()
            for option in param.options:
                dropdown.addItem(str(option))
            if param.default is not None:
                index = dropdown.findText(str(param.default))
                if index >= 0:
                    dropdown.setCurrentIndex(index)
            return dropdown

        if param.kind == "bool":
            # Die Beschriftung steht rechts neben dem Kästchen, wie bei C2PA
            # und Autoretry — die Spalte links bleibt für diese Zeile leer.
            checkbox = OptionCheckBox(param.label)
            checkbox.setChecked(bool(param.default))
            return checkbox

        if param.kind == "int":
            spinbox = QSpinBox()
            spinbox.setRange(int(param.min_value), int(param.max_value))
            spinbox.setSingleStep(int(param.step) if param.step else 1)
            if param.default is not None:
                spinbox.setValue(int(param.default))
            return spinbox

        if param.kind == "float":
            spinbox = QDoubleSpinBox()
            spinbox.setRange(float(param.min_value), float(param.max_value))
            step = float(param.step) if param.step else 0.1
            spinbox.setSingleStep(step)
            spinbox.setDecimals(_decimals_for_step(step))
            if param.default is not None:
                spinbox.setValue(float(param.default))
            return spinbox

        # Alles andere: einfaches Textfeld (z.B. negative_prompt)
        line_edit = QLineEdit()
        if param.default is not None:
            line_edit.setText(str(param.default))
        return line_edit

    def _read_param_values(self) -> dict[str, Any]:
        """Liest die aktuellen Werte aller Felder im Parameter-Bereich."""
        values: dict[str, Any] = {}
        spec = get_model_by_display_name(self.model_dropdown.currentText())
        if not spec:
            return values

        for param in spec.params:
            widget = self.param_widgets.get(param.name)
            if widget is None:
                continue
            if isinstance(widget, QComboBox):
                values[param.name] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                values[param.name] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                values[param.name] = int(widget.value())
            elif isinstance(widget, QDoubleSpinBox):
                values[param.name] = round(float(widget.value()), 4)
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                if text:
                    values[param.name] = text
        return values

    # ------------------------------------------------------------------
    # Splash
    # ------------------------------------------------------------------

    def _show_splash(self) -> None:
        try:
            splash_config = build_splash_config(self.config)
        except ValueError as exc:
            self.status.setText(f"[Splash] in config.ini ungültig ({exc}) – Standardwerte werden verwendet.")
            splash_config = SplashConfig()
        show_splash(self, splash_config, self.build_info)

    # ------------------------------------------------------------------
    # Ordnerauswahl
    # ------------------------------------------------------------------

    def load_archive_folders(self) -> None:
        """Füllt die Ordnerauswahl mit den Unterordnern des Archivordners."""
        self.folder_dropdown.clear()

        if not self.archive_dir.is_dir():
            self._disable_folder_selection(
                "⚠ Archivordner nicht gefunden",
                f"Archivordner nicht gefunden: {self.archive_dir} -> Bitte in config.ini anpassen!",
            )
            return

        try:
            folders = [entry for entry in self.archive_dir.iterdir() if entry.is_dir()]
        except OSError as exc:
            self._disable_folder_selection(
                "⚠ Archivordner nicht lesbar",
                f"Archivordner nicht lesbar: {self.archive_dir} ({exc})",
            )
            return

        if not folders:
            self._disable_folder_selection(
                "⚠ Keine Ordner vorhanden",
                f"Keine Unterordner in: {self.archive_dir} -> Bitte mindestens einen Ordner anlegen!",
            )
            return

        self.folder_dropdown.setEnabled(True)
        self.folder_dropdown.setPlaceholderText("WÄHLE EINEN ORDNER")
        for folder in folders:
            self.folder_dropdown.addItem(folder.name)
        # Noch nichts gewählt: der Platzhalter steht in der Leiste.
        self.folder_dropdown.setCurrentIndex(-1)

    def _disable_folder_selection(self, dropdown_text: str, status_text: str) -> None:
        """Ohne Zielordner ist keine Generierung möglich."""
        self.folder_dropdown.addItem(dropdown_text)
        self.folder_dropdown.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.status.setText(status_text)

    def blink_folder_dropdown(self) -> None:
        """Zeigt, dass der Ordner fehlt: Meldung unten, der Rahmen blinkt rot.

        Ist das Prompt-Feld ausgefahren, deckt es die Ordnerauswahl zu. Dann
        fährt es erst ein; geblinkt wird, sobald die Auswahl zu sehen ist.
        """
        self.status.setText("Bitte zuerst einen Ordner wählen.")
        # Ein Stylesheet wirkt auf das selbstgezeichnete Feld nicht — dafür
        # lässt es seinen Rahmen selbst rot blinken.
        if not self.prompt.is_expanded():
            self.folder_dropdown.flash()
            return
        self.prompt.collapse()
        QTimer.singleShot(self.prompt.GROW_MS, self.folder_dropdown.flash)

    # ------------------------------------------------------------------
    # Generierung
    #
    # Ein Durchgang besteht aus einem Versuch und — mit Autoretry — bis zu
    # max_retries Wiederholungen. Solange er läuft, ist der Generate-Knopf
    # der Cancel-Knopf.
    # ------------------------------------------------------------------

    def _on_generate_clicked(self) -> None:
        """Derselbe Knopf startet und bricht ab — je nachdem, ob etwas läuft."""
        if self._running:
            self.cancel_generation()
        else:
            self.start_generation()

    def start_generation(self) -> None:
        """Startet einen neuen Durchgang: einen Versuch und, falls nötig, Wiederholungen."""
        self._retry_timer.stop()
        self._generation_attempt = 1
        self._cancelled = False
        self._run_generation()

    def cancel_generation(self) -> None:
        """Cancel: für diesen Durchgang keine Wiederholung mehr.

        Der laufende Auftrag wird nicht abgebrochen — er läuft bei der API
        ohnehin weiter. Es wird gewartet, bis er ein Bild oder einen Fehler
        liefert; danach ist Schluss. Das Autoretry-Kästchen bleibt, wie es ist.
        """
        if self._retry_timer.isActive():
            # Zwischen zwei Versuchen läuft kein Auftrag — also sofort Schluss.
            self._abort_generation("Wiederholung abgebrochen.")
            return
        self._cancelled = True
        self.generate_btn.setEnabled(False)
        self.generate_btn.setBusyText(FINISHING_TEXT)
        self.status.setText(
            "Abgebrochen – keine Wiederholung mehr, warte noch auf das Ergebnis "
            "des laufenden Auftrags ..."
        )

    def _run_generation(self) -> None:
        """Führt einen einzelnen Generierungsversuch aus."""
        self._set_generate_btn_loading()

        if not self.api.api_key:
            self._abort_generation("API-Key nicht gesetzt!")
            return
        if not self.imgbb_api_key:
            self._abort_generation("IMGBB API-Key nicht gesetzt!")
            return

        if not self.folder_dropdown.isEnabled() or self.folder_dropdown.currentIndex() < 0:
            self.blink_folder_dropdown()
            self._abort_generation()
            return
        target_folder = self.archive_dir / self.folder_dropdown.currentText() / "ai"

        spec = get_model_by_display_name(self.model_dropdown.currentText())
        if not spec:
            self._abort_generation("Unbekanntes Modell ausgewählt")
            return

        # Der vorige Worker hat sein Ergebnis schon gemeldet, kann aber noch
        # im Beenden sein. Ein QThread darf nicht gelöscht werden, solange er
        # läuft — also kurz warten, bevor er ersetzt wird.
        if self.worker is not None:
            self.worker.wait()

        self.worker = GenerationWorker(
            api                = self.api,
            model_spec         = spec,
            prompt             = self.prompt.toPlainText(),
            reference_urls     = list(self.reference_urls),
            param_values       = self._read_param_values(),
            callback_url       = self.callback_url,
            target_folder      = target_folder,
            remove_c2pa        = self.remove_c2pa_checkbox.isChecked(),
            download_attempts  = self.config.download_attempts,
            download_timeout_s = self.config.download_timeout_s,
        )
        self.worker.status.connect(self._on_worker_status)
        self.worker.succeeded.connect(self._on_generation_succeeded)
        self.worker.failed.connect(self._on_generation_failed)

        self.image_label.setText("")
        self.loading_overlay.start()
        self.worker.start()

    def _on_worker_status(self, text: str) -> None:
        if self._generation_attempt > 1:
            text = f"[Wiederholung {self._generation_attempt - 1}/{self.config.max_retries}] {text}"
        if self._cancelled:
            text = f"[Abgebrochen, letzter Auftrag] {text}"
        self.status.setText(text)

    def _on_generation_succeeded(self, image_path: str) -> None:
        self.loading_overlay.stop()
        self._reset_generate_btn()
        flash_taskbar(int(self.winId()))
        self.last_image_path = image_path

        pixmap = QPixmap(image_path).scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(pixmap)
        self.status.setText("Fertig")
        self.refresh_credits_async()

    def _on_generation_failed(self, message: str) -> None:
        """Wiederholt die Generierung — höchstens max_retries-mal, nach Cancel nicht mehr."""
        max_retries = self.config.max_retries
        retries_done = self._generation_attempt - 1
        retry = (
            self.auto_retry_checkbox.isChecked()
            and not self._cancelled
            and retries_done < max_retries
        )
        if retry:
            delay_s = max(1, self.config.retry_delay_s)
            self._generation_attempt += 1
            self.status.setText(
                f"Fehler: {message} – Wiederholung {retries_done + 1}/{max_retries} "
                f"in {delay_s} s ..."
            )
            self._retry_timer.start(delay_s * 1000)
            return

        if self._cancelled:
            text = f"Fehler: {message} (abgebrochen, keine Wiederholung)"
        elif self.auto_retry_checkbox.isChecked():
            text = f"Fehler nach {max_retries} Wiederholungen: {message}"
        else:
            text = f"Fehler: {message}"
        self._abort_generation(text)
        flash_taskbar(int(self.winId()))

    def _abort_generation(self, message: str = "") -> None:
        """Beendet den Durchgang inkl. einer wartenden Wiederholung."""
        self._retry_timer.stop()
        self.loading_overlay.stop()
        self._reset_generate_btn()
        if message:
            self.status.setText(message)

    def _set_generate_btn_loading(self) -> None:
        # Der Knopf bleibt klickbar — solange der Durchgang läuft, ist er Cancel.
        self._running = True
        self.generate_btn.setEnabled(True)
        self.generate_btn.start_busy(CANCEL_TEXT)

    def _reset_generate_btn(self) -> None:
        self._running = False
        self._cancelled = False
        self.generate_btn.stop_busy()
        self.generate_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Schalter (werden sofort in der config.ini gespeichert)
    # ------------------------------------------------------------------

    def _on_remove_c2pa_toggled(self, checked: bool) -> None:
        self.config.remove_c2pa_data = checked
        self._save_config()

    def _on_auto_retry_toggled(self, checked: bool) -> None:
        # Läuft gerade eine Wartezeit, wird die Wiederholung sofort abgebrochen.
        if not checked and self._retry_timer.isActive():
            self._abort_generation("Automatische Wiederholung gestoppt.")
            flash_taskbar(int(self.winId()))

        self.config.auto_retry = checked
        self._save_config()

    def _save_config(self) -> None:
        try:
            self.config.save()
        except ConfigError as exc:
            self.status.setText(f"Einstellung konnte nicht gespeichert werden: {exc}")

    # ------------------------------------------------------------------
    # Referenzbilder
    # ------------------------------------------------------------------

    def _on_reference_cleared(self, index: int) -> None:
        self.reference_urls[index] = None

    def _on_reference_uploaded(self, index: int, url: str) -> None:
        self.reference_urls[index] = url

    def _on_reference_upload_failed(self, index: int, error: str) -> None:
        self.status.setText(f"Upload Referenzbild {index + 1} fehlgeschlagen: {error}")

    # ------------------------------------------------------------------
    # Credits
    # ------------------------------------------------------------------

    def refresh_credits_async(self) -> None:
        if self.credits_worker is not None and self.credits_worker.isRunning():
            return
        self.credits_label.setText("💰 ...")
        self.credits_worker = CreditsWorker(self.api)
        self.credits_worker.result.connect(self._on_credits_received)
        self.credits_worker.start()

    def _on_credits_received(self, balance: float) -> None:
        self.credits_label.setText("💰 ?" if balance < 0 else f"💰 {int(balance)}")

    # ------------------------------------------------------------------
    # Sonstiges
    # ------------------------------------------------------------------

    def _on_image_clicked(self, event) -> None:
        """Öffnet das zuletzt erzeugte Bild im Standardprogramm von Windows."""
        if not self.last_image_path or not os.path.exists(self.last_image_path):
            return
        try:
            os.startfile(self.last_image_path)
        except OSError as exc:
            self.status.setText(f"Bild konnte nicht geöffnet werden: {exc}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # resizeEvent kommt schon während __init__, bevor die schwebenden
        # Widgets existieren.
        if hasattr(self, "prompt"):
            self.prompt.sync_geometry()
        if hasattr(self, "status"):
            self.status.sync_geometry()


def _decimals_for_step(step: float) -> int:
    """Nachkommastellen eines Zahlenfelds, passend zur Schrittweite."""
    if step >= 1:
        return 0
    if step >= 0.1:
        return 1
    if step >= 0.01:
        return 2
    return 3
