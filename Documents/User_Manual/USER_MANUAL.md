# User Manual

## Assembly

Wire the Teensy 4.1 and EVAL-ADXL355-PMDZ according to `Documents/Hardware/PIN_ASSIGNMENTS.md`. Verify continuity with power disconnected, then verify 3.3 V on PMOD VDD before connecting USB to the host application.

## SD Card Preparation

Use a reliable microSD card formatted as FAT32 or exFAT. Insert it in the Teensy 4.1 built-in socket. The firmware writes to `VIBRATION_DATA.CSV` by default and appends every run to that file.

## RTC Battery and Time Sync

Install a 3 V coin cell from VBAT to GND if wall-clock time must survive power-off. Before each important run, synchronize from the host with the desktop app or:

```text
SET RTC 2026-07-14T12:34:56Z
```

If the RTC is invalid, samples still include elapsed microseconds and sample numbers.

## LED Meanings

- Blue steady: idle and ready.
- Green pulse: recording.
- Yellow: SD/configuration activity or warning.
- Purple/cyan: host command or transfer activity.
- Red steady: critical fault.
- Red blink: SD failure, sensor failure, buffer overrun, or dropped samples.

## Button Operation

Press Run/Stop once while idle to start logging. Press once while recording to stop, flush, and close the CSV file. The firmware debounces the button and prevents rapid repeated transitions.

## Terminal Commands

Open the Teensy virtual COM port with a terminal or Arduino Serial Monitor and type `HELP`. Common commands:

```text
STATUS
GET SENSOR INFO
SET RTC 2026-07-14T12:34:56Z
START
STOP
LIST FILES
DOWNLOAD FILE VIBRATION_DATA.CSV
```

## Desktop Application

Run:

```powershell
python -m building_vibration_analyzer
```

Use the connection panel to discover ports, connect, synchronize RTC, start/stop logging, list SD files, download logs, and open local CSV files for analysis.

## Analysis Workflow

1. Open `VIBRATION_DATA.CSV`.
2. Select one session from the append-only file.
3. Inspect time-domain X/Y/Z acceleration.
4. Remove mean or detrend if appropriate.
5. Run FFT, PSD, ASD, spectrogram, dominant-frequency, and band-RMS tools.
6. Use velocity or displacement spectra only with an explicit low-frequency cutoff.
7. Export selected data or generate a report.

## Units

Firmware calibrated acceleration is stored in `m/s^2`. Raw counts are preserved. The Python app can also display `g`, micro-g, PSD in `(m/s^2)^2/Hz`, ASD in `m/s^2/sqrt(Hz)`, velocity in `mm/s`, and displacement in `um` or `nm`.

## Static Gravity Calibration

For each axis:

1. Place the axis in +1 g orientation and record stable data.
2. Place the same axis in -1 g orientation and record stable data.
3. Offset is the midpoint of the two readings.
4. Scale factor is derived from half the difference.
5. Save the calibration coefficients with `SAVE CONFIG`.

This improves static scale and offset estimates. It is not dynamic or traceable calibration.

## Troubleshooting

- No COM port: try a data-capable USB cable and check Teensy USB type is Serial.
- `ERR SD`: reformat or replace the microSD card, then power-cycle and retry.
- `ERR SENSOR`: verify PMOD wiring, 3.3 V power, CS, and SPI lines.
- Frequent overruns: lower sample rate, use a faster SD card, or increase flush interval.
- No wall-clock time: send `SET RTC` and consider adding a VBAT coin cell.

## Known Limitations

- Hardware timing, SD write robustness, and electrical noise have not been validated on real hardware in this environment.
- File transfer framing is implemented conservatively; large transfers should be tested before field use.
- Dynamic vibration calibration requires external calibrated equipment.
