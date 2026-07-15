from __future__ import annotations

import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Python_Control_Application" / "sample_data" / "SYNTHETIC_BUILDING_VIBRATION_TEST.csv"
G = 9.80665
COUNTS_PER_G = 256000.0


def counts_from_mps2(value: float) -> int:
    return round(value / G * COUNTS_PER_G)


def main() -> None:
    sample_rate_hz = 200.0
    duration_s = 20.0
    samples = int(sample_rate_hz * duration_s)
    session_id = 20260714
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
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
            ]
        )
        writer.writerow(
            [
                "SESSION_START",
                session_id,
                "2026-07-14T12:00:00Z",
                0,
                0,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "synthetic=true;rate_hz=200;range_g=2;known_peaks_x=3,12.5,60;known_peaks_y=5,20;known_peaks_z=3,25",
            ]
        )

        for i in range(samples):
            t = i / sample_rate_hz
            x = (
                0.080 * math.sin(2 * math.pi * 3.0 * t)
                + 0.035 * math.sin(2 * math.pi * 12.5 * t)
                + 0.012 * math.sin(2 * math.pi * 60.0 * t)
            )
            y = 0.060 * math.sin(2 * math.pi * 5.0 * t + 0.4) + 0.020 * math.sin(2 * math.pi * 20.0 * t)
            z_dynamic = 0.050 * math.sin(2 * math.pi * 3.0 * t + 0.2) + 0.025 * math.sin(2 * math.pi * 25.0 * t)
            z = G + z_dynamic
            writer.writerow(
                [
                    "DATA",
                    session_id,
                    "2026-07-14T12:00:00Z",
                    round(t * 1_000_000),
                    i,
                    counts_from_mps2(x),
                    counts_from_mps2(y),
                    counts_from_mps2(z),
                    f"{x:.9f}",
                    f"{y:.9f}",
                    f"{z:.9f}",
                    "25.0",
                    "0x00000001",
                ]
            )

        writer.writerow(
            [
                "SESSION_END",
                session_id,
                "2026-07-14T12:00:20Z",
                round(duration_s * 1_000_000),
                samples,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                f"samples={samples};dropped=0;overruns=0",
            ]
        )
    print(OUTPUT)


if __name__ == "__main__":
    main()
