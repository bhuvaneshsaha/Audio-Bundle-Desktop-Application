from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.core.auth.windows import default_authenticator
from audio_bundle.shared.errors import AuthenticationError
from audio_bundle.shared.messages import user_message


class WindowsSignInForm(QWidget):
    """Username and password, with an optional Windows Hello attempt."""

    def __init__(self, *, title: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(title)
        heading.setWordWrap(True)
        layout.addWidget(heading)
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setAccessibleName("Windows user name")
        self.username.setPlaceholderText(r"DOMAIN\user  or  user@domain")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName("Windows password")
        form.addRow("Windows user name", self.username)
        form.addRow("Windows password", self.password)
        layout.addLayout(form)
        self.hello = QPushButton("Use Windows Hello / PIN / fingerprint")
        self.hello.setAccessibleName("Use Windows Hello, PIN, or fingerprint")
        layout.addWidget(self.hello)

    def credentials(self) -> tuple[str, str]:
        return self.username.text().strip(), self.password.text()


class WindowsSignInDialog(QDialog):
    def __init__(self, block_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(block_name)
        self.setModal(True)
        self.setMinimumWidth(420)
        self._identity_ok = False
        layout = QVBoxLayout(self)
        self._form = WindowsSignInForm(
            title="Sign in with a Windows account to unlock this block. "
            "This is required even if you are already logged on to Windows."
        )
        layout.addWidget(self._form)
        self._form.hello.clicked.connect(self._try_hello)
        self._form.password.returnPressed.connect(self.accept)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Unlock")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setShortcut(QKeySequence.StandardKey.InsertParagraphSeparator)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def credentials(self) -> tuple[str, str]:
        return self._form.credentials()

    def _try_hello(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        try:
            default_authenticator().verify_hello()
        except AuthenticationError as exc:
            QMessageBox.information(self, "Windows Hello", user_message(exc))
