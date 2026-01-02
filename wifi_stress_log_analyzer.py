#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

APP_VERSION = "2026.01.02"
APP_WINDOW_TITLE = "WiFi Stress Log Analyzer - Designed by TechNexion"
APP_HEADER_TITLE = "WiFi Stress Log Analyzer"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
HOME_DIR = os.path.expanduser("~")
_documents_dir = os.path.join(HOME_DIR, "Documents")
DEFAULT_DIR = _documents_dir if os.path.isdir(_documents_dir) else HOME_DIR


_FILENAME_V1_RE = re.compile(
    # Legacy format:
    #   YYYYMMDD_HHMMSS_SN_MAC_RESULT.txt
    # Note: historically this project stored SN in the LogRecord.mac field,
    # and MAC in the LogRecord.serial field (to match the requested CSV columns).
    r"^(?P<date>\d{8})_(?P<time>\d{6})_(?P<sn>[^_]+)_(?P<mac>[^_]+)_(?P<result>[A-Za-z]+)\.txt$"
)

_FILENAME_V2_RE = re.compile(
    # New format:
    #   YYYYMMDD_HHMMSS_SN_MAC1_MAC2_RESULT.txt
    r"^(?P<date>\d{8})_(?P<time>\d{6})_(?P<sn>[^_]+)_(?P<mac1>[^_]+)_(?P<mac2>[^_]+)_(?P<result>[A-Za-z]+)\.txt$"
)


@dataclass(frozen=True)
class LogRecord:
    dt: datetime
    test_date: str
    test_time: str
    mac: str
    serial: str
    result: str  # PASS/FAIL
    filename: str


def parse_log_directory_raw(log_dir: str) -> List[LogRecord]:
    records: List[LogRecord] = []

    if not log_dir or not os.path.isdir(log_dir):
        return records

    for name in os.listdir(log_dir):
        if not name.lower().endswith(".txt"):
            continue

        if _is_excluded_by_name(name):
            continue

        rec = _try_parse_record_from_filename(name)
        if rec is None:
            continue

        records.append(rec)

    records.sort(key=lambda r: r.dt)
    return records


def _dedupe_keep_latest_by_sn(records: List[LogRecord]) -> List[LogRecord]:
    # Counting rule: duplicates by SN keep only the latest time.
    latest_by_sn: dict[str, LogRecord] = {}
    for r in records:
        sn_key = r.mac
        prev = latest_by_sn.get(sn_key)
        if prev is None or r.dt > prev.dt:
            latest_by_sn[sn_key] = r

    deduped = list(latest_by_sn.values())
    deduped.sort(key=lambda r: r.dt)
    return deduped


def _is_excluded_by_name(filename: str) -> bool:
    name_upper = filename.upper()

    # Requirement:
    # - Exclude dummy_dummy or any filename containing dummy
    # - Exclude TERMINATED (and tolerate the common misspelling TERNINATED)
    if "DUMMY" in name_upper:
        return True

    if "TERMINATED" in name_upper or "TERNINATED" in name_upper:
        return True

    return False


def _try_parse_record_from_filename(filename: str) -> Optional[LogRecord]:
    m2 = _FILENAME_V2_RE.match(filename)
    m1 = _FILENAME_V1_RE.match(filename) if m2 is None else None
    m = m2 or m1
    if not m:
        return None

    date_raw = m.group("date")
    time_raw = m.group("time")
    sn = m.group("sn")
    result = m.group("result").upper()

    # Keep existing CSV behavior:
    # - LogRecord.mac maps to the CSV "SN" column
    # - LogRecord.serial maps to the CSV "MAC" column
    if m2 is not None:
        mac1 = m.group("mac1")
        mac2 = m.group("mac2")
        mac_field = f"{mac1}_{mac2}"
    else:
        mac_field = m.group("mac")

    if result not in {"PASS", "FAIL", "TERMINATED", "TERNINATED"}:
        return None

    if result in {"TERMINATED", "TERNINATED"}:
        return None

    try:
        dt = datetime.strptime(f"{date_raw}{time_raw}", "%Y%m%d%H%M%S")
    except ValueError:
        return None

    test_date = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
    test_time = f"{time_raw[0:2]}:{time_raw[2:4]}:{time_raw[4:6]}"

    return LogRecord(
        dt=dt,
        test_date=test_date,
        test_time=test_time,
        mac=sn,
        serial=mac_field,
        result=result,
        filename=filename,
    )


