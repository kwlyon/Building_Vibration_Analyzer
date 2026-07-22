# USB Serial Protocol

The Teensy interface is USB virtual serial. It is not physical RS-232 and must not be connected directly to +/-RS-232 level hardware.

## Transport

- Line ending: `\n`, with optional `\r` accepted.
- Encoding: ASCII/UTF-8 command text.
- Default monitor baud rate can be any value because Teensy USB serial ignores host baud for data rate, but 115200 is conventional.
- Commands are case-insensitive except filenames.
- Replies are one line unless a file-transfer frame is active.

## Response grammar

Successful command:

```text
OK <COMMAND> [key=value ...]
```

Failed command:

```text
ERR <CODE> message
```

Event records:

```text
EVT <TYPE> [key=value ...]
```

Human-readable help:

```text
INFO <text>
```

The Python application parses the leading token first and then parses `key=value` pairs.

## Core commands

| Command | Behavior |
| --- | --- |
| `HELP` | Print command summary. |
| `STATUS` | Return firmware, state, RTC, sensor, SD, dropped samples, overruns, and current configuration. |
| `START` | Create the next unused `Data_N.csv` file and start logging if sensor and SD checks pass. Returns the new filename. |
| `STOP` | Write the session end record, flush, and close the active CSV file. Returns the closed filename. |
| `GET CONFIG` | Return active configuration. |
| `SET RATE <hz>` | Set requested output data rate. Allowed rates map to ADXL355 ODR codes. |
| `SET RANGE <2|4|8>` | Set ADXL355 measurement range in g. Blocked while recording. |
| `SET FILTER <odr_code> [hpf_code]` | Set raw ADXL355 filter register fields. Blocked while recording except future HPF-only changes. |
| `SET RTC <YYYY-MM-DDTHH:MM:SSZ>` | Set Teensy RTC from host UTC time and mark RTC valid. |
| `GET RTC` | Return current RTC value and validity. |
| `LIST FILES` | List regular files in the SD-card root. |
| `FILE INFO <name>` | Return size and basic metadata. |
| `READ FILE <name> [offset] [length]` | Return an exact-length file chunk for download or terminal use. |
| `DOWNLOAD FILE <name>` | Start framed file transfer. |
| `DELETE FILE <name>` | Delete a validated root-level file only when not recording. Python GUI confirms first. |
| `GET ERRORS` | Return sticky firmware error counters. |
| `CLEAR ERRORS` | Clear sticky counters. |
| `GET SENSOR INFO` | Read ADXL355 identity registers and active config. |
| `CALIBRATE OFFSET` | Placeholder for guided gravity calibration workflow. |
| `SAVE CONFIG` | Write validated config to EEPROM with CRC. |
| `LOAD DEFAULTS` | Restore defaults in RAM. |
| `REBOOT` | Restart Teensy by watchdog/CPU reset. |

## CSV schema

Every acquisition uses a separate file:

```text
Data_0.csv
Data_1.csv
Data_2.csv
```

At Start, firmware scans existing names and selects one greater than the highest existing `Data_N.csv` index. It never fills a lower-numbered gap or opens an existing acquisition file for append. Each file contains one session.

Header:

```text
record_type,session_id,timestamp_iso8601,elapsed_us,sample_number,x_counts,y_counts,z_counts,x_mps2,y_mps2,z_mps2,temperature_c,status_flags
```

Record types:

- `META`: file or firmware metadata.
- `SESSION_START`: start marker with session ID and configuration fields in `status_flags`.
- `DATA`: acceleration sample.
- `EVENT`: RTC sync, configuration change, warning, or button action.
- `FAULT`: sensor, SD, overrun, or buffer failure.
- `SESSION_END`: stop marker and summary counters.

When RTC is invalid, `timestamp_iso8601` is `RTC_INVALID`. Accurate timing still uses `elapsed_us` and `sample_number`.

## File transfer framing

`READ FILE <name> [offset] [length]` returns:

```text
OK READ name=<name> offset=<offset> length=<requested-bytes> bytes=<actual-bytes>
<exactly actual-bytes of raw file data>
END READ
```

The raw payload is followed by a line break and the `END READ` marker. Clients must
read the announced `bytes` count exactly before consuming the framing line break and
end marker. This preserves CSV rows when a chunk boundary falls in the middle of a
line and also prevents payload text from being mistaken for a framing marker.

Filenames accepted by `FILE INFO`, `READ FILE`, and `DELETE FILE` are limited to a
single root-level basename containing ASCII letters, digits, underscore, hyphen, and
period. Empty names, `..`, path separators, and traversal forms are rejected. A read
request is limited to 4096 bytes per chunk.

`DOWNLOAD FILE <name>` returns:

```text
OK DOWNLOAD name=<name> size=<bytes> chunk=<bytes>
BEGIN FILE name=<name> size=<bytes> crc32=<hex-if-known>
CHUNK offset=<decimal> length=<decimal> crc32=<hex>
<raw bytes encoded as base64>
END CHUNK
...
END FILE crc32=<hex>
```

The first firmware implementation supports text reads and a base64-friendly frame shape, but full resumable binary-safe transfers should be hardware-tested before field use.
