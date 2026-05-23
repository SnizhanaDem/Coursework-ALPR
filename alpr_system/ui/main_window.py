"""
Main application window for the ALPR system.

Threading model:
  - VideoWorker runs in a QThread and emits:
      · frame_ready(QImage)   → VideoDisplay.setPixmap
      · plate_found(dict)     → ResultsTable.add_row
      · stats_updated(dict)   → StatsPanel.refresh
  - The GUI thread never blocks on CV/OCR work.
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar,
    QFrame, QSizePolicy, QTextEdit, QTabWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QPixmap, QImage, QFont, QColor, QPalette

from ui.video_worker import VideoWorker
from ui.styles import DARK_STYLESHEET
from utils.logger import get_logger

logger = get_logger(__name__)


class StatusDot(QLabel):
    """Coloured circle indicating system state (idle / running / error)."""

    COLORS = {
        "idle":    "#4a5568",
        "running": "#48bb78",
        "error":   "#fc8181",
        "paused":  "#f6ad55",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.set_state("idle")

    def set_state(self, state: str):
        color = self.COLORS.get(state, self.COLORS["idle"])
        self.setStyleSheet(
            f"background:{color}; border-radius:6px;"
            f"border: 1px solid rgba(255,255,255,0.15);"
        )


class StatCard(QFrame):
    """Single metric card: large number + small label underneath."""

    def __init__(self, label: str, initial: str = "—", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self._value_label = QLabel(initial)
        self._value_label.setObjectName("StatValue")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._desc_label = QLabel(label)
        self._desc_label.setObjectName("StatDesc")
        self._desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._value_label)
        layout.addWidget(self._desc_label)

    def update_value(self, value: str):
        self._value_label.setText(value)


class VideoDisplay(QLabel):
    """Displays live annotated video frames."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoDisplay")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(QSize(640, 400))
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._show_placeholder()

    def _show_placeholder(self):
        self.setText("Відеопотік відсутній\n\nОберіть джерело та натисніть «Запустити»")
        self.setStyleSheet(
            "color: #4a5568; font-size: 16px;"
            "border: 2px dashed #2d3748; border-radius: 8px;"
        )

    def update_frame(self, qimage: QImage):
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.setStyleSheet("")  # remove placeholder style


class ResultsTable(QTableWidget):
    """Live-updating table of detected licence plates."""

    COLUMNS = ["Час", "ID авто", "Номерний знак"]
    MAX_ROWS = 200

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setObjectName("ResultsTable")
        self.setHorizontalHeaderLabels(self.COLUMNS)

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)

        # car_id → row index, so we update instead of duplicating
        self._car_row: dict = {}

    def add_row(self, data: dict):
        """
        Insert or update one detection result.

        If a row for this car_id already exists, update it in-place
        (plate and time). This prevents one vehicle from generating
        multiple rows as the voted best-guess evolves.

        Args:
            data: Dict with keys 'time', 'car_id', 'plate'.
        """
        car_id = data.get("car_id")
        plate  = data.get("plate", "")
        time   = data.get("time", "")

        plate_item = QTableWidgetItem(plate)
        plate_item.setForeground(QColor("#68d391"))
        plate_item.setFont(QFont("Courier New", 11, QFont.Weight.Bold))

        if car_id in self._car_row:
            # Update existing row
            row = self._car_row[car_id]
            self.setItem(row, 0, QTableWidgetItem(time))
            self.setItem(row, 2, plate_item)
        else:
            # New car — insert at top, shift existing row indices down
            if self.rowCount() >= self.MAX_ROWS:
                # Remove last row and its tracking entry
                last = self.rowCount() - 1
                old_id = next(
                    (k for k, v in self._car_row.items() if v == last), None
                )
                if old_id is not None:
                    del self._car_row[old_id]
                self.removeRow(last)

            self.insertRow(0)
            # Shift all tracked row indices by +1
            self._car_row = {k: v + 1 for k, v in self._car_row.items()}
            self._car_row[car_id] = 0

            self.setItem(0, 0, QTableWidgetItem(time))
            self.setItem(0, 1, QTableWidgetItem(str(car_id)))
            self.setItem(0, 2, plate_item)

    def clear_results(self):
        self.setRowCount(0)
        self._car_row.clear()


