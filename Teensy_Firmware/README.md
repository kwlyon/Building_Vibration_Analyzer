# Teensy Firmware

Sketch: `BuildingVibrationLogger`

Build target:

```powershell
arduino-cli compile --fqbn teensy:avr:teensy41 Teensy_Firmware/BuildingVibrationLogger
```

The firmware uses Teensyduino/Arduino libraries:

- `SPI` for direct ADXL355 SPI communication.
- `SD` with `BUILTIN_SDCARD` for the Teensy 4.1 microSD socket.
- `EEPROM` for CRC-protected persistent configuration.
- `TimeLib` and `Teensy3Clock` for RTC synchronization.

No hardware-dependent behavior has been validated without the Teensy 4.1 and EVAL-ADXL355-PMDZ attached.
