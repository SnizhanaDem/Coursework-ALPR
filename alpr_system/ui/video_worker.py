"""
VideoWorker — background QThread worker for the ALPR pipeline.

Runs the full detection/OCR loop in a separate thread so the GUI
never freezes. Communicates with the main window exclusively via
Qt signals (frame_ready, plate_found, stats_updated, finished).

Signal contracts
----------------
frame_ready(QImage)
    Emitted every processed frame. The QImage is already annotated
    with bounding boxes and plate labels by the Renderer.

plate_found(dict)
    Emitted each time a new validated plate is elected as best_guess.
    Keys: 'time' (str HH:MM:SS), 'car_id' (int), 'plate' (str).

stats_updated(dict)
    Emitted every second with aggregate metrics.
    Keys: 'fps' (float), 'vehicles' (int), 'plates' (int).

finished()
    Emitted when the video stream ends or stop() is called.
"""

import time
from datetime import datetime
from collections import Counter

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker
from PyQt6.QtGui import QImage

from config.settings import DEFAULT_CONFIG
from pipeline.processor import ALPRPipeline
from utils.logger import get_logger

logger = get_logger(__name__)


def ndarray_to_qimage(frame: np.ndarray) -> QImage:
    """
    Convert an OpenCV BGR frame to a QImage for display in QLabel.

    Args:
        frame: BGR uint8 array of shape (H, W, 3).

    Returns:
        QImage in RGB888 format.
    """
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()


class VideoWorker(QObject):
    """
    Executes the ALPR pipeline on a video source inside a QThread.

    Args:
        source: File path, device index (int), or RTSP URL.
        config: System configuration (defaults to DEFAULT_CONFIG).
    """

    frame_ready   = pyqtSignal(QImage)
    plate_found   = pyqtSignal(dict)
    ocr_attempt   = pyqtSignal(dict)  # Emits OCR attempt details
    stats_updated = pyqtSignal(dict)
    finished      = pyqtSignal()

    def __init__(self, source, config=DEFAULT_CONFIG):
        super().__init__()
        self._source = source
        self._config = config
        self._running = False
        self._mutex = QMutex()

        # Runtime counters
        self._total_plates: int = 0
        self._frame_times: list = []     # timestamps for FPS calculation
        self._last_stats_emit: float = 0.0
        self._car_plate_history: dict = {}  # car_id -> list of validated plates
        self._last_car_plate: dict = {}  # car_id -> last recognized plate (for display)

    def stop(self):
        """Thread-safe stop request."""
        with QMutexLocker(self._mutex):
            self._running = False

    def _print_final_report(self):
        """Print a summary of all detected vehicles and their plates."""
        print("\n" + "="*60)
        print("📊 --- ФІНАЛЬНИЙ ЗВІТ ОБ'ЄКТІВ ---")
        print("="*60)
        
        if not self._car_plate_history:
            print("❌ Жодних автомобілів не виявлено.")
        else:
            for car_id in sorted(self._car_plate_history.keys()):
                plates = self._car_plate_history[car_id]
                if plates:
                    # Get the most common (best guess) plate
                    best_plate = Counter(plates).most_common(1)[0][0]
                    count = len(plates)
                    print(f"🚗 Машина №{car_id} | Номер: {best_plate} | Спостережень: {count}")
        
        print("="*60 + "\n")

    # ------------------------------------------------------------------
    # Public API (called from GUI thread)
    # ------------------------------------------------------------------

    def stop(self):
        """Thread-safe stop request."""
        with QMutexLocker(self._mutex):
            self._running = False

    # ------------------------------------------------------------------
    # Main loop (runs in the worker QThread)
    # ------------------------------------------------------------------

    def run(self):
        """Entry point — called by QThread.started signal."""
        logger.info("VideoWorker.run() started for source: %s", self._source)
        self._running = True

        # Try integer device index
        source = self._source
        try:
            source = int(source)
        except (ValueError, TypeError):
            pass

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logger.error("Cannot open source: %s", self._source)
            self.finished.emit()
            return

        pipeline = ALPRPipeline(self._config)

        try:
            while True:
                with QMutexLocker(self._mutex):
                    if not self._running:
                        break

                ret, frame = cap.read()
                if not ret:
                    logger.info("End of stream.")
                    break

                # Run pipeline
                detections = pipeline.process_frame(frame)
                annotated  = pipeline.get_annotated_frame(frame)

                # Emit annotated frame
                self.frame_ready.emit(ndarray_to_qimage(annotated))

                # Emit all OCR attempts (successful or failed)
                for det in detections:
                    for attempt in det.attempts:
                        self.ocr_attempt.emit(attempt)

                # Emit new plates
                for det in detections:
                    if det.validated_plate:  # Only if validation was successful
                        # Track plate history for each car
                        if det.car_id not in self._car_plate_history:
                            self._car_plate_history[det.car_id] = []
                        self._car_plate_history[det.car_id].append(det.validated_plate)
                        
                        # Get the most common (voted) plate from history
                        best_plate = Counter(self._car_plate_history[det.car_id]).most_common(1)[0][0]
                        
                        # Update last recognized plate for this car
                        old_plate = self._last_car_plate.get(det.car_id)
                        self._last_car_plate[det.car_id] = best_plate  # Store the voted best plate
                        
                        # Only emit if this is a NEW car or the best plate actually changed
                        if old_plate != best_plate:
                            self._total_plates += 1
                            self.plate_found.emit({
                                "time":   datetime.now().strftime("%H:%M:%S"),
                                "car_id": det.car_id,
                                "plate":  best_plate,
                            })

                # FPS tracking
                now = time.monotonic()
                self._frame_times.append(now)
                self._frame_times = [t for t in self._frame_times if now - t < 1.0]

                # Emit stats once per second
                if now - self._last_stats_emit >= 1.0:
                    self.stats_updated.emit({
                        "fps":      float(len(self._frame_times)),
                        "vehicles": len(pipeline.final_report),
                        "plates":   self._total_plates,
                    })
                    self._last_stats_emit = now

        finally:
            cap.release()
            self._print_final_report()
            self.finished.emit()
            logger.info("VideoWorker finished.")
