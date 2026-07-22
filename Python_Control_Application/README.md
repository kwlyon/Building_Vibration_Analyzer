# Python Control Application

Windows desktop control and analysis application for the Building Vibration Analyzer.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python -m building_vibration_analyzer
```

PySide6 is required for the GUI. The core protocol, CSV parsing, and vibration-analysis modules are tested separately and can be used without the GUI package installed.

## Main Features

- Discover serial ports with pyserial.
- Send documented Teensy commands and parse `OK` / `ERR` / `EVT` replies.
- Synchronize the Teensy RTC.
- Start a newly numbered `Data_N.csv` acquisition and stop/close it safely.
- List SD files with multi-selection, download selected files, and delete selected files after confirmation without blocking the GUI.
- Parse acquisition CSV logs and select sessions.
- Compute time-domain statistics, FFT, PSD, ASD, spectrograms, dominant frequencies, harmonics, coherence, and band RMS.
- Generate HTML and PDF-style reports when Matplotlib is available.
- Save only the current cursor-selected time window back to a local CSV file.
- Export selected-session FFT, PSD, ASD, band RMS, dominant peaks, and source time data to one `.xlsx` workbook.
- Select the analysis time window with numeric start/end controls or draggable vertical cursors on the time-domain plot.
- Show selectable X, Y, Z, dynamic resultant (`R dynamic`), and spectral root-sum-square resultant (`R spectral RSS`) traces in FFT and ASD plots.
- Inspect raw session samples in a read-only data table and copy selected cells with `Ctrl+C`.

## Test Data

`sample_data/SYNTHETIC_BUILDING_VIBRATION_TEST.csv` is a synthetic 200 Hz, 20 second data file with known frequency content. Open it with `Open CSV`, select the session, inspect the frequency tab, and use `Export FFT` to create a workbook for Excel.
