import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from building_vibration_analyzer.protocol import (
    build_set_range_command,
    build_set_rate_command,
    build_set_rtc_command,
    chunk_crc32,
    parse_response_line,
    validate_chunk,
)


class ProtocolTests(unittest.TestCase):
    def test_parse_ok_fields(self):
        response = parse_response_line('OK STATUS firmware=0.1.0 hardware="Teensy 4.1" recording=0')
        self.assertTrue(response.ok)
        self.assertEqual(response.command, "STATUS")
        self.assertEqual(response.fields["firmware"], "0.1.0")
        self.assertEqual(response.fields["hardware"], "Teensy 4.1")

    def test_parse_error(self):
        response = parse_response_line("ERR START sensor_not_found")
        self.assertFalse(response.ok)
        self.assertEqual(response.code, "START")
        self.assertEqual(response.message, "sensor_not_found")

    def test_command_validation(self):
        self.assertEqual(build_set_rate_command(500), "SET RATE 500")
        self.assertEqual(build_set_range_command(8), "SET RANGE 8")
        self.assertEqual(build_set_rtc_command("2026-07-14T12:00:00Z"), "SET RTC 2026-07-14T12:00:00Z")
        with self.assertRaises(ValueError):
            build_set_range_command(16)

    def test_chunk_crc(self):
        data = b"abc123"
        crc = chunk_crc32(data)
        self.assertTrue(validate_chunk(data, crc))
        self.assertFalse(validate_chunk(data + b"x", crc))


if __name__ == "__main__":
    unittest.main()
