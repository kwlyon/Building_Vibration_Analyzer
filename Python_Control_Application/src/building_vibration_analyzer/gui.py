from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from .csv_log import load_sessions, samples_to_arrays
from .protocol import build_set_rtc_command
from .serial_device import DeviceClient, likely_teensy_ports


def main() -> int:
    try:
        from PySide6 import QtCore, QtWidgets
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
    except ImportError as exc:
        print("PySide6 GUI dependencies are not installed.")
        print("Install requirements.txt or run the tested protocol/analysis modules directly.")
        print(f"Missing dependency detail: {exc}")
        return 2

    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Building Vibration Analyzer")
            self.resize(1180, 760)
            self.client = DeviceClient()
            self.sessions = []

            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            layout = QtWidgets.QVBoxLayout(central)

            toolbar = QtWidgets.QHBoxLayout()
            self.port_combo = QtWidgets.QComboBox()
            self.refresh_button = QtWidgets.QPushButton("Refresh")
            self.connect_button = QtWidgets.QPushButton("Connect")
            self.rtc_button = QtWidgets.QPushButton("Sync RTC")
            self.start_button = QtWidgets.QPushButton("Start")
            self.stop_button = QtWidgets.QPushButton("Stop")
            self.open_button = QtWidgets.QPushButton("Open CSV")
            for widget in (
                self.port_combo,
                self.refresh_button,
                self.connect_button,
                self.rtc_button,
                self.start_button,
                self.stop_button,
                self.open_button,
            ):
                toolbar.addWidget(widget)
            layout.addLayout(toolbar)

            splitter = QtWidgets.QSplitter()
            layout.addWidget(splitter, 1)

            left = QtWidgets.QWidget()
            left_layout = QtWidgets.QVBoxLayout(left)
            self.session_list = QtWidgets.QListWidget()
            self.log = QtWidgets.QPlainTextEdit()
            self.log.setReadOnly(True)
            left_layout.addWidget(QtWidgets.QLabel("Sessions"))
            left_layout.addWidget(self.session_list, 1)
            left_layout.addWidget(QtWidgets.QLabel("Device Log"))
            left_layout.addWidget(self.log, 1)
            splitter.addWidget(left)

            right = QtWidgets.QTabWidget()
            self.figure = Figure(figsize=(8, 5))
            self.canvas = FigureCanvas(self.figure)
            right.addTab(self.canvas, "Time Domain")
            self.summary = QtWidgets.QPlainTextEdit()
            self.summary.setReadOnly(True)
            right.addTab(self.summary, "Summary")
            splitter.addWidget(right)
            splitter.setSizes([320, 860])

            self.refresh_button.clicked.connect(self.refresh_ports)
            self.connect_button.clicked.connect(self.toggle_connect)
            self.rtc_button.clicked.connect(self.sync_rtc)
            self.start_button.clicked.connect(lambda: self.send_command("START"))
            self.stop_button.clicked.connect(lambda: self.send_command("STOP"))
            self.open_button.clicked.connect(self.open_csv)
            self.session_list.currentRowChanged.connect(self.plot_session)
            self.refresh_ports()

        def refresh_ports(self) -> None:
            self.port_combo.clear()
            ports = DeviceClient.list_ports()
            ordered = likely_teensy_ports(ports) or ports
            for port in ordered:
                self.port_combo.addItem(f"{port.device} - {port.description}", port.device)

        def toggle_connect(self) -> None:
            if self.client.connected:
                self.client.disconnect()
                self.connect_button.setText("Connect")
                self.append_log("Disconnected")
                return
            port = self.port_combo.currentData()
            if not port:
                return
            self.client.connect(port)
            self.connect_button.setText("Disconnect")
            self.append_log(f"Connected to {port}")
            self.send_command("STATUS")

        def send_command(self, command: str) -> None:
            if not self.client.connected:
                self.append_log("Not connected")
                return
            try:
                responses = self.client.command(command)
            except Exception as exc:
                self.append_log(f"Command failed: {exc}")
                return
            for response in responses:
                self.append_log(str(response))

        def sync_rtc(self) -> None:
            stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            self.send_command(build_set_rtc_command(stamp))

        def open_csv(self) -> None:
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open vibration CSV", str(Path.home()), "CSV files (*.csv)")
            if not filename:
                return
            self.sessions = load_sessions(filename)
            self.session_list.clear()
            for session in self.sessions:
                self.session_list.addItem(f"Session {session.session_id} - {len(session.samples)} samples")
            if self.sessions:
                self.session_list.setCurrentRow(0)

        def plot_session(self, row: int) -> None:
            if row < 0 or row >= len(self.sessions):
                return
            session = self.sessions[row]
            t, data = samples_to_arrays(session.samples)
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            for axis in ("x", "y", "z"):
                ax.plot(t, data[axis], label=axis.upper(), linewidth=0.8)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Acceleration (m/s^2)")
            ax.set_title(f"Session {session.session_id}")
            ax.grid(True, alpha=0.3)
            ax.legend()
            self.canvas.draw()
            self.summary.setPlainText(
                f"Samples: {len(session.samples)}\nDuration: {session.duration_s:.3f} s\n"
                f"Sample rate: {session.sample_rate_hz or 0:.3f} Hz\nFaults: {len(session.faults)}"
            )

        def append_log(self, text: str) -> None:
            self.log.appendPlainText(text)

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
