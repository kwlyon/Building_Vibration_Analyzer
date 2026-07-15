import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from building_vibration_analyzer.csv_log import export_session_csv, load_sessions, select_samples_by_elapsed


SAMPLE_CSV = """record_type,session_id,timestamp_iso8601,elapsed_us,sample_number,x_counts,y_counts,z_counts,x_mps2,y_mps2,z_mps2,temperature_c,status_flags
SESSION_START,7,2026-07-14T12:00:00Z,0,0,,,,,,,,rate_hz=100;range_g=2
DATA,7,2026-07-14T12:00:00Z,0,0,0,0,0,0,0,0,25,0x1
DATA,7,2026-07-14T12:00:00Z,10000,1,1,2,3,0.1,0.2,0.3,25,0x1
DATA,7,2026-07-14T12:00:00Z,bad,2,1,2,3,0.1,0.2,0.3,25,0x1
FAULT,7,RTC_INVALID,0,0,,,,,,,,sensor_error
SESSION_END,7,2026-07-14T12:00:01Z,20000,2,,,,,,,,samples=2
"""


class CsvLogTests(unittest.TestCase):
    def test_load_sessions_skips_corrupt_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "log.csv"
            path.write_text(SAMPLE_CSV, encoding="utf-8")
            sessions = load_sessions(path)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].session_id, "7")
            self.assertEqual(len(sessions[0].samples), 2)
            self.assertEqual(len(sessions[0].faults), 1)
            self.assertAlmostEqual(sessions[0].sample_rate_hz, 100.0)

    def test_export_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "source.csv"
            dest = pathlib.Path(tmp) / "export.csv"
            source.write_text(SAMPLE_CSV, encoding="utf-8")
            session = load_sessions(source)[0]
            export_session_csv(session, dest)
            self.assertIn("x_mps2", dest.read_text(encoding="utf-8"))

    def test_select_samples_by_elapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "log.csv"
            path.write_text(SAMPLE_CSV, encoding="utf-8")
            session = load_sessions(path)[0]
            selected = select_samples_by_elapsed(session, 0.005, 0.02)
            self.assertEqual([sample.sample_number for sample in selected], [1])


if __name__ == "__main__":
    unittest.main()
