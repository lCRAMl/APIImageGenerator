# GeminiAPI.py

import sys
import time
import os
import json
import base64
import requests
import winreg
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QComboBox,
    QFileDialog, QStyleFactory, QSizePolicy, QCheckBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QPlainTextEdit, QFormLayout, QFrame
)
from PyQt6.QtGui import QPixmap, QPalette, QColor, QFont, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal as Signal, QTimer

from loading_overlay import LoadingOverlayGemini
from referencethumb import ReferenceThumb
from config import AppConfig
from SplashScreenPython.splash_video_webP import SplashScreen
from models_registry import MODELS, ModelSpec, ParamSpec, get_model_by_display_name
from ui.flashtaskbar import flash_taskbar

# =========================
# CONFIG
# =========================
config = AppConfig()
ARCHIVE_DIR = config.archive_path
from build_version import BUILD_INFO, VERSION, BUILD_TIME, APP_NAME

def is_windows_dark_mode() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except Exception:
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
# API CLIENT (generisch)
# ==========================

class KieAPI:
    """
    Generischer kie.ai-kompatibler Client.
    URLs werden aus der Konfiguration gelesen und nicht fest im Code verdrahtet.
    """

    def __init__(
        self,
        api_key: str,
        generate_url: str,
        status_url: str,
        credits_url: str,
    ) -> None:
        self.api_key = api_key
        self.generate_url = generate_url
        self.status_url = status_url
        self.credits_url = credits_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def create_task(self, api_model: str, callback_url: str, input_payload: dict) -> str:
        """Legt einen Generierungs-Task an und gibt die taskId zurück."""
        payload = {
            "model":       api_model,
            "callBackUrl": callback_url,
            "input":       input_payload,
        }
        try:
            r = requests.post(self.generate_url, headers=self.headers, json=payload, timeout=60)
        except requests.RequestException as exc:
            raise Exception(f"Netzwerkfehler beim Task-Erzeugen: {exc}") from exc

        try:
            data = r.json()
        except ValueError:
            raise Exception(f"Ungültige Antwort vom Server ({r.status_code}): {r.text[:200]}")

        if not r.ok:
            raise Exception(data.get("msg") or data.get("message") or f"HTTP {r.status_code}")
        code = data.get("code")
        if code is not None and code != 200:
            raise Exception(data.get("msg") or data.get("message") or f"API-Fehlercode {code}")

        task_id = (data.get("data") or {}).get("taskId")
        if not task_id:
            raise Exception(f"Keine taskId in der Antwort: {r.text[:200]}")
        return task_id

    def get_task_status(self, task_id: str) -> tuple[dict, str | None]:
        """
        Fragt den Status eines Tasks ab.

        Returns:
            (data, error) — data ist das "data"-Objekt der Antwort (oder {}),
            error ist None bei Erfolg oder eine lesbare Fehlermeldung sonst.
        """
        try:
            r = requests.get(
                f"{self.status_url}?taskId={task_id}",
                headers=self.headers,
                timeout=60,
            )
        except requests.RequestException as exc:
            return {}, f"Netzwerkfehler beim Statusabruf: {exc}"

        try:
            body = r.json()
        except ValueError:
            return {}, f"Ungültige Statusantwort (HTTP {r.status_code}): {r.text[:200]}"

        if not r.ok:
            msg = body.get("msg") or body.get("message") or f"HTTP {r.status_code}"
            return body.get("data") or {}, f"Status-Endpoint Fehler: {msg}"

        code = body.get("code")
        if code is not None and code != 200:
            msg = body.get("msg") or body.get("message") or f"code {code}"
            return body.get("data") or {}, f"API-Fehler: {msg}"

        return body.get("data") or {}, None

    def get_account_credits(self) -> float:
        r = requests.get(self.credits_url, headers=self.headers, timeout=15)
        try:
            body = r.json()
        except ValueError:
            return -1.0
        val = body.get("data")
        if isinstance(val, dict):
            val = val.get("credits") or val.get("balance") or val.get("amount")
        try:
            return float(val) if val is not None else -1.0
        except (TypeError, ValueError):
            return -1.0


