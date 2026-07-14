# Datasheet and Source Inventory

Downloaded and cited on 2026-07-14.

The project uses manufacturer documentation as the technical authority. A few large or access-controlled files could not be downloaded automatically, so their official source URLs are still recorded here.

| Local filename | Title | Manufacturer | Revision/date | Source URL | Project use |
| --- | --- | --- | --- | --- | --- |
| `PJRC_Teensy_4_1_Pinout_Front_card11a_rev4_web.pdf` | Teensy 4.1 pinout card, front | PJRC | Rev. 4 | https://www.pjrc.com/teensy/card11a_rev4_web.pdf | Pin selection, SPI pin names, SD socket awareness |
| `PJRC_Teensy_4_1_Pinout_Back_card11b_rev4_web.pdf` | Teensy 4.1 pinout card, back | PJRC | Rev. 4 | https://www.pjrc.com/teensy/card11b_rev4_web.pdf | Alternate pin functions and bottom-side pin references |
| `PJRC_Teensy_4_1_Product_Page.html` | Teensy 4.1 development board product page | PJRC | Current page captured 2026-07-14 | https://www.pjrc.com/store/teensy41.html | 3.3 V I/O, non-5 V-tolerant pins, SDIO socket, RTC/VBAT, USB serial, EEPROM size |
| `SparkFun_DEV_16996_Teensy_4_1_Headers_Product_Page.html` | Teensy 4.1 with headers product page | SparkFun | Current page captured 2026-07-14 | https://www.sparkfun.com/products/16996 | Confirms SparkFun DEV-16996 product identity |
| `Analog_Devices_ADXL354_ADXL355_Data_Sheet_RevD.pdf` | ADXL354/ADXL355 data sheet | Analog Devices | Rev. D | https://www.analog.com/media/en/technical-documentation/data-sheets/adxl354_adxl355.pdf | ADXL355 SPI protocol, register map, signed 20-bit format, scale factors, DRDY, filter/range settings |
| Not downloaded automatically | EVAL-ADXL355-PMDZ user guide | Analog Devices Wiki | Approved 2023-04-20; ADI product page lists user guide 2024-06-25 | https://wiki.analog.com/resources/eval/user-guides/circuits-from-the-lab/eval-adxl355-pmdz | PMOD header pinout, VDD/DGND, INT1/INT2/DRDY availability |
| Not downloaded automatically | EVAL-ADXL355-PMDZ product page | Analog Devices | Current page captured 2026-07-14 | https://www.analog.com/en/resources/evaluation-hardware-and-software/evaluation-boards-kits/eval-adxl355-pmdz.html | Confirms low-noise, low-drift 3-axis accelerometer PMOD board and design resources |
| Not downloaded automatically | EVAL-ADXL355-PMDZ Mouser listing | Mouser / Analog Devices listing | Current page captured 2026-07-14 | https://www.mouser.com/en/ProductDetail/Analog-Devices/EVAL-ADXL355-PMDZ?qs=OpCP5WdiozdR9J91tlTHog%3D%3D | Confirms the exact purchased board named by the user |
| Not downloaded automatically | i.MX RT1060 Processor Reference Manual | NXP | Current manufacturer document | https://www.nxp.com/docs/en/reference-manual/IMXRT1060RM.pdf | Processor-level background only; firmware relies on Teensyduino abstractions |
| Not downloaded automatically | i.MX RT1060 Processor Data Sheet | NXP | Current manufacturer document | https://www.nxp.com/docs/en/data-sheet/IMXRT1060CEC.pdf | Electrical background only; board-level limits use PJRC documentation |
| Not downloaded automatically | Teensy SD library documentation | PJRC | Current page | https://www.pjrc.com/teensy/td_libs_SD.html | `SD.begin(BUILTIN_SDCARD)` and SD library behavior |
| `PJRC_Teensy_Time_RTC_Documentation.html` if available | Teensy Time library documentation | PJRC | Current page captured 2026-07-14 | https://www.pjrc.com/teensy/td_libs_Time.html | `time_t`, `setTime`, `now`, time validity semantics |

## Verified source facts used in this project

- Teensy 4.1 uses 3.3 V logic, its I/O pins are not 5 V tolerant, and normal digital output drive should be kept modest.
- Teensy 4.1 exposes three SPI ports, USB device serial appears as a COM port on Windows, and the built-in microSD socket uses `SD.begin(BUILTIN_SDCARD)` over native 4-bit SDIO.
- Teensy 4.1 has an RTC driven from a 32.768 kHz crystal; a 3 V coin cell on VBAT keeps date/time while main power is off.
- ADXL355 supports SPI and I2C, but this project uses SPI. ADI specifies SPI mode 0 and 100 kHz to 10 MHz SCLK.
- ADXL355 acceleration data is signed, two's-complement, 20-bit, left-justified in three data bytes per axis.
- ADXL355 typical sensitivities are 256000 LSB/g at +/-2 g, 128000 LSB/g at +/-4 g, and 64000 LSB/g at +/-8 g.
- ADXL355 range is controlled by register `0x2C`, filter/ODR by register `0x28`, power/standby by register `0x2D`, and identity registers are `0x00=0xAD`, `0x01=0x1D`, `0x02=0xED`.
- EVAL-ADXL355-PMDZ PMOD connector exposes CS, MOSI, MISO, SCLK, DGND, VDD, INT1, INT2, and DRDY.
