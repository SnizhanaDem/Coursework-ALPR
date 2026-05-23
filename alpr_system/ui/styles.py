"""
QSS stylesheet for the ALPR application.

Design direction: Industrial monitoring terminal.
Palette:
  Background layers  #0d1117 → #161b22 → #1c2128 → #21262d
  Borders            #30363d
  Text primary       #e6edf3
  Text muted         #8b949e
  Accent green       #3fb950  (detections, success states)
  Accent blue        #388bfd  (interactive elements)
  Accent orange      #d29922  (warnings, paused)
  Accent red         #f85149  (stop, errors)
"""

DARK_STYLESHEET = """

/* ── Root & Global ──────────────────────────────────────── */

QMainWindow, QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: "Segoe UI", "SF Pro Display", "Ubuntu", sans-serif;
    font-size: 13px;
}

QSplitter::handle {
    background-color: #21262d;
    width: 2px;
}

/* ── Header ─────────────────────────────────────────────── */

#Header {
    background-color: #161b22;
    border-bottom: 1px solid #30363d;
}

#HeaderTitle {
    font-size: 14px;
    font-weight: 600;
    color: #e6edf3;
    letter-spacing: 0.3px;
}

#StatusLabel {
    color: #8b949e;
    font-size: 12px;
}

/* ── Panels ─────────────────────────────────────────────── */

#VideoPanel {
    background-color: #0d1117;
}

#RightPanel {
    background-color: #0d1117;
}

/* ── Video Display ──────────────────────────────────────── */

#VideoDisplay {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
}

/* ── Section Titles ─────────────────────────────────────── */

#SectionTitle {
    color: #8b949e;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding-bottom: 4px;
}

/* ── Stat Cards ─────────────────────────────────────────── */

#StatCard {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
}

#StatCard:hover {
    border-color: #388bfd;
}

#StatValue {
    font-size: 26px;
    font-weight: 700;
    color: #3fb950;
    font-family: "Courier New", "Consolas", monospace;
}

#StatDesc {
    font-size: 10px;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

/* ── Divider ─────────────────────────────────────────────── */

#Divider {
    color: #21262d;
    background-color: #21262d;
    max-height: 1px;
    margin: 4px 0;
}

/* ── Results Table ──────────────────────────────────────── */

#ResultsTable {
    background-color: #161b22;
    alternate-background-color: #1c2128;
    border: 1px solid #30363d;
    border-radius: 6px;
    gridline-color: #21262d;
    outline: none;
}

#ResultsTable QHeaderView::section {
    background-color: #21262d;
    color: #8b949e;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #30363d;
}

#ResultsTable::item {
    padding: 5px 10px;
    border: none;
    color: #c9d1d9;
}

#ResultsTable::item:selected {
    background-color: #1f3460;
    color: #e6edf3;
}

/* ── Control Bar ─────────────────────────────────────────── */

#ControlBar {
    background-color: #161b22;
    border-top: 1px solid #30363d;
}

#SourceLabel {
    color: #8b949e;
    font-size: 12px;
    padding-left: 8px;
}

/* ── Buttons ─────────────────────────────────────────────── */

QPushButton {
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    border: 1px solid transparent;
    min-width: 110px;
}

#PrimaryButton {
    background-color: #238636;
    color: #ffffff;
    border-color: #2ea043;
}

#PrimaryButton:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}

#PrimaryButton:pressed {
    background-color: #196127;
}

#PrimaryButton:disabled {
    background-color: #21262d;
    color: #484f58;
    border-color: #30363d;
}

#DangerButton {
    background-color: #21262d;
    color: #f85149;
    border-color: #f85149;
}

#DangerButton:hover {
    background-color: #3d1a19;
    border-color: #ff7b72;
    color: #ff7b72;
}

#DangerButton:pressed {
    background-color: #5c1d1a;
}

#DangerButton:disabled {
    background-color: #21262d;
    color: #484f58;
    border-color: #30363d;
}

#SecondaryButton {
    background-color: #21262d;
    color: #c9d1d9;
    border-color: #30363d;
}

#SecondaryButton:hover {
    background-color: #30363d;
    border-color: #8b949e;
    color: #e6edf3;
}

#SecondaryButton:pressed {
    background-color: #161b22;
}

/* ── Progress Bar ────────────────────────────────────────── */

#ProgressBar {
    background-color: #21262d;
    border: none;
    border-radius: 2px;
}

#ProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #388bfd, stop:1 #3fb950
    );
    border-radius: 2px;
}

/* ── Scrollbars ──────────────────────────────────────────── */

QScrollBar:vertical {
    background: #161b22;
    width: 8px;
    border: none;
}

QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #484f58;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #161b22;
    height: 8px;
    border: none;
}

QScrollBar::handle:horizontal {
    background: #30363d;
    border-radius: 4px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: #484f58;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Tooltip ─────────────────────────────────────────────── */

QToolTip {
    background-color: #1c2128;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
"""
