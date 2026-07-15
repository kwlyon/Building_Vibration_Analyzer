from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from .analysis import amplitude_spectral_density, dominant_frequencies, fft_amplitude, welch_psd
from .csv_log import export_session_csv, load_sessions, samples_to_arrays
from .excel_export import export_fft_workbook
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
            local_buttons = QtWidgets.QHBoxLayout()
            self.save_session_button = QtWidgets.QPushButton("Save CSV")
            self.export_fft_button = QtWidgets.QPushButton("Export FFT")
            local_buttons.addWidget(self.save_session_button)
            local_buttons.addWidget(self.export_fft_button)
            self.sd_file_list = QtWidgets.QListWidget()
            sd_buttons = QtWidgets.QHBoxLayout()
            self.list_files_button = QtWidgets.QPushButton("List SD")
            self.download_button = QtWidgets.QPushButton("Download")
            sd_buttons.addWidget(self.list_files_button)
            sd_buttons.addWidget(self.download_button)
            self.log = QtWidgets.QPlainTextEdit()
            self.log.setReadOnly(True)
            left_layout.addWidget(QtWidgets.QLabel("Sessions"))
            left_layout.addWidget(self.session_list, 1)
            left_layout.addLayout(local_buttons)
            left_layout.addWidget(QtWidgets.QLabel("SD Card Files"))
            left_layout.addWidget(self.sd_file_list, 1)
            left_layout.addLayout(sd_buttons)
            left_layout.addWidget(QtWidgets.QLabel("Device Log"))
            left_layout.addWidget(self.log, 1)
            splitter.addWidget(left)

            right = QtWidgets.QTabWidget()
            self.time_figure = Figure(figsize=(8, 5))
            self.time_canvas = FigureCanvas(self.time_figure)
            right.addTab(self.time_canvas, "Time Domain")
            self.freq_figure = Figure(figsize=(8, 5))
            self.freq_canvas = FigureCanvas(self.freq_figure)
            right.addTab(self.freq_canvas, "Frequency Domain")
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
            self.save_session_button.clicked.connect(self.save_selected_session)
            self.export_fft_button.clicked.connect(self.export_selected_fft)
            self.list_files_button.clicked.connect(self.list_sd_files)
            self.download_button.clicked.connect(self.download_selected_sd_file)
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
            return responses

        def sync_rtc(self) -> None:
            stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            self.send_command(build_set_rtc_command(stamp))

        def list_sd_files(self) -> None:
            if not self.client.connected:
                self.append_log("Connect to the Teensy before listing SD files")
                return
            responses = self.send_command("LIST FILES") or []
            self.sd_file_list.clear()
            for response in responses:
                if response.kind == "FILE" and "name" in response.fields:
                    size = response.fields.get("size", "?")
                    item = QtWidgets.QListWidgetItem(f"{response.fields['name']} ({size} bytes)")
                    item.setData(QtCore.Qt.UserRole, response.fields["name"])
                    self.sd_file_list.addItem(item)

        def download_selected_sd_file(self) -> None:
            if not self.client.connected:
                self.append_log("Connect to the Teensy before downloading SD files")
                return
            item = self.sd_file_list.currentItem()
            if item is None:
                self.append_log("Select an SD file first")
                return
            remote_name = item.data(QtCore.Qt.UserRole)
            default_name = str(Path.home() / "Downloads" / remote_name)
            destination, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save SD file", default_name, "CSV files (*.csv);;All files (*.*)")
            if not destination:
                return
            try:
                self.client.save_read_file_chunks(remote_name, Path(destination))
            except Exception as exc:
                self.append_log(f"Download failed: {exc}")
                return
            self.append_log(f"Downloaded {remote_name} to {destination}")
            if destination.lower().endswith(".csv"):
                self.load_csv(destination)

        def open_csv(self) -> None:
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open vibration CSV", str(Path.home()), "CSV files (*.csv)")
            if not filename:
                return
            self.load_csv(filename)

        def load_csv(self, filename: str) -> None:
            self.sessions = load_sessions(filename)
            self.session_list.clear()
            for session in self.sessions:
                self.session_list.addItem(f"Session {session.session_id} - {len(session.samples)} samples")
            if self.sessions:
                self.session_list.setCurrentRow(0)

        def selected_session(self):
            row = self.session_list.currentRow()
            if row < 0 or row >= len(self.sessions):
                return None
            return self.sessions[row]

        def save_selected_session(self) -> None:
            session = self.selected_session()
            if session is None:
                self.append_log("Select a session before saving")
                return
            default_name = str(Path.home() / "Downloads" / f"session_{session.session_id}.csv")
            destination, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save selected session CSV", default_name, "CSV files (*.csv)")
            if not destination:
                return
            try:
                export_session_csv(session, destination)
            except Exception as exc:
                self.append_log(f"Save failed: {exc}")
                return
            self.append_log(f"Saved session {session.session_id} to {destination}")

        def export_selected_fft(self) -> None:
            session = self.selected_session()
            if session is None:
                self.append_log("Select a session before exporting FFT data")
                return
            default_name = str(Path.home() / "Downloads" / f"session_{session.session_id}_fft_export.xlsx")
            destination, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export frequency analysis workbook", default_name, "Excel workbooks (*.xlsx)"
            )
            if not destination:
                return
            if not destination.lower().endswith(".xlsx"):
                destination += ".xlsx"
            try:
                export_fft_workbook(session, destination)
            except Exception as exc:
                self.append_log(f"FFT export failed: {exc}")
                return
            self.append_log(f"Exported FFT workbook for session {session.session_id} to {destination}")

        def plot_session(self, row: int) -> None:
            if row < 0 or row >= len(self.sessions):
                return
            session = self.sessions[row]
            if not session.samples:
                self.summary.setPlainText(f"Session {session.session_id} has no valid DATA samples.")
                return
            t, data = samples_to_arrays(session.samples)
            self.time_figure.clear()
            ax = self.time_figure.add_subplot(111)
            for axis in ("x", "y", "z"):
                ax.plot(t, data[axis], label=axis.upper(), linewidth=0.8)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Acceleration (m/s^2)")
            ax.set_title(f"Session {session.session_id}")
            ax.grid(True, alpha=0.3)
            ax.legend()
            self.time_canvas.draw()

            self.freq_figure.clear()
            fs = session.sample_rate_hz or 0.0
            if fs > 0 and len(session.samples) > 4:
                top = self.freq_figure.add_subplot(211)
                bottom = self.freq_figure.add_subplot(212)
                dominant_lines = []
                for axis in ("x", "y", "z"):
                    freq, amp = fft_amplitude(data[axis], fs)
                    top.plot(freq, amp, label=axis.upper(), linewidth=0.8)
                    peaks = dominant_frequencies(freq, amp, count=1, min_frequency=max(0.5, freq[1] if len(freq) > 1 else 0.0))
                    if peaks:
                        dominant_lines.append(f"{axis.upper()}: {peaks[0][0]:.3g} Hz ({peaks[0][1]:.3g} m/s^2)")
                top.set_ylabel("FFT amplitude (m/s^2)")
                top.set_title(f"Frequency Domain - Session {session.session_id}")
                top.grid(True, alpha=0.3)
                top.legend()

                nfft = min(1024, len(data["z"]))
                freq_psd, psd = welch_psd(data["z"], fs, fft_length=nfft)
                asd = amplitude_spectral_density(psd)
                bottom.semilogy(freq_psd, asd, color="tab:purple", linewidth=0.9)
                bottom.set_xlabel("Frequency (Hz)")
                bottom.set_ylabel("Z ASD (m/s^2/sqrt(Hz))")
                bottom.grid(True, which="both", alpha=0.3)
                self.freq_figure.tight_layout()
                dominant_text = "\nDominant frequencies:\n" + "\n".join(dominant_lines)
            else:
                ax_freq = self.freq_figure.add_subplot(111)
                ax_freq.text(0.5, 0.5, "Need at least five samples with valid elapsed_us timing.", ha="center", va="center")
                ax_freq.axis("off")
                dominant_text = ""
            self.freq_canvas.draw()

            self.summary.setPlainText(
                f"Samples: {len(session.samples)}\nDuration: {session.duration_s:.3f} s\n"
                f"Sample rate: {session.sample_rate_hz or 0:.3f} Hz\nFaults: {len(session.faults)}"
                f"{dominant_text}"
            )

        def append_log(self, text: str) -> None:
            self.log.appendPlainText(text)

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