def _extract_image_url(status_data: dict) -> str | None:
    """Versucht, die Bild-URL aus verschiedenen Antwortformaten zu lesen."""

    # kie.ai-typisch: data.resultJson als String enthält { "resultUrls": [...] }
    # (manchmal ist es auch schon ein dict)
    result_json = status_data.get("resultJson")
    if result_json:
        parsed = result_json
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:
                parsed = None
        if isinstance(parsed, dict):
            for key in ("resultUrls", "result_urls", "resultImageUrls", "resultImageUrl", "images", "urls"):
                urls = parsed.get(key)
                if isinstance(urls, list) and urls:
                    return urls[0] if isinstance(urls[0], str) else urls[0].get("url")
                if isinstance(urls, str) and urls:
                    return urls

    # direkt am data-Objekt
    for key in ("resultUrls", "result_urls", "resultImageUrls", "images", "urls"):
        urls = status_data.get(key)
        if isinstance(urls, list) and urls:
            first = urls[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("url") or first.get("imageUrl")
    for key in ("resultImageUrl", "imageUrl", "url"):
        v = status_data.get(key)
        if isinstance(v, str) and v:
            return v

    # nanobanana-Legacy: response.resultImageUrl / response-Objekt generell
    resp = status_data.get("response")
    if isinstance(resp, dict):
        for key in ("resultImageUrl", "imageUrl", "url"):
            v = resp.get(key)
            if isinstance(v, str) and v:
                return v
        urls = resp.get("resultUrls")
        if isinstance(urls, list) and urls:
            return urls[0]

    return None


def _terminal_state(status_data: dict) -> tuple[bool, bool, str, str]:
    """
    Analysiert das Status-Objekt.

    Returns:
        (is_terminal, is_success, message, raw_state)
        raw_state ist der erkannte State als Text (für das UI-Log).
    """
    # kie.ai: "state" / andere APIs: "status" / "taskStatus"
    state_raw = (
        status_data.get("state")
        or status_data.get("status")
        or status_data.get("taskStatus")
    )
    state_str = str(state_raw).lower() if state_raw is not None else ""

    if state_str:
        if state_str in ("success", "succeeded", "succeed", "completed", "complete", "done", "finished"):
            return True, True, "", state_str
        if state_str in ("fail", "failed", "failure", "error"):
            msg = (
                status_data.get("failMsg")
                or status_data.get("failMessage")
                or status_data.get("errorMessage")
                or status_data.get("msg")
                or "Generierung fehlgeschlagen"
            )
            return True, False, str(msg), state_str
        # bekannte "in progress"-States: waiting, queuing, generating, wait, pending, running
        # → nicht terminal, weiter pollen
        return False, False, "", state_str

    # Legacy nanobanana: successFlag ∈ {0:wartet, 1:ok, 2/3:fehler}
    flag = status_data.get("successFlag")
    if flag == 1:
        return True, True, "", "flag=1"
    if flag in (2, 3):
        msg = status_data.get("errorMessage") or "Generierung fehlgeschlagen"
        return True, False, str(msg), f"flag={flag}"
    if flag == 0:
        return False, False, "", "flag=0"

    # Kein erkennbarer Status — wenn ein Bild-URL schon drin ist, behandeln wir das
    # als Erfolg (manche APIs liefern das Bild direkt ohne expliziten state).
    if _extract_image_url(status_data):
        return True, True, "", "no-state-but-url"

    return False, False, "", "unknown"


# ==========================
# WORKER THREAD
# ==========================

class GenerationWorker(QThread):
    status   = Signal(str)
    finished = Signal(str, str, str)  # local_image_path, prompt, task_id

    def __init__(
        self,
        api: KieAPI,
        model_spec: ModelSpec,
        prompt: str,
        reference_files: list,
        param_values: dict,
        callback_url: str,
        target_folder: Path,
        win_id: int,
    ) -> None:
        super().__init__()
        self.api = api
        self.model_spec = model_spec
        self.prompt = prompt
        self.reference_files = reference_files
        self.param_values = param_values
        self.callback_url = callback_url
        self.target_folder = target_folder
        self.win_id = win_id

    def run(self) -> None:
        try:
            # --- Referenzbilder vorbereiten ---
            self.status.emit("Bereite Referenzbilder vor ...")
            image_urls: list[str] = []
            for f in self.reference_files:
                if not f:
                    continue
                if f.startswith("http"):
                    image_urls.append(f)
                else:
                    with open(f, "rb") as file:
                        encoded = base64.b64encode(file.read()).decode("utf-8")
                        image_urls.append(f"data:image/png;base64,{encoded}")

            # auf max_images des Modells begrenzen
            image_urls = image_urls[: self.model_spec.max_images]

            # --- Input-Payload bauen ---
            input_payload: dict = {self.model_spec.prompt_field: self.prompt}

            if self.model_spec.max_images > 0 and image_urls:
                if self.model_spec.images_is_list:
                    input_payload[self.model_spec.images_field] = image_urls
                else:
                    # Modell erwartet einen einzelnen String (z.B. Qwen, Qwen2)
                    input_payload[self.model_spec.images_field] = image_urls[0]

            # Modell-spezifische Parameter ergänzen
            for key, value in self.param_values.items():
                input_payload[key] = value

            # --- Task starten ---
            self.status.emit(f"Sende Generierungsanfrage ({self.model_spec.display_name}) ...")
            task_id = self.api.create_task(
                api_model=self.model_spec.api_model,
                callback_url=self.callback_url,
                input_payload=input_payload,
            )
            self.status.emit(f"Task erstellt: {task_id}. Warte auf Ergebnis ...")

            # --- Polling ---
            start = time.time()
            last_state = ""
            unknown_count = 0
            while time.time() - start < 600:
                status_data, err = self.api.get_task_status(task_id)

                # HTTP-/API-Fehler beim Statusabruf sofort eskalieren.
                if err:
                    flash_taskbar(self.win_id)
                    raise Exception(err)

                is_terminal, is_success, msg, raw_state = _terminal_state(status_data)

                if is_terminal and is_success:
                    flash_taskbar(self.win_id)
                    image_url = _extract_image_url(status_data)
                    if not image_url:
                        raise Exception(
                            "Erfolgsmeldung erhalten, aber keine Bild-URL gefunden. "
                            f"Antwort: {json.dumps(status_data)[:400]}"
                        )

                    self.status.emit("Lade Bild herunter ...")

                    # Dateiendung bestimmen
                    ext = self.param_values.get("output_format") or "png"
                    if ext == "jpeg":
                        ext = "jpg"

                    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
                    local_path = self.target_folder / f"{ts}.{ext}"
                    txt_path   = self.target_folder / f"{ts}.txt"

                    r = requests.get(image_url, timeout=30, stream=True)
                    r.raise_for_status()
                    with open(local_path, "wb") as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(self.prompt)

                    self.finished.emit(str(local_path), self.prompt, task_id)
                    return

                if is_terminal and not is_success:
                    flash_taskbar(self.win_id)
                    raise Exception(msg or "Generierung fehlgeschlagen")

                # nicht-terminal — Zähler für unbekannten State führen
                if raw_state == "unknown":
                    flash_taskbar(self.win_id)
                    unknown_count += 1
                    if unknown_count >= 3:
                        # nach 3 erfolglosen Polls: Rohdaten anzeigen, damit sichtbar wird,
                        # was die API tatsächlich liefert (Fehldiagnose vermeiden).
                        raise Exception(
                            "Unbekanntes Status-Antwortformat. "
                            f"Beispiel-Antwort: {json.dumps(status_data)[:400]}"
                        )
                else:
                    unknown_count = 0

                if raw_state != last_state:
                    self.status.emit(f"Bild wird generiert [{raw_state}] ... {task_id}")
                    last_state = raw_state
                time.sleep(3)

            raise Exception("Timeout – Bild konnte nicht generiert werden")

        except Exception as e:
            self.status.emit(f"Fehler: {e}")


# ==========================
# CREDITS WORKER
# ==========================

class CreditsWorker(QThread):
    result = Signal(float)

    def __init__(self, api: KieAPI, parent=None) -> None:
        super().__init__(parent)
        self.api = api

    def run(self) -> None:
        try:
            self.result.emit(self.api.get_account_credits())
        except Exception:
            self.result.emit(-1.0)


# ==========================
# MAIN WINDOW
# ==========================

class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.api = KieAPI(
            api_key=config.nanobanana_api_key or "",
            generate_url=config.generate_url,
            status_url=config.status_url,
            credits_url=config.credits_url,
        )
        self.imgbb_api_key = config.imgbb_api_key or ""
        self.callback_url  = config.callback_url
        self.last_image_path: str | None = None

        # Widget-Registry für dynamische Parameter (param_name -> widget)
        self.param_widgets: dict[str, QWidget] = {}

        self.setWindowTitle(BUILD_INFO)
        self.resize(1600, 900)

        icon_path = (
            Path(sys._MEIPASS) / "assets/gemini_icon.ico"
            if getattr(sys, "frozen", False)
            else Path("assets/gemini_icon.ico")
        )
        self.setWindowIcon(QIcon(str(icon_path)))

        # =====================================================
        # LAYOUTS
        # =====================================================
        root_layout  = QHBoxLayout(self)
        left_layout  = QVBoxLayout()
        right_layout = QVBoxLayout()

        # ---------- Prompt (schlicht, kein Highlighting) ----------
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Prompt eingeben ...")
        self.prompt.setMinimumHeight(180)
        left_layout.addWidget(self.prompt)

        # ---------- Folder Dropdown + Info Button (unverändert) ----------
        self.folder_dropdown = QComboBox()
        self.folder_dropdown.setFixedHeight(40)
        self.folder_dropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        dropdown_font = QFont()
        dropdown_font.setPointSize(14)
        self.folder_dropdown.setFont(dropdown_font)

        self.info_btn = QPushButton("ℹ")
        self.info_btn.setFixedSize(40, 40)
        self.info_btn.setFont(QFont("Segoe UI", 14))
        self.info_btn.setToolTip("Info / About")
        self.info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_btn.clicked.connect(self._show_splash)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        folder_row.addWidget(self.folder_dropdown)
        folder_row.addWidget(self.info_btn)
        left_layout.addLayout(folder_row)

        # ---------- Model-Dropdown ----------
        model_row = QHBoxLayout()
        model_label = QLabel("Model")
        model_label.setFixedWidth(80)
        self.model_dropdown = QComboBox()
        for spec in MODELS:
            self.model_dropdown.addItem(spec.display_name)
        self.model_dropdown.currentTextChanged.connect(self._on_model_changed)
        model_row.addWidget(model_label)
        model_row.addWidget(self.model_dropdown, 1)
        left_layout.addLayout(model_row)

        # ---------- Dynamischer Parameter-Bereich ----------
        self.param_frame = QFrame()
        self.param_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.param_layout = QFormLayout(self.param_frame)
        self.param_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.param_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.param_layout.setContentsMargins(10, 10, 10, 10)
        self.param_layout.setSpacing(6)
        left_layout.addWidget(self.param_frame)

        # ---------- Reference Thumbnails ----------
        thumb_row = QHBoxLayout()
        self.thumb_labels: list = []
        self.reference_images: list = [None] * 6

        for index in range(6):
            thumb = ReferenceThumb(index, self.imgbb_api_key)
            thumb.cleared.connect(self.clear_reference)
            thumb.uploaded.connect(self.reference_uploaded)
            self.thumb_labels.append(thumb)
            thumb_row.addWidget(thumb)

        left_layout.addLayout(thumb_row)

        # ---------- Generate Button ----------
        self.generate_btn = QPushButton("✨ Generate AI")
        self.generate_btn.setFixedHeight(50)
        self.generate_btn.setFont(QFont("", 14, QFont.Weight.Bold))
        left_layout.addWidget(self.generate_btn)

        # ---------- Image Preview ----------
        self.image_label = QLabel("🗋")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(900, 900)
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_label.setStyleSheet("border:1px solid #333; font-size:40px;")
        self.image_label.mousePressEvent = self.open_image_external
        right_layout.addWidget(self.image_label)

        # ---------- Status Bar ----------
        status_row = QHBoxLayout()
        self.status = QLabel("Idle")
        self.status.setFixedHeight(20)
        self.status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.credits_label = QLabel("💰 --")
        self.credits_label.setFixedHeight(20)
        self.credits_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.credits_label.setStyleSheet("color:#8fd18f; font-size:11px;")

        status_row.addWidget(self.status)
        status_row.addWidget(self.credits_label)
        right_layout.addLayout(status_row)

        # =====================================================
        # FINAL LAYOUT
        # =====================================================
        root_layout.addLayout(left_layout, 1)
        root_layout.addLayout(right_layout, 1)

        # =====================================================
        # SIGNALS
        # =====================================================
        self.generate_btn.clicked.connect(self.start_generation)

        self.loading_overlay = LoadingOverlayGemini(self.image_label, "assets/gemini_symbol.png")

        # Initialer Parameter-Bereich für das vorausgewählte Modell
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

        for p in spec.params:
            widget = self._build_param_widget(p)
            self.param_widgets[p.name] = widget
            self.param_layout.addRow(p.label, widget)

        # Ungenutzte Referenz-Thumbs deaktivieren
        for i, thumb in enumerate(self.thumb_labels):
            thumb.setEnabled(i < spec.max_images)

    @staticmethod
    def _build_param_widget(p: ParamSpec) -> QWidget:
        """Erzeugt für einen ParamSpec das passende Input-Widget."""
        kind = p.kind

        if kind == "enum":
            w = QComboBox()
            for opt in p.options:
                w.addItem(str(opt))
            if p.default is not None:
                idx = w.findText(str(p.default))
                if idx >= 0:
                    w.setCurrentIndex(idx)
            return w

        if kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(p.default))
            return w

        if kind == "int":
            w = QSpinBox()
            w.setRange(int(p.min_value), int(p.max_value))
            w.setSingleStep(int(p.step) if p.step else 1)
            if p.default is not None:
                w.setValue(int(p.default))
            return w

        if kind == "float":
            w = QDoubleSpinBox()
            w.setRange(float(p.min_value), float(p.max_value))
            step = float(p.step) if p.step else 0.1
            w.setSingleStep(step)
            # Anzahl Dezimalstellen aus Step ableiten
            if step >= 1:
                decimals = 0
            elif step >= 0.1:
                decimals = 1
            elif step >= 0.01:
                decimals = 2
            else:
                decimals = 3
            w.setDecimals(decimals)
            if p.default is not None:
                w.setValue(float(p.default))
            return w

        # Fallback: einfaches Textfeld (z.B. negative_prompt)
        w = QLineEdit()
        if p.default is not None:
            w.setText(str(p.default))
        return w

    def _read_param_values(self) -> dict[str, Any]:
        """Liest die aktuellen Werte aller dynamischen Parameter aus."""
        values: dict[str, Any] = {}
        spec = get_model_by_display_name(self.model_dropdown.currentText())
        if not spec:
            return values

        for p in spec.params:
            w = self.param_widgets.get(p.name)
            if w is None:
                continue
            if isinstance(w, QComboBox):
                values[p.name] = w.currentText()
            elif isinstance(w, QCheckBox):
                values[p.name] = w.isChecked()
            elif isinstance(w, QSpinBox):
                values[p.name] = int(w.value())
            elif isinstance(w, QDoubleSpinBox):
                values[p.name] = round(float(w.value()), 4)
            elif isinstance(w, QLineEdit):
                txt = w.text().strip()
                if txt:
                    values[p.name] = txt
        return values

    # ------------------------------------------------------------------
    # Splash
    # ------------------------------------------------------------------

    def _show_splash(self) -> None:
        splash = SplashScreen(
            build_info=BUILD_INFO,
            parent=self,
        )
        splash.show_centered(self)

    # ------------------------------------------------------------------
    # Folder
    # ------------------------------------------------------------------

    def load_archive_folders(self) -> None:
        self.folder_dropdown.clear()

        if not ARCHIVE_DIR.exists() or not ARCHIVE_DIR.is_dir():
            self.folder_dropdown.addItem("⚠ Archivordner nicht gefunden")
            self.folder_dropdown.setEnabled(False)
            self.generate_btn.setEnabled(False)
            self.status.setText(
                f"Archivordner nicht gefunden: {ARCHIVE_DIR} -> Bitte in config.ini anpassen!"
            )
            return

        folders = [f for f in ARCHIVE_DIR.iterdir() if f.is_dir()]

        if not folders:
            self.folder_dropdown.addItem("⚠ Keine Ordner vorhanden")
            self.folder_dropdown.setEnabled(False)
            self.generate_btn.setEnabled(False)
            self.status.setText(
                f"Keine Unterordner in: {ARCHIVE_DIR} -> Bitte mindestens einen Ordner anlegen!"
            )
            return

        self.folder_dropdown.setEnabled(True)
        self.folder_dropdown.addItem("WÄHLE EINEN ORDNER")
        for folder in folders:
            self.folder_dropdown.addItem(folder.name)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def start_generation(self) -> None:
        self._set_generate_btn_loading()

        if not self.api.api_key:
            self.status.setText("API-Key nicht gesetzt!")
            self._reset_generate_btn()
            return
        if not self.imgbb_api_key:
            self.status.setText("IMGBB API-Key nicht gesetzt!")
            self._reset_generate_btn()
            return

        selected_folder = self.folder_dropdown.currentText()
        if not self.folder_dropdown.isEnabled() or selected_folder == "WÄHLE EINEN ORDNER":
            self.blink_folder_dropdown()
            self._reset_generate_btn()
            return

        target_folder = ARCHIVE_DIR / selected_folder / "ai"
        target_folder.mkdir(parents=True, exist_ok=True)
        self.target_folder = target_folder

        spec = get_model_by_display_name(self.model_dropdown.currentText())
        if not spec:
            self.status.setText("Unbekanntes Modell ausgewählt")
            self._reset_generate_btn()
            return

        param_values = self._read_param_values()

        self.worker = GenerationWorker(
            api           = self.api,
            model_spec    = spec,
            prompt        = self.prompt.toPlainText(),
            reference_files = self.reference_images,
            param_values  = param_values,
            callback_url  = self.callback_url,
            target_folder = target_folder,
            win_id        = int(self.winId()),
        )
        self.worker.status.connect(self.handle_status)
        self.worker.finished.connect(self.handle_result)

        self.image_label.setText("")
        self.loading_overlay.start()
        self.worker.start()

    def handle_result(self, local_image_path: str, prompt: str, task_id: str) -> None:
        self.loading_overlay.stop()
        self._reset_generate_btn()
        self.last_image_path = local_image_path

        pix = QPixmap(local_image_path).scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(pix)
        self.status.setText("Fertig")
        self.refresh_credits_async()

    def handle_status(self, text: str) -> None:
        self.status.setText(text)
        if text.startswith("Fehler"):
            self.loading_overlay.stop()
            self._reset_generate_btn()

    # ------------------------------------------------------------------
    # UI Helpers
    # ------------------------------------------------------------------

    def blink_folder_dropdown(self) -> None:
        self._blink_count = 0

        def toggle():
            if self._blink_count >= 6:
                self.folder_dropdown.setStyleSheet("")
                timer.stop()
                return
            self.folder_dropdown.setStyleSheet(
                "QComboBox { background-color: red; }" if self._blink_count % 2 == 0 else ""
            )
            self._blink_count += 1

        timer = QTimer(self)
        timer.timeout.connect(toggle)
        timer.start(100)

    def open_image_external(self, event) -> None:
        if self.last_image_path and os.path.exists(self.last_image_path):
            os.startfile(self.last_image_path)

    def refresh_credits_async(self) -> None:
        if hasattr(self, "credits_worker") and self.credits_worker.isRunning():
            return
        self.credits_label.setText("💰 ...")
        self.credits_worker = CreditsWorker(self.api)
        self.credits_worker.result.connect(self.on_credits_received)
        self.credits_worker.start()

    def on_credits_received(self, balance: float) -> None:
        self.credits_label.setText("💰 ?" if balance < 0 else f"💰 {int(balance)}")

    def clear_reference(self, index: int) -> None:
        self.reference_images[index] = None

    def reference_uploaded(self, index: int, url: str) -> None:
        self.reference_images[index] = url

    def load_reference(self, index: int) -> None:
        file, _ = QFileDialog.getOpenFileName(
            self, "Bild auswählen", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not file:
            return
        if file.startswith("http"):
            self.status.setText("URL-Referenz erkannt - kein Preview")
        else:
            pix = QPixmap(file).scaled(
                self.thumb_labels[index].size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.thumb_labels[index].setPixmap(pix)
        self.reference_images[index] = file

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "loading_overlay"):
            self.loading_overlay.resize(self.size())

    def _set_generate_btn_loading(self) -> None:
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("⏳ Generating...")

    def _reset_generate_btn(self) -> None:
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("✨ Generate AI")


# ==========================
# MAIN
# ==========================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if is_windows_dark_mode():
        app.setStyle(QStyleFactory.create("Fusion"))
        apply_dark_palette(app)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

