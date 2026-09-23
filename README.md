# APIImageGenerator

Windows-Desktopprogramm (PyQt6), das über eine kie.ai-kompatible API Bilder
erzeugt. Prompt und bis zu sechs Referenzbilder (per ImgBB hochgeladen) gehen an
das gewählte Modell; das Ergebnis wird im gewählten Archivordner gespeichert,
auf Wunsch ohne C2PA-Metadaten.

## Projektstruktur

```
APIImageGenerator.py     Einstiegspunkt: Konfiguration laden, Qt starten, Fenster zeigen
AUTOBUILD.py             Baut die EXE mit PyInstaller (schreibt build_version.py)

core/                    Programmlogik, ohne GUI
  config.py              config.ini lesen/schreiben (AppConfig)
  paths.py               Pfade zu config.ini und Ressourcen (Quellcode vs. EXE)
  build_info.py          Name, Version, Commit (aus build_version.py)
  models_registry.py     Unterstützte Modelle und ihre Parameter
  kie_api.py             API-Client und Auswertung der API-Antworten
  generation.py          Ein Durchlauf: Task anlegen, warten, herunterladen, speichern
  c2pa_cleaner.py        C2PA-Metadaten erkennen und entfernen

ui/                      Qt-Oberfläche
  ui.py                  Hauptfenster (MainWindow) und Farbschema
  controls.py            Bedienelemente aus qt-controls-pyrs, für dieses Programm eingestellt
  loading_overlay.py     Animation über der Bildvorschau während der Generierung
  splash.py              Splash hinter dem ℹ-Knopf (Paket qt_splash)
  workers.py             Hintergrund-Threads für Generierung und Guthaben

assets/                  Icon, Stern-Symbol
docs/                    API-Referenz der Modelle (kie.ai)
tests/                   pytest-Tests
```

`core/` importiert nichts aus `ui/` und kein Qt. Neue Logik gehört dorthin und
lässt sich ohne Fenster testen.

## Einrichten

```
git clone https://github.com/lCRAMl/APIImageGenerator.git
cd APIImageGenerator
pip install -r requirements-dev.txt
```

Die beiden eigenen Pakete liegen als eigene Projekte neben diesem und werden
für die Entwicklung editierbar installiert (Änderungen wirken sofort):

```
pip install -e ..\QtControlsPyRS          # qt_controls_pyrs: Bedienelemente
pip install -e ..\SplashScreenPython      # qt_splash: Splash-Screen
```

Das Splash-Video `SplashScreenPython\assets\splashvid\splash_ChloeGraceMoretz_90percent.webp`
(mit Tracking-Datei daneben) wird über den Installationsort von `qt_splash`
gefunden, braucht also die editierbare Installation. Welches Video, steht in
`ui/splash.py`.

## Konfiguration (`config.ini`)

Wird beim ersten Start im Projektordner angelegt (die EXE in `output/` liest
dieselbe Datei). Sie enthält die API-Keys im Klartext und ist deshalb nicht im
Repository.

| Abschnitt    | Schlüssel                                              | Bedeutung                                            |
|--------------|--------------------------------------------------------|------------------------------------------------------|
| `[Paths]`    | `archive_path`                                         | Archivordner; seine Unterordner stehen zur Auswahl   |
| `[API]`      | `nanobanana_api_key`, `imgbb_api_key`                  | Keys für kie.ai und ImgBB                            |
| `[URLs]`     | `generate_url`, `status_url`, `credits_url`, `callback_url` | Endpunkte der API                               |
| `[Options]`  | `remove_c2pa_data`, `auto_retry`, `retry_delay_s`, `max_retries` | Schalter und Autoretry                     |
| `[Download]` | `download_attempts`, `download_timeout_s`              | Versuche und Zeitlimit je Download                   |
| `[Splash]`   | `font_family`, `font_size_pt`, `text_color`, `outline_color` | Schrift im Splash; leere Schriftart = Systemschrift, Farben als `#rrggbb` |

Die Bilder landen in `<archive_path>/<gewählter Ordner>/ai/` als
`JJJJ-MM-TT_hh-mm-ss.<endung>`, daneben der Prompt als `.txt`.

## Starten

```
python APIImageGenerator.py
```

## Tests

```
python -m pytest
```

Die GUI-Tests laufen ohne sichtbares Fenster (Qt-Plattform `offscreen`).

## Build

```
python AUTOBUILD.py
```

Erzeugt `output/APIImageGenerator_<git-version>.exe` und eine
Startmenü-Verknüpfung. Die Version kommt aus `git describe --tags`. Das
Splash-Video wird aus dem SplashScreenPython-Projekt in die EXE gepackt.

## Ein neues Modell hinzufügen

Einen `ModelSpec`-Eintrag in `core/models_registry.py` ergänzen. Der
Parameter-Bereich im Fenster baut sich daraus von selbst auf; die Feldnamen
stehen in der API-Referenz unter `docs/`.
