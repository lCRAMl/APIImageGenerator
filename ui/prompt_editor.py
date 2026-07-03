# prompt_editor.py

from PySide6.QtWidgets import QTextEdit
from highlight.prompt_highlighter import PromptHighlighter


class PromptEditor(QTextEdit):
    def __init__(self, config, parent=None):
        super().__init__(parent)

        self.config = config
        sections = self.config.get_prompt_sections()

        # Placeholder automatisch aus Sections
        self.setPlaceholderText(
            "\n".join(f"{s}:" for s in sections)
        )

        # Syntax Highlighting
        self.highlighter = PromptHighlighter(
            self.document(),
            sections
        )

    def reload_sections(self):
        """Falls Sections zur Laufzeit geändert werden"""
        sections = self.config.get_prompt_sections()
        self.highlighter.sections = sections
        self.highlighter._build_rules()
        self.highlighter.rehighlight()