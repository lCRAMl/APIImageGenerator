# prompt_highlighter.py

from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression


class PromptHighlighter(QSyntaxHighlighter):
    def __init__(self, document, sections: list[str]):
        super().__init__(document)

        self.sections = sections
        self.rules = []

        self._build_rules()

    def _build_rules(self):
        self.rules.clear()

        section_format = QTextCharFormat()
        section_format.setForeground(QColor("#8fd18f"))
        section_format.setFontWeight(QFont.Weight.Bold)

        for sec in self.sections:
            pattern = QRegularExpression(
                rf"^{sec}\s*:?.*",
                QRegularExpression.MultilineOption
            )
            self.rules.append((pattern, section_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(
                    m.capturedStart(),
                    m.capturedLength(),
                    fmt
                )