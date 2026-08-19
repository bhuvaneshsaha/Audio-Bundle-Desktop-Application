from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

from audio_bundle.core.models.manifest import BundleFileEntry

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
except ImportError:  # pragma: no cover - optional QtPdf
    QPdfDocument = None  # type: ignore[misc, assignment]
    QPdfView = None  # type: ignore[misc, assignment]


class PdfViewer(QWidget):
    """Embedded PDF page view. Zoom/search extras are Milestone 7."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._title = QLabel("No PDF selected")
        self._title.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)
        self._document = None
        self._view = None
        self._page = None
        if QPdfDocument is not None and QPdfView is not None:
            self._document = QPdfDocument(self)
            self._view = QPdfView(self)
            self._view.setDocument(self._document)
            self._view.setPageMode(QPdfView.PageMode.SinglePage)
            layout.addWidget(self._view, 1)
            nav = QHBoxLayout()
            prev_btn = QPushButton("Previous page")
            next_btn = QPushButton("Next page")
            self._page = QSpinBox()
            self._page.setMinimum(1)
            prev_btn.clicked.connect(lambda: self._page.setValue(self._page.value() - 1))
            next_btn.clicked.connect(lambda: self._page.setValue(self._page.value() + 1))
            self._page.valueChanged.connect(self._go_page)
            nav.addWidget(prev_btn)
            nav.addWidget(self._page)
            nav.addWidget(next_btn)
            nav.addStretch(1)
            layout.addLayout(nav)
        else:
            missing = QLabel("PDF viewing is not available in this Qt build.")
            missing.setWordWrap(True)
            layout.addWidget(missing)

    def load(self, entry: BundleFileEntry, path: Path) -> None:
        self._title.setText(entry.display_name)
        if self._document is None:
            return
        self._document.load(str(path))
        pages = max(self._document.pageCount(), 1)
        if self._page is not None:
            self._page.setMaximum(pages)
            self._page.setValue(1)
        self._go_page(1)

    def _go_page(self, page: int) -> None:
        if self._view is None or self._document is None:
            return
        index = max(0, min(page - 1, self._document.pageCount() - 1))
        self._view.pageNavigator().jump(index, self._view.pageNavigator().currentLocation())

    def clear(self) -> None:
        if self._document is not None:
            self._document.close()
        self._title.setText("No PDF selected")
