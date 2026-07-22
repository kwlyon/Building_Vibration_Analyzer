from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from .analysis import (
    amplitude_spectral_density,
    dominant_frequencies,
    dynamic_resultant,
    fft_amplitude,
    root_sum_square_spectra,
    sum_power_spectra,
    welch_psd,
)
from .csv_log import (
    export_session_csv,
    load_sessions,
    normalize_elapsed_window,
    sample_rate_from_samples,
    samples_to_arrays,
    select_samples_by_elapsed,
)
from .excel_export import export_fft_workbook
from .protocol import build_set_rtc_command
from .serial_device import DeviceClient, likely_teensy_ports

BASE_AXES = ("x", "y", "z")
FREQUENCY_TRACE_OPTIONS = (
    ("x", "X", True),
    ("y", "Y", True),
    ("z", "Z", True),
    ("r_dynamic", "R dynamic", False),
    ("r_spectral", "R spectral RSS", False),
)
TRACE_LABELS = {key: label for key, label, _checked in FREQUENCY_TRACE_OPTIONS}


def main() -> int:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
        from matplotlib.figure import Figure
    except ImportError as exc:
        print("PySide6 GUI dependencies are not installed.")
        print("Install requirements.txt or run the tested protocol/analysis modules directly.")
        print(f"Missing dependency detail: {exc}")
        return 2

    class WorkerSignals(QtCore.QObject):
        completed = QtCore.Signal(object)
        failed = QtCore.Signal(str)

    class DeviceWorker(QtCore.QRunnable):
        def __init__(self, operation) -> None:
            super().__init__()
            self.operation = operation
            self.signals = WorkerSignals()

        @QtCore.Slot()
        def run(self) -> None:
            try:
                result = self.operation()
            except Exception as exc:
                self.signals.failed.emit(str(exc))
                return
            self.signals.completed.emit(result)

    class SampleTableModel(QtCore.QAbstractTableModel):
        headers = [
            "timestamp_iso8601",
            "elapsed_s",
            "sample_number",
            "x_counts",
            "y_counts",
            "z_counts",
            "x_mps2",
            "y_mps2",
            "z_mps2",
            "temperature_c",
            "status_flags",
        ]

        def __init__(self) -> None:
            super().__init__()
            self.samples = []

        def set_samples(self, samples) -> None:
            self.beginResetModel()
            self.samples = list(samples)
            self.endResetModel()

        def rowCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else len(self.samples)

        def columnCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else len(self.headers)

        def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
            if role != QtCore.Qt.DisplayRole:
                return None
            if orientation == QtCore.Qt.Horizontal:
                return self.headers[section]
            return section + 1

        def data(self, index, role=QtCore.Qt.DisplayRole):
            if not index.isValid() or role not in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
                return None
            sample = self.samples[index.row()]
            elapsed_s = (sample.elapsed_us - self.samples[0].elapsed_us) / 1_000_000.0 if self.samples else 0.0
            values = [
                sample.timestamp_iso8601,
                f"{elapsed_s:.6f}",
                sample.sample_number,
                sample.x_counts,
                sample.y_counts,
                sample.z_counts,
                f"{sample.x_mps2:.9g}",
                f"{sample.y_mps2:.9g}",
                f"{sample.z_mps2:.9g}",
                "" if sample.temperature_c is None else f"{sample.temperature_c:.6g}",
                sample.status_flags,
            ]
            return values[index.column()]

        def flags(self, index):
            if not index.isValid():
                return QtCore.Qt.NoItemFlags
            return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled

    class CopyableTableView(QtWidgets.QTableView):
        def keyPressEvent(self, event) -> None:
            if event.matches(QtGui.QKeySequence.Copy):
                self.copy_selection()
                return
            super().keyPressEvent(event)

        def copy_selection(self) -> None:
            indexes = self.selectedIndexes()
            if not indexes:
                return
            rows = sorted({idx.row() for idx in indexes})
            cols = sorted({idx.column() for idx in indexes})
            index_set = {(idx.row(), idx.column()): idx for idx in indexes}
            lines = []
            for row in rows:
                fields = []
                for col in cols:
                    idx = index_set.get((row, col))
                    fields.append("" if idx is None else str(idx.data()))
                lines.append("\t".join(fields))
            QtWidgets.QApplication.clipboard().setText("\n".join(lines))

    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Building Vibration Analyzer")
            self.resize(1180, 760)
            self.client = DeviceClient()
            self.sessions = []
            self.analysis_window = None
            self._updating_window_controls = False
            self._dragging_cursor = None
            self._time_axis = None
            self._window_start_line = None
            self._window_end_line = None
            self._window_span = None
            self._device_busy = False
            self._device_workers = set()
            self._device_thread_pool = QtCore.QThreadPool(self)
            self._device_thread_pool.setMaxThreadCount(1)

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
            self.sd_file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
            sd_buttons = QtWidgets.QHBoxLayout()
            self.list_files_button = QtWidgets.QPushButton("List SD")
            self.download_button = QtWidgets.QPushButton("Download Selected")
            self.delete_files_button = QtWidgets.QPushButton("Delete Selected")
            sd_buttons.addWidget(self.list_files_button)
            sd_buttons.addWidget(self.download_button)
            sd_buttons.addWidget(self.delete_files_button)
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
            time_tab = QtWidgets.QWidget()
            time_layout = QtWidgets.QVBoxLayout(time_tab)
            time_layout.setContentsMargins(0, 0, 0, 0)
            window_controls = QtWidgets.QHBoxLayout()
            self.window_start_spin = QtWidgets.QDoubleSpinBox()
            self.window_end_spin = QtWidgets.QDoubleSpinBox()
            for spin in (self.window_start_spin, self.window_end_spin):
                spin.setDecimals(4)
                spin.setSingleStep(0.1)
                spin.setSuffix(" s")
                spin.setMinimum(0.0)
            self.full_window_button = QtWidgets.QPushButton("Full Session")
            window_controls.addWidget(QtWidgets.QLabel("Analysis window"))
            window_controls.addWidget(QtWidgets.QLabel("Start"))
            window_controls.addWidget(self.window_start_spin)
            window_controls.addWidget(QtWidgets.QLabel("End"))
            window_controls.addWidget(self.window_end_spin)
            window_controls.addWidget(self.full_window_button)
            window_controls.addStretch(1)
            time_layout.addLayout(window_controls)
            time_layout.addWidget(NavigationToolbar(self.time_canvas, time_tab))
            time_layout.addWidget(self.time_canvas, 1)
            right.addTab(time_tab, "Time Domain")
            self.freq_figure = Figure(figsize=(8, 5))
            self.freq_canvas = FigureCanvas(self.freq_figure)
            freq_tab = QtWidgets.QWidget()
            freq_layout = QtWidgets.QVBoxLayout(freq_tab)
            freq_layout.setContentsMargins(0, 0, 0, 0)
            axis_controls = QtWidgets.QHBoxLayout()
            self.axis_checkboxes = {}
            for key, label, checked in FREQUENCY_TRACE_OPTIONS:
                checkbox = QtWidgets.QCheckBox(label)
                checkbox.setChecked(checked)
                self.axis_checkboxes[key] = checkbox
                axis_controls.addWidget(checkbox)
            axis_controls.addStretch(1)
            freq_layout.addLayout(axis_controls)
            freq_layout.addWidget(NavigationToolbar(self.freq_canvas, freq_tab))
            freq_layout.addWidget(self.freq_canvas, 1)
            right.addTab(freq_tab, "Frequency Domain")
            self.table_model = SampleTableModel()
            self.data_table = CopyableTableView()
            self.data_table.setModel(self.table_model)
            self.data_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
            self.data_table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
            self.data_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.data_table.setAlternatingRowColors(True)
            self.data_table.horizontalHeader().setStretchLastSection(True)
            copy_action = QtGui.QAction("Copy Selection", self.data_table)
            copy_action.triggered.connect(self.data_table.copy_selection)
            self.data_table.addAction(copy_action)
            self.data_table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
            right.addTab(self.data_table, "Data Table")
            self.summary = QtWidgets.QPlainTextEdit()
            self.summary.setReadOnly(True)
            right.addTab(self.summary, "Summary")
            splitter.addWidget(right)
            splitter.setSizes([320, 860])

            self.refresh_button.clicked.connect(self.refresh_ports)
            self.connect_button.clicked.connect(self.toggle_connect)
            self.rtc_button.clicked.connect(self.sync_rtc)
            self.start_button.clicked.connect(lambda: self.send_command_async("START"))
            self.stop_button.clicked.connect(lambda: self.send_command_async("STOP"))
            self.open_button.clicked.connect(self.open_csv)
            self.save_session_button.clicked.connect(self.save_selected_session)
            self.export_fft_button.clicked.connect(self.export_selected_fft)
            self.list_files_button.clicked.connect(self.list_sd_files)
            self.download_button.clicked.connect(self.download_selected_sd_file)
            self.delete_files_button.clicked.connect(self.delete_selected_sd_files)
            self.session_list.currentRowChanged.connect(self.plot_session)
            self.window_start_spin.valueChanged.connect(self.update_analysis_window_from_controls)
            self.window_end_spin.valueChanged.connect(self.update_analysis_window_from_controls)
            self.full_window_button.clicked.connect(self.reset_analysis_window)
            for checkbox in self.axis_checkboxes.values():
                checkbox.stateChanged.connect(self.refresh_frequency_plot)
            self.time_canvas.mpl_connect("button_press_event", self.on_time_mouse_press)
            self.time_canvas.mpl_connect("motion_notify_event", self.on_time_mouse_move)
            self.time_canvas.mpl_connect("button_release_event", self.on_time_mouse_release)
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

        def set_device_busy(self, busy: bool) -> None:
            self._device_busy = busy
            for widget in (
                self.connect_button,
                self.rtc_button,
                self.start_button,
                self.stop_button,
                self.list_files_button,
                self.download_button,
                self.delete_files_button,
            ):
                widget.setEnabled(not busy)

        def run_device_task(self, description: str, operation, on_success=None) -> None:
            if self._device_busy:
                self.append_log("Another device operation is already in progress")
                return
            self.set_device_busy(True)
            self.append_log(f"{description}...")
            worker = DeviceWorker(operation)
            self._device_workers.add(worker)

            def completed(result) -> None:
                self._device_workers.discard(worker)
                self.set_device_busy(False)
                if on_success is not None:
                    on_success(result)

            def failed(message: str) -> None:
                self._device_workers.discard(worker)
                self.set_device_busy(False)
                self.append_log(f"{description} failed: {message}")
                QtWidgets.QMessageBox.warning(self, description, message)

            worker.signals.completed.connect(completed)
            worker.signals.failed.connect(failed)
            self._device_thread_pool.start(worker)

        def send_command_async(self, command: str) -> None:
            if not self.client.connected:
                self.append_log("Not connected")
                return

            def show_responses(responses) -> None:
                for response in responses:
                    self.append_log(str(response))

            self.run_device_task(command, lambda: self.client.command(command), show_responses)

        def sync_rtc(self) -> None:
            stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            self.send_command_async(build_set_rtc_command(stamp))

        def list_sd_files(self) -> None:
            if not self.client.connected:
                self.append_log("Connect to the Teensy before listing SD files")
                return
            self.run_device_task("Listing SD-card files", self.client.list_files, self.populate_sd_file_list)

        def populate_sd_file_list(self, files) -> None:
            self.sd_file_list.clear()
            for remote_file in files:
                item = QtWidgets.QListWidgetItem(f"{remote_file.name} ({remote_file.size} bytes)")
                item.setData(QtCore.Qt.UserRole, remote_file.name)
                self.sd_file_list.addItem(item)
            self.append_log(f"Listed {len(files)} SD-card file(s)")

        def selected_sd_filenames(self) -> list[str]:
            return [item.data(QtCore.Qt.UserRole) for item in self.sd_file_list.selectedItems()]

        def download_selected_sd_file(self) -> None:
            if not self.client.connected:
                self.append_log("Connect to the Teensy before downloading SD files")
                return
            remote_names = self.selected_sd_filenames()
            if not remote_names:
                self.append_log("Select one or more SD files first")
                return
            destination_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Choose download folder", str(Path.home() / "Downloads")
            )
            if not destination_dir:
                return
            destination_root = Path(destination_dir)
            destinations = [(name, destination_root / Path(name).name) for name in remote_names]
            existing = [path.name for _name, path in destinations if path.exists()]
            if existing:
                answer = QtWidgets.QMessageBox.question(
                    self,
                    "Overwrite downloaded files?",
                    "The following files already exist and will be replaced:\n\n" + "\n".join(existing),
                )
                if answer != QtWidgets.QMessageBox.Yes:
                    return

            def download_all():
                downloaded = []
                for remote_name, destination in destinations:
                    self.client.save_read_file_chunks(remote_name, destination)
                    downloaded.append(destination)
                return downloaded

            def download_complete(downloaded) -> None:
                for path in downloaded:
                    self.append_log(f"Downloaded {path.name} to {path}")
                if len(downloaded) == 1 and downloaded[0].suffix.lower() == ".csv":
                    self.load_csv(str(downloaded[0]))

            self.run_device_task(f"Downloading {len(remote_names)} file(s)", download_all, download_complete)

        def delete_selected_sd_files(self) -> None:
            if not self.client.connected:
                self.append_log("Connect to the Teensy before deleting SD files")
                return
            remote_names = self.selected_sd_filenames()
            if not remote_names:
                self.append_log("Select one or more SD files first")
                return
            answer = QtWidgets.QMessageBox.question(
                self,
                "Delete selected SD-card files?",
                "Permanently delete these files from the SD card?\n\n" + "\n".join(remote_names),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return

            def delete_all():
                deleted = []
                errors = []
                for remote_name in remote_names:
                    try:
                        self.client.delete_file(remote_name)
                        deleted.append(remote_name)
                    except Exception as exc:
                        errors.append(f"{remote_name}: {exc}")
                return deleted, errors

            def delete_complete(result) -> None:
                deleted, errors = result
                if deleted:
                    self.append_log("Deleted: " + ", ".join(deleted))
                if errors:
                    message = "\n".join(errors)
                    self.append_log("Delete errors:\n" + message)
                    QtWidgets.QMessageBox.warning(self, "Some files were not deleted", message)
                elif deleted:
                    QtWidgets.QMessageBox.information(self, "Delete complete", f"Deleted {len(deleted)} file(s).")
                self.list_sd_files()

            self.run_device_task(f"Deleting {len(remote_names)} file(s)", delete_all, delete_complete)

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

        def selected_axes(self):
            return tuple(axis for axis, checkbox in self.axis_checkboxes.items() if checkbox.isChecked())

        def analysis_endpoints(self, session):
            if self.analysis_window is None:
                return (0.0, session.duration_s)
            start, end = self.analysis_window
            duration = session.duration_s
            return (
                max(0.0, min(duration, float(start))),
                max(0.0, min(duration, float(end))),
            )

        def selected_window(self, session):
            return normalize_elapsed_window(session, *self.analysis_endpoints(session))

        def selected_window_samples(self, session):
            start, end = self.selected_window(session)
            return select_samples_by_elapsed(session, start, end)

        def set_window_controls(self, session, start: float, end: float) -> None:
            self._updating_window_controls = True
            try:
                for spin in (self.window_start_spin, self.window_end_spin):
                    spin.setMaximum(max(session.duration_s, 0.001))
                self.window_start_spin.setValue(start)
                self.window_end_spin.setValue(end)
            finally:
                self._updating_window_controls = False

        def apply_analysis_window(self, start: float, end: float, refresh_frequency: bool = True) -> None:
            session = self.selected_session()
            if session is None or not session.samples:
                return
            duration = session.duration_s
            start = max(0.0, min(float(start), duration))
            end = max(0.0, min(float(end), duration))
            self.analysis_window = (start, end)
            self.set_window_controls(session, start, end)
            self.update_window_artists(start, end)
            if refresh_frequency:
                self.refresh_frequency_plot()

        def update_analysis_window_from_controls(self) -> None:
            if self._updating_window_controls:
                return
            self.apply_analysis_window(self.window_start_spin.value(), self.window_end_spin.value())

        def reset_analysis_window(self) -> None:
            session = self.selected_session()
            if session is None:
                return
            self.analysis_window = (0.0, session.duration_s)
            self.set_window_controls(session, 0.0, session.duration_s)
            self.draw_time_plot(session)
            self.refresh_frequency_plot()

        def on_time_mouse_press(self, event) -> None:
            session = self.selected_session()
            if session is None or event.inaxes != self._time_axis or event.xdata is None:
                return
            start, end = self.analysis_endpoints(session)
            tolerance = max(session.duration_s * 0.015, 0.02)
            if abs(event.xdata - start) <= abs(event.xdata - end) and abs(event.xdata - start) <= tolerance:
                self._dragging_cursor = "start"
            elif abs(event.xdata - end) <= tolerance:
                self._dragging_cursor = "end"

        def on_time_mouse_move(self, event) -> None:
            session = self.selected_session()
            if self._dragging_cursor is None or session is None or event.inaxes != self._time_axis or event.xdata is None:
                return
            start, end = self.analysis_endpoints(session)
            if self._dragging_cursor == "start":
                start = event.xdata
            else:
                end = event.xdata
            self.apply_analysis_window(start, end, refresh_frequency=False)

        def on_time_mouse_release(self, event) -> None:
            if self._dragging_cursor is None:
                return
            self._dragging_cursor = None
            self.refresh_frequency_plot()

        def save_selected_session(self) -> None:
            session = self.selected_session()
            if session is None:
                self.append_log("Select a session before saving")
                return
            start, end = self.selected_window(session)
            selected_samples = select_samples_by_elapsed(session, start, end)
            if end <= start or not selected_samples:
                self.append_log("Save failed: selected time window contains no usable samples")
                QtWidgets.QMessageBox.warning(self, "Save CSV", "Select a non-zero time window containing data.")
                return
            default_name = str(Path.home() / "Downloads" / f"session_{session.session_id}.csv")
            destination, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save selected session CSV", default_name, "CSV files (*.csv)")
            if not destination:
                return
            try:
                export_session_csv(session, destination, time_window=(start, end))
            except Exception as exc:
                self.append_log(f"Save failed: {exc}")
                return
            self.append_log(
                f"Saved {len(selected_samples)} selected samples from session {session.session_id} to {destination}"
            )

        def export_selected_fft(self) -> None:
            session = self.selected_session()
            if session is None:
                self.append_log("Select a session before exporting FFT data")
                return
            start, end = self.selected_window(session)
            selected_samples = select_samples_by_elapsed(session, start, end)
            if end <= start or len(selected_samples) < 5:
                self.append_log("FFT export failed: select a non-zero window containing at least five samples")
                QtWidgets.QMessageBox.warning(
                    self, "Export FFT", "Select a non-zero time window containing at least five samples."
                )
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
                export_fft_workbook(session, destination, time_window=(start, end), axes=self.selected_axes())
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
                self.table_model.set_samples([])
                return
            self.analysis_window = (0.0, session.duration_s)
            self.set_window_controls(session, 0.0, session.duration_s)
            self.table_model.set_samples(session.samples)
            self.data_table.resizeColumnsToContents()
            self.draw_time_plot(session)
            self.refresh_frequency_plot()

        def draw_time_plot(self, session) -> None:
            t, data = samples_to_arrays(session.samples)
            self.time_figure.clear()
            ax = self.time_figure.add_subplot(111)
            for axis in ("x", "y", "z"):
                ax.plot(t, data[axis], label=axis.upper(), linewidth=0.8)
            start, end = self.analysis_endpoints(session)
            left, right = sorted((start, end))
            self._time_axis = ax
            self._window_span = ax.axvspan(left, right, color="tab:orange", alpha=0.12)
            self._window_start_line = ax.axvline(start, color="tab:orange", linewidth=1.4, linestyle="--", picker=5)
            self._window_end_line = ax.axvline(end, color="tab:orange", linewidth=1.4, linestyle="--", picker=5)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Acceleration (m/s^2)")
            ax.set_title(f"Session {session.session_id}")
            ax.grid(True, alpha=0.3)
            ax.legend()
            self.time_canvas.draw()

        def update_window_artists(self, start: float, end: float) -> None:
            if self._time_axis is None:
                return
            if self._window_start_line is not None:
                self._window_start_line.set_xdata([start, start])
            if self._window_end_line is not None:
                self._window_end_line.set_xdata([end, end])
            if self._window_span is not None:
                self._window_span.remove()
            left, right = sorted((start, end))
            self._window_span = self._time_axis.axvspan(left, right, color="tab:orange", alpha=0.12)
            self.time_canvas.draw_idle()

        def refresh_frequency_plot(self) -> None:
            session = self.selected_session()
            if session is None or not session.samples:
                return
            self.freq_figure.clear()
            selected_samples = self.selected_window_samples(session)
            fs = sample_rate_from_samples(selected_samples) or 0.0
            axes = self.selected_axes()
            if fs > 0 and len(selected_samples) > 4 and axes:
                t, data = samples_to_arrays(selected_samples)
                data["r_dynamic"] = dynamic_resultant(data["x"], data["y"], data["z"])
                top = self.freq_figure.add_subplot(211)
                bottom = self.freq_figure.add_subplot(212)
                fft_cache = {}
                psd_cache = {}

                def independent_fft(axis):
                    if axis not in fft_cache:
                        fft_cache[axis] = fft_amplitude(data[axis], fs)
                    return fft_cache[axis]

                def trace_fft(axis):
                    if axis == "r_spectral":
                        spectra = [independent_fft(base_axis) for base_axis in BASE_AXES]
                        return spectra[0][0], root_sum_square_spectra(*(spectrum[1] for spectrum in spectra))
                    return independent_fft(axis)

                nfft = min(1024, len(selected_samples))

                def independent_psd(axis):
                    if axis not in psd_cache:
                        psd_cache[axis] = welch_psd(data[axis], fs, fft_length=nfft)
                    return psd_cache[axis]

                def trace_asd(axis):
                    if axis == "r_spectral":
                        spectra = [independent_psd(base_axis) for base_axis in BASE_AXES]
                        psd = sum_power_spectra(*(spectrum[1] for spectrum in spectra))
                        return spectra[0][0], amplitude_spectral_density(psd)
                    freq_psd, psd = independent_psd(axis)
                    return freq_psd, amplitude_spectral_density(psd)

                dominant_lines = []
                for axis in axes:
                    freq, amp = trace_fft(axis)
                    label = TRACE_LABELS.get(axis, axis.upper())
                    top.plot(freq, amp, label=label, linewidth=0.8)
                    peaks = dominant_frequencies(freq, amp, count=1, min_frequency=max(0.5, freq[1] if len(freq) > 1 else 0.0))
                    if peaks:
                        dominant_lines.append(f"{label}: {peaks[0][0]:.3g} Hz ({peaks[0][1]:.3g} m/s^2)")
                top.set_ylabel("FFT amplitude (m/s^2)")
                top.set_title(f"Frequency Domain - Session {session.session_id}")
                top.grid(True, alpha=0.3)
                top.legend()

                for axis in axes:
                    freq_psd, asd = trace_asd(axis)
                    label = TRACE_LABELS.get(axis, axis.upper())
                    bottom.semilogy(freq_psd, asd, label=label, linewidth=0.9)
                bottom.set_xlabel("Frequency (Hz)")
                bottom.set_ylabel("ASD (m/s^2/sqrt(Hz))")
                bottom.grid(True, which="both", alpha=0.3)
                bottom.legend()
                self.freq_figure.tight_layout()
                dominant_text = "\nDominant frequencies:\n" + "\n".join(dominant_lines)
            else:
                ax_freq = self.freq_figure.add_subplot(111)
                message = "Need at least five selected samples with valid elapsed_us timing."
                if not axes:
                    message = "Select at least one frequency-domain trace."
                ax_freq.text(0.5, 0.5, message, ha="center", va="center")
                ax_freq.axis("off")
                dominant_text = ""
            self.freq_canvas.draw()

            start, end = self.selected_window(session)
            window_duration = max(0.0, end - start)
            resolution = (fs / len(selected_samples)) if fs > 0 and selected_samples else 0.0
            self.summary.setPlainText(
                f"Samples: {len(session.samples)}\nDuration: {session.duration_s:.3f} s\n"
                f"Sample rate: {session.sample_rate_hz or 0:.3f} Hz\nFaults: {len(session.faults)}\n"
                f"Analysis window: {start:.4f} s to {end:.4f} s ({window_duration:.4f} s)\n"
                f"Selected samples: {len(selected_samples)}\nFrequency resolution: {resolution:.6g} Hz"
                f"{dominant_text}"
            )

        def append_log(self, text: str) -> None:
            self.log.appendPlainText(text)

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
