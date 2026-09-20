# controls.py
#
# Die Bedienelemente aus qt-controls-pyrs, auf dieses Programm eingestellt.
# Was hier von der Sammlung abweicht, steht an einer Stelle statt an jeder
# Fundstelle im Fenster.

from __future__ import annotations

from qt_controls_pyrs import FiberHaloButton


class GenerateAiButton(FiberHaloButton):
    """Der große Knopf, der die Generierung startet.

    Unter der Maus wandert sein Rahmen nach außen und der Knopf leuchtet auf.
    Solange eine Generierung läuft, füllen ziehende Farbflächen und schwingende
    Glasfasern seine Fläche — auch dann, wenn er dabei gesperrt ist.
    """

    # Die Beschriftung bleibt so stehen, wie sie geschrieben ist ("✨ Generate
    # AI"), statt in Großbuchstaben zu erscheinen.
    UPPERCASE = False

    # Die Fläche ist so hoch wie beim alten Knopf; die 16 Pixel Rand je Seite
    # für den auswandernden Rahmen kommen oben und unten dazu, deshalb braucht
    # es hier kein setFixedHeight mehr.
    HEIGHT = 50

    # Das Fenster schaltet die Anzeige selbst ein und aus
    # (_set_generate_btn_loading / _reset_generate_btn). Ein Klick allein soll
    # deshalb noch nichts starten — sonst liefe die Anzeige auch dann, wenn ein
    # Versuch gleich wieder abbricht.
    AUTO_BUSY = False

    # Dieselbe Farbe wie QPalette.Highlight des Programms. Sie färbt die
    # ganze Anzeige: Grund, ziehende Flächen, Lichter und Fasern.
    ACCENT = "#5a8cff"
