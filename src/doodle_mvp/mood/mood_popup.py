"""Compact mood popup: four choices, clear feedback, easy dismissal."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..desktop import positioning
from .mood import MOOD_EMOJI, MOOD_LABELS, VALID_MOODS


class MoodPopup(QWidget):
    mood_chosen = Signal(str)

    FEEDBACK_MS = 1200

    def __init__(self, parent=None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(220, 190)
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(self.close)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.setStyleSheet(
            "MoodPopup { background: rgba(40, 36, 40, 235); border-radius: 14px; }"
            "QLabel { color: white; }"
            "QPushButton { background: rgba(255,255,255,28); color: white;"
            " border: none; border-radius: 10px; padding: 10px 4px; font-size: 14px; }"
            "QPushButton:hover { background: rgba(255,255,255,60); }"
        )

        title = QLabel("How are you feeling?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(6)
        for i, mood in enumerate(VALID_MOODS):
            btn = QPushButton(f"{MOOD_EMOJI[mood]}\n{MOOD_LABELS[mood]}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, m=mood: self._choose(m))
            grid.addWidget(btn, i // 2, i % 2)
        root.addLayout(grid)

        self._feedback = QLabel("")
        self._feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._feedback)

    def show_near(self, anchor: QWidget) -> None:
        """Show the popup just above the panda window."""
        top_left = anchor.mapToGlobal(QPoint(0, 0))
        x = top_left.x() + (anchor.width() - self.width()) // 2
        y = top_left.y() - self.height() - 12
        self.move(positioning.clamp_to_screen(self, QPoint(x, y)))
        self._feedback.setText("")
        for child in self.findChildren(QPushButton):
            child.setVisible(True)
        self.show()
        self.raise_()
        self.activateWindow()

    def _choose(self, mood: str) -> None:
        for child in self.findChildren(QPushButton):
            child.setVisible(False)
        self._feedback.setText(f"Saved: {MOOD_LABELS[mood]} ✓")
        self.mood_chosen.emit(mood)
        self._feedback_timer.start(self.FEEDBACK_MS)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)
