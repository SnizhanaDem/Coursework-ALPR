import argparse
import sys

from utils.logger import get_logger, add_file_handler

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ALPR — Automatic License Plate Recognition System"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without GUI (terminal output only).",
    )
    parser.add_argument(
        "--source",
        default="video0.mp4",
        help="Video file path, webcam index (e.g. 0), or RTSP URL.",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional path to a log file.",
    )
    return parser.parse_args()


def run_gui():
    """Launch the PyQt6 graphical interface."""
    from PyQt6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("ALPR System")
    app.setOrganizationName("CourseWork")

    window = MainWindow()
    window.show()

    logger.info("GUI launched.")
    sys.exit(app.exec())


def run_headless(source: str):
    """Run the pipeline without a GUI and print a final report."""
    import cv2
    from config.settings import DEFAULT_CONFIG
    from pipeline.processor import ALPRPipeline

    source_arg = source
    try:
        source_arg = int(source)
    except ValueError:
        pass

    cap = cv2.VideoCapture(source_arg)
    if not cap.isOpened():
        logger.error("Cannot open source: %s", source)
        sys.exit(1)

    pipeline = ALPRPipeline(DEFAULT_CONFIG)
    frame_count = 0

    logger.info("Headless mode started. Press Ctrl+C to stop.")
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            detections = pipeline.process_frame(frame)
            for det in detections:
                logger.info(
                    "Frame %d | Car %d | %s",
                    frame_count, det.car_id, det.validated_plate,
                )

            annotated = pipeline.get_annotated_frame(frame)
            cv2.imshow("ALPR — Headless", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    report = pipeline.final_report
    print("\n" + "=" * 50)
    print("  ФІНАЛЬНИЙ ЗВІТ")
    print("=" * 50)
    for cid, plate in sorted(report.items()):
        print(f"  Авто #{cid:>3d}  →  {plate}")
    print("=" * 50)


if __name__ == "__main__":
    args = parse_args()

    if args.log_file:
        add_file_handler(logger, args.log_file)

    if args.headless:
        run_headless(args.source)
    else:
        run_gui()
