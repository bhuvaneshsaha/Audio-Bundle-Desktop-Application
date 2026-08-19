from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.core.models.manifest import BundleFileEntry

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
except ImportError:  # pragma: no cover
    QPdfDocument = None  # type: ignore[misc, assignment]
    QPdfView = None  # type: ignore[misc, assignment]

try:
    from PySide6.QtPdf import QPdfSearchModel
except ImportError:  # pragma: no cover
    QPdfSearchModel = None  # type: ignore[misc, assignment]


class PdfViewer(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._title = QLabel("No PDF selected")
        self._title.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)
        self._document = None
        self._view = None
        self._search_model = None
        self._page = QSpinBox()
        self._page.setMinimum(1)
        self._page.setAccessibleName("Page number")
        if QPdfDocument is not None and QPdfView is not None:
            self._document = QPdfDocument(self)
            self._view = QPdfView(self)
            self._view.setDocument(self._document)
            try:
                self._view.setPageMode(QPdfView.PageMode.MultiPage)
            except Exception:
                self._view.setPageMode(QPdfView.PageMode.SinglePage)
            layout.addWidget(self._view, 1)
            if QPdfSearchModel is not None:
                self._search_model = QPdfSearchModel(self)
                self._search_model.setDocument(self._document)
                setter = getattr(self._view, "setSearchModel", None)
                if callable(setter):
                    setter(self._search_model)
        else:
            missing = QLabel("PDF viewing is not available in this Qt build.")
            missing.setWordWrap(True)
            layout.addWidget(missing)

        nav = QHBoxLayout()
        prev_btn = QPushButton("Previous")
        next_btn = QPushButton("Next")
        prev_btn.clicked.connect(lambda: self._page.setValue(self._page.value() - 1))
        next_btn.clicked.connect(lambda: self._page.setValue(self._page.value() + 1))
        self._page.valueChanged.connect(self._go_page)
        nav.addWidget(prev_btn)
        nav.addWidget(QLabel("Page"))
        nav.addWidget(self._page)
        nav.addWidget(next_btn)
        nav.addWidget(QLabel("View"))
        self._zoom = QComboBox()
        self._zoom.setAccessibleName("PDF zoom")
        self._zoom.addItem("Fit page", "fit-page")
        self._zoom.addItem("Fit width", "fit-width")
        self._zoom.addItem("75%", 0.75)
        self._zoom.addItem("100%", 1.0)
        self._zoom.addItem("125%", 1.25)
        self._zoom.addItem("150%", 1.5)
        self._zoom.addItem("200%", 2.0)
        self._zoom.currentIndexChanged.connect(self._apply_zoom)
        nav.addWidget(self._zoom)
        zoom_out = QPushButton("−")
        zoom_in = QPushButton("+")
        zoom_out.clicked.connect(self._zoom_out)
        zoom_in.clicked.connect(self._zoom_in)
        nav.addWidget(zoom_out)
        nav.addWidget(zoom_in)
        nav.addStretch(1)
        layout.addLayout(nav)

        search_row = QHBoxLayout()
        self._query = QLineEdit()
        self._query.setPlaceholderText("Search text")
        self._query.setAccessibleName("PDF search")
        find = QPushButton("Find")
        find.clicked.connect(self._search)
        self._query.returnPressed.connect(self._search)
        search_row.addWidget(self._query, 1)
        search_row.addWidget(find)
        layout.addLayout(search_row)
        self._status = QLabel("")
        layout.addWidget(self._status)

    def load(self, entry: BundleFileEntry, path: Path) -> None:
        self._title.setText(entry.display_name)
        self._status.setText("")
        if self._document is None:
            return
        self._document.load(str(path))
        pages = max(self._document.pageCount(), 1)
        self._page.setMaximum(pages)
        self._page.setValue(1)
        self._apply_zoom()
        self._go_page(1)

    def _go_page(self, page: int) -> None:
        if self._view is None or self._document is None:
            return
        count = max(self._document.pageCount(), 1)
        index = max(0, min(page - 1, count - 1))
        navigator = self._view.pageNavigator()
        navigator.jump(index, navigator.currentLocation())

    def _apply_zoom(self) -> None:
        if self._view is None:
            return
        mode = self._zoom.currentData()
        if mode == "fit-page":
            self._view.setZoomMode(QPdfView.ZoomMode.FitInView)
        elif mode == "fit-width":
            self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        else:
            self._view.setZoomMode(QPdfView.ZoomMode.Custom)
            self._view.setZoomFactor(float(mode))

    def _zoom_in(self) -> None:
        index = min(self._zoom.count() - 1, self._zoom.currentIndex() + 1)
        self._zoom.setCurrentIndex(index)

    def _zoom_out(self) -> None:
        index = max(0, self._zoom.currentIndex() - 1)
        self._zoom.setCurrentIndex(index)

    def _search(self) -> None:
        query = self._query.text().strip()
        if self._search_model is None or not query:
            self._status.setText("Search is not available." if self._search_model is None else "")
            return
        self._search_model.setSearchString(query)
        count = int(self._search_model.rowCount())
        if count <= 0:
            self._status.setText("No matches.")
            return
        self._status.setText(f"{count} match{'es' if count != 1 else ''}.")
        result = self._search_model.resultAtIndex(0)
        page = getattr(result, "pageNumber", None)
        if page is not None:
            self._page.setValue(int(page) + 1)

    def clear(self) -> None:
        if self._document is not None:
            self._document.close()
        self._title.setText("No PDF selected")
        self._status.setText("")
