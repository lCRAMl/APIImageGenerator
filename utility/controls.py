# controls.py
#
# Die Bedienelemente aus qt-controls-pyrs, auf dieses Programm eingestellt.
# Was hier von der Sammlung abweicht, steht an einer Stelle statt an jeder
# Fundstelle im Fenster.

from __future__ import annotations

from qt_controls_pyrs import PulseHaloButton


class GenerateAiButton(PulseHaloButton):
    """Der große Knopf, der die Generierung startet.

    Unter der Maus wandert sein Rahmen nach außen und der Knopf leuchtet auf.
    Solange eine Generierung läuft, lösen sich ruhig Striche aus dem Rahmen und
    wandern nach außen, und die Beschriftung blendet auf den Arbeitstext über.
    Die Fläche bleibt dabei leer — nichts blinkt, nichts flimmert.

    Die Anzeige bleibt auch dann kräftig, wenn der Knopf während der
    Generierung gesperrt ist.
    """

    # Die Beschriftung bleibt so stehen, wie sie geschrieben ist ("✨ Generate
    # AI"), statt in Großbuchstaben zu erscheinen.
    UPPERCASE = False

    # Die Fläche ist so hoch wie beim alten Knopf; die 16 Pixel Rand je Seite,
    # in die Halo-Strich und Anzeige hinauswandern, kommen oben und unten dazu.
    # Deshalb braucht es hier kein setFixedHeight mehr.
    HEIGHT = 50

    # Das Fenster schaltet die Anzeige selbst ein und aus
    # (_set_generate_btn_loading / _reset_generate_btn). Ein Klick allein soll
    # deshalb noch nichts starten — sonst liefe die Anzeige auch dann, wenn ein
    # Versuch gleich wieder abbricht.
    AUTO_BUSY = False

    # Dieselbe Farbe wie QPalette.Highlight des Programms.
    ACCENT = "#5a8cff"

    # Ein Durchlauf der wandernden Striche. Länger heißt ruhiger.
    CYCLE_MS = 2800