def parse_log_directory(log_dir: str) -> Tuple[List[LogRecord], int, int, int]:
    raw = parse_log_directory_raw(log_dir)
    deduped = _dedupe_keep_latest_by_sn(raw)

    pass_count = sum(1 for r in deduped if r.result == "PASS")
    fail_count = sum(1 for r in deduped if r.result == "FAIL")
    total = pass_count + fail_count

    return deduped, total, pass_count, fail_count


def _ratio_text(count: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{(count / total) * 100.0:.1f}%"


def _default_browse_dir() -> str:
    return DEFAULT_DIR

def run_gui() -> int:
    try:
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont
        from PyQt5.QtWidgets import (
            QApplication,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QFileDialog,
            QVBoxLayout,
            QWidget,
        )
    except ModuleNotFoundError as e:
        print("PyQt5 is not installed in this Python environment.")
        print("Install it first. On Ubuntu 22.04 you can use either:")
        print("  sudo apt update")
        print("  sudo apt install -y python3-pyqt5 python3-pyqt5.qtsvg")
        print("Or via pip:")
        print("  python3 -m pip install PyQt5")
        print(f"Details: {e}")
        return 2

    # QtSvg is optional (logo only). Keep the app running even if it's missing.
    try:
        from PyQt5.QtSvg import QSvgWidget  # type: ignore
    except ModuleNotFoundError:
        QSvgWidget = None  # type: ignore

    class WiFiStressLogAnalyzer(QMainWindow):
        def __init__(self):
            super().__init__()
            self.records: List[LogRecord] = []
            self.raw_records: List[LogRecord] = []
            self.init_ui()

        def _apply_result_styles(self):
            # Larger typography + result highlighting.
            self.total_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #2c3e50;")
            self.pass_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #27ae60;")
            self.fail_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #e74c3c;")

        def init_ui(self):
            self.setWindowTitle(f"{APP_WINDOW_TITLE} - (v{APP_VERSION})")
            self.setGeometry(120, 120, 1000, 560)
            self.setStyleSheet("QMainWindow { background-color: #f0f0f0; }")

            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            main_layout = QVBoxLayout()
            main_widget.setLayout(main_layout)

            title_layout = QHBoxLayout()

            logo_path = os.path.join(APP_DIR, "technexion_logo.svg")
            if QSvgWidget is not None and os.path.exists(logo_path):
                logo_widget = QSvgWidget(logo_path)
                logo_widget.setFixedSize(200, 30)
                title_layout.addWidget(logo_widget)
            else:
                logo_placeholder = QLabel("")
                logo_placeholder.setFixedWidth(200)
                title_layout.addWidget(logo_placeholder)

            title_label = QLabel(APP_HEADER_TITLE)
            title_font = QFont("Arial", 18, QFont.Bold)
            title_label.setFont(title_font)
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("color: #2c3e50; padding: 10px;")
            title_layout.addWidget(title_label, 1)

            right_spacer = QLabel("")
            right_spacer.setFixedWidth(200)
            title_layout.addWidget(right_spacer)

            main_layout.addLayout(title_layout)

            input_group = QGroupBox("Log Analysis")
            input_group.setStyleSheet(
                """
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #3498db;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                """
            )
            grid = QGridLayout()
            input_group.setLayout(grid)

            grid.addWidget(QLabel("Product Name:"), 0, 0)
            self.production_name_input = QLineEdit()
            self.production_name_input.setPlaceholderText("TNXXX-XXXX-XXXXXX")
            self.production_name_input.setMinimumHeight(34)
            self.production_name_input.setStyleSheet(
                """
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    font-size: 12pt;
                }
                QLineEdit::placeholder {
                    color: #999999;
                }
                """
            )
            grid.addWidget(self.production_name_input, 0, 1, 1, 2)

            grid.addWidget(QLabel("Log Folder:"), 1, 0)
            self.log_dir_display = QLineEdit()
            self.log_dir_display.setReadOnly(True)
            self.log_dir_display.setPlaceholderText("Select folder that contains log .txt files")
            self.log_dir_display.setText(DEFAULT_DIR)
            self.log_dir_display.setMinimumHeight(32)
            grid.addWidget(self.log_dir_display, 1, 1)

            browse_log_btn = QPushButton("Browse")
            browse_log_btn.clicked.connect(self.on_browse_log_dir)
            browse_log_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #95a5a6;
                    color: white;
                    border: none;
                    padding: 6px 16px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #7f8c8d;
                }
                """
            )
            grid.addWidget(browse_log_btn, 1, 2)

            self.parse_btn = QPushButton("Parse")
            self.parse_btn.clicked.connect(self.on_parse)
            self.parse_btn.setMinimumHeight(38)
            self.parse_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    font-size: 12px;
                    font-weight: bold;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1f5f8b;
                }
                """
            )
            grid.addWidget(self.parse_btn, 2, 2)

            self.total_label = QLabel("Total: 0")
            self.pass_label = QLabel("PASS: 0 (0.0%)")
            self.fail_label = QLabel("FAIL: 0 (0.0%)")

            self._apply_result_styles()

            grid.addWidget(self.total_label, 2, 0)
            grid.addWidget(self.pass_label, 2, 1)
            grid.addWidget(self.fail_label, 3, 1)

            main_layout.addWidget(input_group)

            report_group = QGroupBox("Report")
            report_group.setStyleSheet(
                """
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #3498db;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                """
            )
            report_layout = QGridLayout()
            report_group.setLayout(report_layout)

            report_layout.addWidget(QLabel("Report Output Folder:"), 0, 0)
            self.report_dir_display = QLineEdit()
            self.report_dir_display.setReadOnly(True)
            self.report_dir_display.setPlaceholderText("Select report output directory")
            self.report_dir_display.setText(DEFAULT_DIR)
            self.report_dir_display.setMinimumHeight(32)
            report_layout.addWidget(self.report_dir_display, 0, 1)

            browse_report_btn = QPushButton("Browse")
            browse_report_btn.clicked.connect(self.on_browse_report_dir)
            browse_report_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #95a5a6;
                    color: white;
                    border: none;
                    padding: 6px 16px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #7f8c8d;
                }
                """
            )
            report_layout.addWidget(browse_report_btn, 0, 2)

            self.report_btn = QPushButton("Report")
            self.report_btn.clicked.connect(self.on_report)
            self.report_btn.setMinimumHeight(38)
            self.report_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    font-size: 12px;
                    font-weight: bold;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #1f8f4f;
                }
                QPushButton:pressed {
                    background-color: #18703d;
                }
                """
            )
            report_layout.addWidget(self.report_btn, 1, 2)

            main_layout.addWidget(report_group)
            main_layout.addStretch(1)

        def on_browse_log_dir(self):
            initial_dir = self.log_dir_display.text().strip() or _default_browse_dir()
            folder = QFileDialog.getExistingDirectory(self, "Select Log Folder", initial_dir)
            if folder:
                self.log_dir_display.setText(folder)

        def on_browse_report_dir(self):
            initial_dir = self.report_dir_display.text().strip() or _default_browse_dir()
            folder = QFileDialog.getExistingDirectory(self, "Select Report Output Folder", initial_dir)
            if folder:
                self.report_dir_display.setText(folder)

        def on_parse(self):
            log_dir = self.log_dir_display.text().strip()
            raw = parse_log_directory_raw(log_dir)
            deduped = _dedupe_keep_latest_by_sn(raw)
            self.raw_records = raw
            self.records = deduped

            pass_count = sum(1 for r in deduped if r.result == "PASS")
            fail_count = sum(1 for r in deduped if r.result == "FAIL")
            total = pass_count + fail_count

            self.total_label.setText(f"Total: {total}")
            self.pass_label.setText(f"PASS: {pass_count} ({_ratio_text(pass_count, total)})")
            self.fail_label.setText(f"FAIL: {fail_count} ({_ratio_text(fail_count, total)})")

            if not log_dir:
                QMessageBox.warning(self, "Parse", "Please select Log Folder first.")
                return

            QMessageBox.information(
                self,
                "Parse",
                f"Parse completed.\nTotal: {total}\nPASS: {pass_count}\nFAIL: {fail_count}",
            )

        def on_report(self):
            if not self.records:
                QMessageBox.warning(self, "Report", "No parsed records. Please click Parse first.")
                return

            out_dir = self.report_dir_display.text().strip()
            if not out_dir or not os.path.isdir(out_dir):
                QMessageBox.warning(self, "Report", "Please select Report Output Folder first.")
                return

            production_name = (
                self.production_name_input.text().strip()
                or self.production_name_input.placeholderText().strip()
                or "UNKNOWN"
            )
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", production_name)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = os.path.join(out_dir, f"wifi_stress_report_{safe_name}_{ts}.csv")
            txt_path = os.path.join(out_dir, f"wifi_stress_yield_{safe_name}_{ts}.txt")

            try:
                with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["Product", "Date", "Time", "SN", "MAC", "Result"])
                    for r in sorted(self.records, key=lambda x: x.dt):
                        # Per request: SN column shows the (long) MAC; MAC column shows the sequence/short code.
                        w.writerow([production_name, r.test_date, r.test_time, r.mac, r.serial, r.result])
            except OSError as e:
                QMessageBox.critical(self, "Report", f"Failed to create report.\n{e}")
                return

            # Generate a simple TXT yield report after CSV.
            total = len(self.records)
            pass_count = sum(1 for r in self.records if r.result == "PASS")
            fail_count = sum(1 for r in self.records if r.result == "FAIL")

            # Test date: if logs are from a single day, show that day; otherwise show a range.
            dates = sorted({r.test_date for r in self.records})
            if not dates:
                test_date_text = datetime.now().strftime("%Y-%m-%d")
            elif len(dates) == 1:
                test_date_text = dates[0]
            else:
                test_date_text = f"{dates[0]} ~ {dates[-1]}"

            report_time_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            def _ratio_text_2(count: int, total_count: int) -> str:
                if total_count <= 0:
                    return "0.00%"
                return f"{(count / total_count) * 100.0:.2f}%"

            try:
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write("WiFi Yield Report\n")
                    f.write(f"Product: {production_name}\n")
                    f.write(f"Test Date: {test_date_text}\n")
                    f.write(f"Report Time: {report_time_text}\n")
                    f.write(f"Total Tests: {total}\n")
                    f.write(f"PASS Count: {pass_count}, PASS Rate: {_ratio_text_2(pass_count, total)}\n")
                    f.write(f"FAIL Count: {fail_count}, FAIL Rate: {_ratio_text_2(fail_count, total)}\n")

                    # Retest details: if a SN appears multiple times in raw logs, it indicates retest.
                    # "Retest count" excludes the last (final) test: retests = attempts - 1.
                    raw_source = self.raw_records if self.raw_records else self.records
                    by_sn: dict[str, List[LogRecord]] = {}
                    for r in raw_source:
                        by_sn.setdefault(r.mac, []).append(r)

                    retest_items = [(sn, sorted(items, key=lambda x: x.dt)) for sn, items in by_sn.items() if len(items) > 1]
                    retest_items.sort(key=lambda x: x[0])

                    total_retests = sum(len(items) - 1 for _, items in retest_items)

                    f.write("\n")
                    f.write("Retest Details (grouped by SN)\n")
                    f.write(f"Total Retests (exclude final): {total_retests}\n")
                    if not retest_items:
                        f.write("No retest records found.\n")
                    else:
                        for sn, items in retest_items:
                            results_seq = " -> ".join(
                                f"{i.result}@{i.test_date} {i.test_time}" for i in items
                            )
                            f.write(
                                f"SN: {sn}, Attempts: {len(items)}, Retests: {len(items) - 1}, Results: {results_seq}\n"
                            )
            except OSError as e:
                QMessageBox.warning(
                    self,
                    "Report",
                    "CSV generated, but failed to create TXT summary.\n" + str(e),
                )
                QMessageBox.information(
                    self,
                    "Report",
                    "Report generated.\n" f"CSV: {os.path.normpath(csv_path)}",
                )
                return

            QMessageBox.information(
                self,
                "Report",
                "Report generated.\n"
                f"CSV: {os.path.normpath(csv_path)}\n"
                f"TXT: {os.path.normpath(txt_path)}",
            )

    import sys

    app = QApplication(sys.argv)
    win = WiFiStressLogAnalyzer()
    win.show()
    return app.exec_()


def main() -> int:
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
