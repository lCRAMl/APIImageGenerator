# controls.py
#
# Die Bedienelemente aus qt-controls-pyrs, auf dieses Programm eingestellt.
# Was hier von der Sammlung abweicht, steht an einer Stelle statt an jeder
# Fundstelle im Fenster.

from __future__ import annotations

from qt_controls_pyrs import (
    HaloCheckBox, HaloDropdown, HaloPromptBox, PulseHaloButton, ReferenceThumb
)


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

    # Eckenradius in Pixeln — 0 ist eckig. Rahmen, wandernde Striche und
    # Schein folgen der Rundung.
    RADIUS = 0


class OptionCheckBox(HaloCheckBox):
    """Die Kästchen des Programms: C2PA und Autoretry über dem Generate-Knopf
    und die Ja/Nein-Parameter der Modelle.

    Angehakt füllt sich innen ein Kern, und einmal läuft ein Strich aus dem
    Rahmen nach außen — die Bewegung des GenerateAiButton, im Kleinen.
    """

    # Eckenradius in Pixeln — 0 ist eckig, wie Knopf und Auswahlfelder.
    RADIUS = 0

    # Dieselbe Farbe wie QPalette.Highlight des Programms.
    ACCENT = "#5a8cff"


class ReferenceCard(ReferenceThumb):
    """Die Bild-Miniaturen für die Referenzbilder.

    Leer eine dunkle Karte, deren Rahmen dem Mauszeiger nachleuchtet; mit Bild
    bleibt das Leuchten auf dem Rahmen, und unter der Maus legt sich eine Decke
    mit einem runden X darüber.
    """

    # Glow Radius, der Referenzkarten einen leichten Schein verleiht, damit sie
    # sich vom Hintergrund abheben. Anteil der Kartenseite: 0.25 bleibt in der
    # eigenen Karte, ab etwa 0.75 leuchten die Nachbarinnen mit.
    GLOW_SPREAD = 0.45

    # Dieselbe Farbe wie QPalette.Highlight des Programms — und wie die Anzeige
    # des GenerateAiButton. Zur Laufzeit ginge auch thumb.setGlowColor(...).
    GLOW_COLOR = "#5a8cff"

    # Eckenradius der Karte in Pixeln — 0 ist eckig. Die Decke mit dem X,
    # die sich über ein geladenes Bild legt, folgt derselben Rundung.
    RADIUS = 0


class Dropdown(HaloDropdown):
    """Die Auswahlfelder des Programms — hier die Modellauswahl.

    Beim Aufklappen rollt die Liste weich auf, ein Buchstabe springt zum
    passenden Eintrag, und `flash()` lässt den Rahmen rot blinken.
    """

    # So hoch wie der ℹ-Knopf neben der Ordnerauswahl, damit die Reihe
    # bündig ist. Links und rechts bleibt der Rand der Halo-Knöpfe, so
    # steht der Rahmen genau über dem des GenerateAiButton.
    HEIGHT = 40

    # Tempo: beim Aufklappen rollt das Feld in UNFOLD_MS von der Leiste aus
    # auf, und jeder Eintrag gleitet in ITEM_MS an seinen Platz. Zugeklappt
    # wird in CLOSE_MS.
    UNFOLD_MS = 200
    ITEM_MS = 160
    CLOSE_MS = 150

    # Eckenradius in Pixeln — 0 ist eckig, wie beim GenerateAiButton.
    RADIUS = 0

    # Markierung in der Liste — dieselbe Farbe wie QPalette.Highlight.
    HIGHLIGHT = "#5a8cff"


class FolderDropdown(Dropdown):
    """Die Ordnerauswahl: sortiert, damit ein Buchstabe zum Ordner springt.

    „WÄHLE EINEN ORDNER" ist kein Eintrag mehr, sondern der Platzhalter
    (setPlaceholderText) — sonst würde er mit einsortiert.
    """

    # Deutsch sortiert: Ä bei A, ohne Groß/Klein, "Ordner 2" vor "Ordner 10".
    SORTED = True


class PromptBox(HaloPromptBox):
    """Das Prompt-Feld über den Einstellungen.

    Ein Klick auf den Doppelpfeil oben rechts fährt es über die Einstellungen
    aus, bis an den Generate-Knopf; ein zweiter Klick oder Escape fährt es
    wieder ein.
    """

    # Der Rahmen steht genau über dem des GenerateAiButton: derselbe Rand,
    # den die Halo-Knöpfe links und rechts für ihren Schein freihalten.
    ROOM = GenerateAiButton.ROOM

    # Eckenradius in Pixeln — 0 ist eckig, wie Knopf und Auswahlfelder.
    RADIUS = 0

    # So lange dauert das Aus- und Einfahren (0 = ohne Bewegung).
    GROW_MS = 300


class ParamDropdown(Dropdown):
    """Auswahlfelder im Parameter-Bereich.

    So niedrig wie die Zahlenfelder daneben und ohne den Rand der
    Halo-Knöpfe, damit sie im Formular mit den anderen Feldern fluchten.
    Ihre Reihenfolge ist gewollt (etwa bei Seitenverhältnissen) — also
    nicht sortiert.
    """

    HEIGHT = 28
    ROOM = 0
    ROOM_Y = 1
    PAD = 10
    ITEM_HEIGHT = 28
