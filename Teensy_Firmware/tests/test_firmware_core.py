import binascii
import re
import unittest


STANDARD_GRAVITY = 9.80665


def decode_signed_20(byte2, byte1, byte0):
    raw = (byte2 << 12) | (byte1 << 4) | (byte0 >> 4)
    if raw & 0x80000:
        raw |= 0xFFF00000
    if raw & 0x80000000:
        raw -= 0x100000000
    return raw


def counts_per_g(range_g):
    return {2: 256000.0, 4: 128000.0, 8: 64000.0}[range_g]


def counts_to_mps2(counts, range_g, offset=0.0, scale=1.0):
    return ((counts - offset) * scale) / counts_per_g(range_g) * STANDARD_GRAVITY


def odr_code_for_rate(rate_hz):
    table = [
        (4000, 0x00),
        (2000, 0x01),
        (1000, 0x02),
        (500, 0x03),
        (250, 0x04),
        (125, 0x05),
        (62, 0x06),
        (31, 0x07),
        (15, 0x08),
        (8, 0x09),
        (4, 0x0A),
    ]
    for minimum, code in table:
        if rate_hz >= minimum:
            return code
    return 0x0A


def next_data_filename(existing_names):
    pattern = re.compile(r"^data_(\d+)\.csv$", re.IGNORECASE)
    indices = [int(match.group(1)) for name in existing_names if (match := pattern.fullmatch(name))]
    return f"Data_{max(indices) + 1 if indices else 0}.csv"


class FirmwareMathTests(unittest.TestCase):
    def test_signed_20_positive_and_negative(self):
        self.assertEqual(decode_signed_20(0x00, 0x00, 0x00), 0)
        self.assertEqual(decode_signed_20(0x7F, 0xFF, 0xF0), 524287)
        self.assertEqual(decode_signed_20(0xFF, 0xFF, 0xF0), -1)
        self.assertEqual(decode_signed_20(0x80, 0x00, 0x00), -524288)

    def test_counts_to_acceleration_scale(self):
        self.assertAlmostEqual(counts_to_mps2(256000, 2), STANDARD_GRAVITY, places=6)
        self.assertAlmostEqual(counts_to_mps2(128000, 4), STANDARD_GRAVITY, places=6)
        self.assertAlmostEqual(counts_to_mps2(64000, 8), STANDARD_GRAVITY, places=6)
        self.assertAlmostEqual(counts_to_mps2(0, 2, offset=1000), -1000 / 256000 * STANDARD_GRAVITY)

    def test_odr_code_mapping(self):
        self.assertEqual(odr_code_for_rate(500), 0x03)
        self.assertEqual(odr_code_for_rate(501), 0x03)
        self.assertEqual(odr_code_for_rate(499), 0x04)
        self.assertEqual(odr_code_for_rate(1), 0x0A)

    def test_crc32_known_vector(self):
        self.assertEqual(binascii.crc32(b"123456789") & 0xFFFFFFFF, 0xCBF43926)


class CsvSchemaTests(unittest.TestCase):
    def test_required_header_fields(self):
        header = (
            "record_type,session_id,timestamp_iso8601,elapsed_us,sample_number,"
            "x_counts,y_counts,z_counts,x_mps2,y_mps2,z_mps2,temperature_c,status_flags"
        )
        fields = header.split(",")
        for required in ("timestamp_iso8601", "x_mps2", "y_mps2", "z_mps2"):
            self.assertIn(required, fields)
        self.assertEqual(fields[0], "record_type")

    def test_new_acquisition_uses_highest_existing_index_plus_one(self):
        self.assertEqual(next_data_filename([]), "Data_0.csv")
        self.assertEqual(next_data_filename(["Data_0.csv", "Data_1.csv", "Data_3.csv"]), "Data_4.csv")
        self.assertEqual(next_data_filename(["notes.txt", "DATA_9.CSV"]), "Data_10.csv")


if __name__ == "__main__":
    unittest.main()
