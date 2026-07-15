import csv
import math
import pathlib
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from building_vibration_analyzer.csv_log import load_sessions
from building_vibration_analyzer.excel_export import export_fft_workbook


class ExcelExportTests(unittest.TestCase):
    def test_export_fft_workbook_contains_expected_sheets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            csv_path = tmp_path / "synthetic.csv"
            xlsx_path = tmp_path / "export.xlsx"
            self._write_synthetic_csv(csv_path)
            session = load_sessions(csv_path)[0]

            export_fft_workbook(session, xlsx_path, window="boxcar")

            self.assertTrue(xlsx_path.exists())
            with zipfile.ZipFile(xlsx_path) as zf:
                names = set(zf.namelist())
                self.assertIn("xl/workbook.xml", names)
                self.assertIn("xl/worksheets/sheet1.xml", names)
                self.assertIn("xl/worksheets/sheet3.xml", names)
                workbook_xml = zf.read("xl/workbook.xml").decode("utf-8")
                self.assertIn("Summary", workbook_xml)
                self.assertIn("FFT_Amplitude", workbook_xml)
                fft_xml = zf.read("xl/worksheets/sheet3.xml").decode("utf-8")
                self.assertIn("frequency_hz", fft_xml)
                self.assertIn("x_fft_mps2", fft_xml)

    def test_windowed_export_can_include_dynamic_resultant(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            csv_path = tmp_path / "synthetic.csv"
            xlsx_path = tmp_path / "export_windowed.xlsx"
            self._write_synthetic_csv(csv_path)
            session = load_sessions(csv_path)[0]

            export_fft_workbook(session, xlsx_path, window="boxcar", time_window=(1.0, 3.0), axes=("x", "r"))

            with zipfile.ZipFile(xlsx_path) as zf:
                summary_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
                fft_xml = zf.read("xl/worksheets/sheet3.xml").decode("utf-8")
                self.assertIn("Exported samples", summary_xml)
                self.assertIn("Analysis start", summary_xml)
                self.assertIn("r_fft_mps2", fft_xml)
                self.assertNotIn("z_fft_mps2", fft_xml)

    @staticmethod
    def _write_synthetic_csv(path):
        fs = 128.0
        rows = [
            [
                "record_type",
                "session_id",
                "timestamp_iso8601",
                "elapsed_us",
                "sample_number",
                "x_counts",
                "y_counts",
                "z_counts",
                "x_mps2",
                "y_mps2",
                "z_mps2",
                "temperature_c",
                "status_flags",
            ],
            ["SESSION_START", "99", "2026-07-14T12:00:00Z", 0, 0, "", "", "", "", "", "", "", "rate_hz=128"],
        ]
        for i in range(512):
            t = i / fs
            x = 0.2 * math.sin(2 * math.pi * 8.0 * t)
            y = 0.1 * math.sin(2 * math.pi * 16.0 * t)
            z = 9.80665 + 0.05 * math.sin(2 * math.pi * 24.0 * t)
            rows.append(["DATA", "99", "2026-07-14T12:00:00Z", int(t * 1_000_000), i, 0, 0, 0, x, y, z, 25.0, "0x1"])
        rows.append(["SESSION_END", "99", "2026-07-14T12:00:04Z", 4_000_000, 512, "", "", "", "", "", "", "", "samples=512"])
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)


if __name__ == "__main__":
    unittest.main()
