# RTC and Power

## Teensy RTC

Teensy 4.1 includes an RTC driven by a 32.768 kHz crystal. It can keep date/time while the main board is unpowered if a 3 V coin cell is connected to VBAT and GND.

This firmware treats wall-clock time as valid only after either:

- The host sends `SET RTC <ISO-8601 timestamp>`.
- A retained RTC value appears plausible at startup.

If RTC validity is uncertain, logged samples still include `elapsed_us` and `sample_number`, while `timestamp_iso8601` is marked `RTC_INVALID`.

## Backup battery

Connect a CR2032 positive terminal to VBAT and negative terminal to GND. Do not connect rechargeable cells unless the holder and circuit are designed for that chemistry.

The RTC backup battery is not a substitute for the main USB/VIN supply. It only maintains the RTC domain.

## Main power

For development, power the Teensy from USB. If powering from VIN in the field, review the PJRC VUSB/VIN guidance so external 5 V does not backfeed the host USB port.

The EVAL-ADXL355-PMDZ should draw far less than the Teensy 3.3 V auxiliary output limit, but avoid powering additional loads from 3.3 V without a current budget.

## Power-loss behavior

On sudden power loss, buffered CSV data not yet flushed may be lost. For field logging:

- Use a reliable USB power source or battery pack.
- Stop logging before unplugging.
- Consider a small UPS or supercapacitor-assisted shutdown if unattended operation becomes important.
