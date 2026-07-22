# User Manual

## Assembly

Wire the Teensy 4.1 and EVAL-ADXL355-PMDZ according to `Documents/Hardware/PIN_ASSIGNMENTS.md`. Verify continuity with power disconnected, then verify 3.3 V on PMOD VDD before connecting USB to the host application.

## SD Card Preparation

Use a reliable microSD card formatted as FAT32 or exFAT. Insert it in the Teensy 4.1 built-in socket. Every Start creates a new file named `Data_0.csv`, `Data_1.csv`, and so on. The firmware scans existing numbered files and uses one greater than the highest present number, so gaps are not filled and existing files are never overwritten. Stop writes the session summary, flushes, and closes the active file. During recording, the file is flushed at the configured interval (one second by default).

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
READ FILE Data_0.csv 0 4096
```

## Desktop Application

Run:

```powershell
python -m building_vibration_analyzer
```

Use the connection panel to discover ports, connect, synchronize RTC, start/stop logging, list SD files, download one or several selected logs, delete selected logs after confirmation, and open local CSV files for analysis. SD-card listing, downloading, and deletion run in a worker thread so the interface remains responsive.

For unattended measurements, the logger can record to the Teensy microSD card without the Windows app connected, as long as the Teensy is powered. Use the physical Run/Stop button to begin and end logging. Later, connect USB, click `List SD`, select one or more `Data_N.csv` files, and click `Download Selected`. You can also remove the SD card and open a CSV directly from the local machine.

Local file workflow:

- `Open CSV`: load a downloaded acquisition file or exported window CSV.
- `Save CSV`: save only samples between the two orange selection bars to a local CSV.
- `Export FFT`: calculate and export FFT amplitudes, Welch PSD, ASD, dominant peaks, and frequency-band RMS values using only samples between the selection bars.
- `Data Table`: inspect raw selected-session samples in a read-only grid. Select cells and press `Ctrl+C` to copy tab-separated data.

## Analysis Workflow

1. Open a downloaded `Data_N.csv` file.
2. Select the acquisition session in the file.
3. Inspect time-domain X/Y/Z acceleration.
4. Set the analysis window using the Start/End controls or by dragging the two vertical orange cursors on the time plot.
5. Select frequency-domain traces for X, Y, Z, and either resultant option. `R dynamic` is the FFT/ASD of `sqrt((X-mean(X))^2 + (Y-mean(Y))^2 + (Z-mean(Z))^2)`. `R spectral RSS` combines spectra directly, using `sqrt(X_fft^2 + Y_fft^2 + Z_fft^2)` for FFT amplitude and `sqrt(PSD_X + PSD_Y + PSD_Z)` for ASD.
6. Run FFT, PSD, ASD, spectrogram, dominant-frequency, and band-RMS tools.
7. Use velocity or displacement spectra only with an explicit low-frequency cutoff.
8. Export selected data, export FFT data to Excel, or generate a report.

The selected time window controls the frequency-domain plot, Save CSV, and FFT Excel export. Reversed cursor limits are sorted and limits outside the data are clipped. A zero-width selection is rejected; FFT display/export requires at least five selected samples. Shorter windows have coarser frequency resolution, approximately `sample_rate / selected_sample_count`.

## Synthetic Test Data

The desktop app includes `sample_data/SYNTHETIC_BUILDING_VIBRATION_TEST.csv`. It is a 200 Hz, 20 second synthetic dataset with known vibration peaks. Open it with `Open CSV`, inspect the `Frequency Domain` tab, and use `Export FFT` to produce a workbook for Excel.

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