class OCRLogViewer(QTextEdit):
    """Displays real-time OCR attempt log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("OCRLogViewer")
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(
            "background: #1a202c; color: #a0aec0; border: none;"
        )

    def add_attempt(self, attempt: dict):
        """Add an OCR attempt entry to the log."""
        car_id = attempt.get("car_id", "?")
        raw = attempt.get("raw_text", "")
        corrected = attempt.get("corrected", "")
        success = attempt.get("success", False)
        
        if success:
            status = "✅"
            line = f"[ID {car_id}] '{raw}' → {status} {corrected}"
        else:
            status = "❌"
            reason = attempt.get("reason", "невалідний формат")
            line = f"[ID {car_id}] '{raw}' → {status} '{corrected}' ({reason})"
        
        # Append to log and auto-scroll to bottom
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.insertPlainText(line + "\n")
        self.ensureCursorVisible()

    def clear_log(self):
        self.clear()


class MainWindow(QMainWindow):
    """
    Top-level application window.

    Wires together VideoDisplay, StatCards, ResultsTable,
    and the VideoWorker background thread.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALPR — Система розпізнавання номерних знаків")
        self.setMinimumSize(QSize(1100, 680))

        self._worker: VideoWorker | None = None
        self._thread: QThread | None = None
        self._source: str | None = None

        self._build_ui()
        self.setStyleSheet(DARK_STYLESHEET)
        logger.info("MainWindow initialised.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("MainSplitter")
        splitter.addWidget(self._build_video_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([700, 380])
        root_layout.addWidget(splitter, 1)

        root_layout.addWidget(self._build_control_bar())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("Header")
        header.setFixedHeight(52)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("ALPR  —  Автоматичне розпізнавання номерних знаків")
        title.setObjectName("HeaderTitle")

        self._status_dot = StatusDot()
        self._status_label = QLabel("Очікування")
        self._status_label.setObjectName("StatusLabel")

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self._status_dot)
        layout.addWidget(self._status_label)
        return header

    def _build_video_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("VideoPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 6, 6)

        self._video_display = VideoDisplay()
        layout.addWidget(self._video_display)

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("ProgressBar")
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(4)
        layout.addWidget(self._progress_bar)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("RightPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 12, 12, 6)
        layout.setSpacing(12)

        layout.addWidget(self._build_stats_section())

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("Divider")
        layout.addWidget(divider)

        # Use tabs for results and OCR log
        self._tabs = QTabWidget()
        self._tabs.setObjectName("ResultsTabs")

        # Tab 1: Results Table
        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        results_label = QLabel("Знайдені номери")
        results_label.setObjectName("SectionTitle")
        results_layout.addWidget(results_label)

        self._results_table = ResultsTable()
        results_layout.addWidget(self._results_table, 1)

        self._tabs.addTab(results_container, "Результати")

        # Tab 2: OCR Log
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)

        log_label = QLabel("Журнал спроб OCR")
        log_label.setObjectName("SectionTitle")
        log_layout.addWidget(log_label)

        self._ocr_log = OCRLogViewer()
        log_layout.addWidget(self._ocr_log, 1)

        self._tabs.addTab(log_container, "OCR Спроби")

        layout.addWidget(self._tabs, 1)

        return panel

    def _build_stats_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Статистика сесії")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        cards_row = QHBoxLayout()
        self._fps_card     = StatCard("FPS")
        self._vehicles_card = StatCard("Авто")
        self._plates_card  = StatCard("Номери")

        for card in (self._fps_card, self._vehicles_card, self._plates_card):
            cards_row.addWidget(card)

        layout.addLayout(cards_row)
        return section

    def _build_control_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ControlBar")
        bar.setFixedHeight(60)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        self._source_btn = QPushButton("📂  Вибрати відео")
        self._source_btn.setObjectName("SecondaryButton")
        self._source_btn.clicked.connect(self._on_choose_source)

        self._source_label = QLabel("Джерело не обрано")
        self._source_label.setObjectName("SourceLabel")

        self._start_btn = QPushButton("▶  Запустити")
        self._start_btn.setObjectName("PrimaryButton")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)

        self._stop_btn = QPushButton("■  Зупинити")
        self._stop_btn.setObjectName("DangerButton")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)

        self._clear_btn = QPushButton("🗑  Очистити")
        self._clear_btn.setObjectName("SecondaryButton")
        self._clear_btn.clicked.connect(self._on_clear)

        layout.addWidget(self._source_btn)
        layout.addWidget(self._source_label, 1)
        layout.addWidget(self._start_btn)
        layout.addWidget(self._stop_btn)
        layout.addWidget(self._clear_btn)
        return bar

    # ------------------------------------------------------------------
    # Slots — control bar
    # ------------------------------------------------------------------

    def _on_choose_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Оберіть відеофайл",
            "",
            "Відеофайли (*.mp4 *.avi *.mkv *.mov);;Всі файли (*)",
        )
        if path:
            self._source = path
            short = path.split("/")[-1]
            self._source_label.setText(f"📹  {short}")
            self._start_btn.setEnabled(True)
            logger.info("Source selected: %s", path)

    def _on_start(self):
        if self._source is None:
            return
        self._launch_worker(self._source)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_dot.set_state("running")
        self._status_label.setText("Обробка…")
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # indeterminate

    def _on_stop(self):
        self._stop_worker()
        self._start_btn.setEnabled(self._source is not None)
        self._stop_btn.setEnabled(False)
        self._status_dot.set_state("idle")
        self._status_label.setText("Зупинено")
        self._progress_bar.setVisible(False)
        self._video_display._show_placeholder()

    def _on_clear(self):
        self._results_table.clear_results()
        self._ocr_log.clear_log()
        for card in (self._fps_card, self._vehicles_card, self._plates_card):
            card.update_value("—")

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def _launch_worker(self, source: str):
        # Always cleanly stop any previous worker before creating a new one.
        # This prevents "QThread destroyed while still running" when the user
        # presses Start again after a video finishes naturally.
        self._stop_worker()

        self._thread = QThread()
        self._worker = VideoWorker(source)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.frame_ready.connect(self._video_display.update_frame)
        self._worker.plate_found.connect(self._results_table.add_row)
        self._worker.ocr_attempt.connect(self._ocr_log.add_attempt)
        self._worker.stats_updated.connect(self._on_stats_updated)
        self._worker.finished.connect(self._on_worker_finished)

        # When the worker emits finished, tell the thread to exit its event loop.
        # deleteLater lets Qt clean up both objects safely on the GUI thread,
        # avoiding the "destroyed while still running" warning.
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()
        logger.info("Worker thread started for source: %s", source)

    def _stop_worker(self):
        if self._worker:
            self._worker.stop()
        if self._thread:
            try:
                if self._thread.isRunning():
                    self._thread.quit()
                    if not self._thread.wait(4000):
                        logger.warning("Thread did not stop in time — forcing termination.")
                        self._thread.terminate()
                        self._thread.wait()
            except RuntimeError:
                # Thread object has been deleted by Qt's event loop
                logger.debug("QThread was already deleted.")
        self._worker = None
        self._thread = None
        logger.info("Worker thread stopped.")

    # ------------------------------------------------------------------
    # Slots — worker signals
    # ------------------------------------------------------------------

    def _on_stats_updated(self, stats: dict):
        self._fps_card.update_value(f"{stats.get('fps', 0):.1f}")
        self._vehicles_card.update_value(str(stats.get("vehicles", 0)))
        self._plates_card.update_value(str(stats.get("plates", 0)))

    def _on_worker_finished(self):
        self._start_btn.setEnabled(self._source is not None)
        self._stop_btn.setEnabled(False)
        self._status_dot.set_state("idle")
        self._status_label.setText("Завершено")
        self._progress_bar.setVisible(False)
        logger.info("Worker finished.")

    # ------------------------------------------------------------------
    # Cleanup on close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        self._stop_worker()
        event.accept()