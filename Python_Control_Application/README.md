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
- Start and stop logging.
- List, inspect, read, and delete SD card files through firmware commands.
- Parse append-only CSV logs and select acquisition sessions.
- Compute time-domain statistics, FFT, PSD, ASD, spectrograms, dominant frequencies, harmonics, coherence, and band RMS.
- Generate HTML and PDF-style reports when Matplotlib is available.
