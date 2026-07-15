# Building Vibration Analyzer

Portable building-vibration logger and Windows analysis tool using a Teensy 4.1, an Analog Devices EVAL-ADXL355-PMDZ accelerometer board, the Teensy built-in microSD socket, one RGB status LED, one Run/Stop button, and USB virtual serial.

## Project Status

This repository contains:

- Modular Teensy firmware for SPI ADXL355 acquisition, append-only CSV logging, RTC sync, LED/button handling, and a human-readable USB serial command protocol.
- Hardware and protocol documentation for the selected Teensy pins and ADXL355 PMOD wiring.
- A Python control/analysis application scaffold with tested protocol parsing, CSV session parsing, and vibration-analysis routines.
- A repeatable Windows release script.

No actual Teensy or ADXL355 hardware was available in this coding environment. Hardware behavior must be validated on the bench before using the logger for real measurements.

## Hardware Overview

The ADXL355 is read directly over SPI from the Teensy 4.1. The PMOD board is powered from Teensy 3.3 V. The Teensy built-in microSD socket stores all acquisition sessions in one persistent append-only CSV file, `VIBRATION_DATA.CSV`.

Default pin choices are documented in `Documents/Hardware/PIN_ASSIGNMENTS.md`.

## Software Overview

- `Teensy_Firmware/BuildingVibrationLogger`: Arduino-compatible Teensy firmware.
- `Python_Control_Application`: Python desktop control and analysis app.
- `Documents/Protocol/SERIAL_PROTOCOL.md`: serial command and CSV schema.
- `Tools/build_windows_release.ps1`: repeatable Windows build script.

## Firmware Build

Install Arduino IDE 2.x or Arduino CLI with the Teensy boards package. This machine has `arduino-cli` and `teensy:avr` installed.

```powershell
arduino-cli compile --fqbn teensy:avr:teensy41 Teensy_Firmware/BuildingVibrationLogger
```

## Python Development

```powershell
cd Python_Control_Application
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python -m building_vibration_analyzer
```

The GUI prefers PySide6. Core protocol, CSV parsing, and analysis modules can be tested without PySide6.

## Executable Build

```powershell
.\Tools\build_windows_release.ps1
```

The script creates a virtual environment, installs pinned dependencies, runs tests, attempts the Teensy compile when Arduino CLI is present, builds a PyInstaller executable, copies sample files, and writes SHA-256 checksums under `Releases`.

## Basic Operation

1. Wire the ADXL355 PMOD board to Teensy 4.1 as documented.
2. Insert a formatted microSD card.
3. Connect USB to the Windows computer.
4. Use the Python app or a serial terminal.
5. Send `SET RTC <timestamp>` before field logging when wall-clock time matters.
6. Send `START` or press the Run/Stop button.
7. Send `STOP` or press the button again before unplugging power.
8. Download or remove the SD card and analyze selected sessions.

The desktop app also supports purely local file work: open a CSV from disk, save a selected session as a new CSV, inspect raw samples in a read-only copyable data table, select an analysis time window with draggable cursors, and export the selected window's frequency-analysis data to a single Excel `.xlsx` workbook.

## Safety and Measurement Limits

This is not a safety-rated seismic instrument. Static gravity calibration does not provide traceable dynamic calibration. Derived velocity and displacement spectra require low-frequency cutoffs and careful interpretation because integration amplifies drift and low-frequency noise.

## GitHub Remote

This directory is initialized as a local git repository. No remote is configured by default. To publish later:

```powershell
git remote add origin https://github.com/<account>/Building_Vibration_Analyzer.git
git branch -M main
git push -u origin main
```

## Documentation

- `Documents/Datasheets/SOURCES.md`
- `Documents/Hardware/WIRING.md`
- `Documents/Hardware/PIN_ASSIGNMENTS.md`
- `Documents/Hardware/RTC_AND_POWER.md`
- `Documents/Hardware/SENSOR_MOUNTING.md`
- `Documents/Protocol/SERIAL_PROTOCOL.md`
- `Documents/User_Manual/USER_MANUAL.md`
