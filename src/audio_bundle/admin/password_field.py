from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget


class PasswordField(QWidget):
    """Session password entry with an optional reveal toggle. Never written to disk."""

    def __init__(self, caption: str, *, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(caption))
        row = QHBoxLayout()
        self._edit = QLineEdit()
        self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit.setAccessibleName(caption)
        self._show = QCheckBox("Show password")
        self._show.setAccessibleName(f"Show {caption}")
        self._show.toggled.connect(self._toggle)
        row.addWidget(self._edit, 1)
        row.addWidget(self._show)
        layout.addLayout(row)

    def _toggle(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self._edit.setEchoMode(mode)

    def text(self) -> str:
        return self._edit.text()

    def setText(self, value: str) -> None:  # noqa: N802 - Qt-style
        self._edit.setText(value)

    def editingFinished(self):  # noqa: N802
        return self._edit.editingFinished

    def textEdited(self):  # noqa: N802
        return self._edit.textEdited
