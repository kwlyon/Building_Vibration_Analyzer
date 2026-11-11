from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks


WORK_DIR = Path(
    r"C:\Users\kwlyon\.codex\visualizations\2026\07\24"
    r"\019f923a-5419-7092-902a-9a4aa6822fb4\manual_report_work"
)
INPUT_JSON = WORK_DIR / "manual_spectra.json"
OUTPUT_JSON = WORK_DIR / "analysis_results.json"

LOW_CUT_HZ = 2.0
PRINCIPAL_PLANT_LINES_HZ = [
    29.8149712212212,
    98.731544044044,
    101.664164164164,
    119.993039914915,
]

FLOOR_LOCATIONS = {
    "PHYS_TITAN_FLOOR": "Titan Lab",
    "PHYS_245_Floor": "PHYS 245",
    "PHYS_244_Floor": "PHYS 244",
    "PHYS_111_Floor": "PHYS 111",
    "PHYS_Herzog_Floor": "Herzog Lab",
}

TABLE_COMPARISONS = [
    ("PHYS_Herzog_Floor", "PHYS_Herzog_Optical_Table", "Herzog optical table", False),
    ("PHYS_111_Floor", "PHYS_111_Far_Optical_Table", "PHYS 111 far optical table", False),
    (
        "PHYS_111_Floor",
        "PHYS_111_Near_Door_Optical_Table",
        "PHYS 111 near-door optical table",
        False,
    ),
    ("PHYS_244_Floor", "PHYS_244_Rolling_Table", "PHYS 244 rolling table", False),
    ("PHYS_245_Floor", "PHYS_245_Unfloated_Table", "PHYS 245 unfloated table", False),
    ("PHYS_245_Floor", "PHYS_245_Floated_Table", "PHYS 245 floated table", True),
]


def load_spectra() -> dict[str, dict[str, np.ndarray]]:
    raw = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    result: dict[str, dict[str, np.ndarray]] = {}
    for entry in raw["spectra"]:
        result[entry["location"]] = {
            "frequency": np.asarray(entry["frequencyHz"], dtype=float),
            "asd": np.asarray(entry["asd"], dtype=float),
            "metadata": entry["metadata"],
        }
    return result


def nearest_value(run: dict[str, np.ndarray], frequency_hz: float) -> tuple[float, float]:
    index = int(np.argmin(np.abs(run["frequency"] - frequency_hz)))
    return float(run["frequency"][index]), float(run["asd"][index])


def integrated_rms(
    run: dict[str, np.ndarray],
    low_hz: float = LOW_CUT_HZ,
    high_hz: float = 250.1,
    excluded_centers: list[float] | None = None,
    exclusion_half_width_hz: float = 1.0,
) -> float:
    frequency = run["frequency"]
    asd = run["asd"]
    mask = (frequency >= low_hz) & (frequency < high_hz)
    for center in excluded_centers or []:
        mask &= np.abs(frequency - center) > exclusion_half_width_hz
    df = float(np.median(np.diff(frequency)))
    return float(np.sqrt(np.sum(np.square(asd[mask])) * df))


def detect_peaks(run: dict[str, np.ndarray], high_hz: float = 200.0) -> list[dict[str, float]]:
    frequency = run["frequency"]
    asd = run["asd"]
    valid = (frequency >= LOW_CUT_HZ) & (frequency <= high_hz)
    indices = np.flatnonzero(valid)
    log_asd = np.log10(np.maximum(asd, np.finfo(float).tiny))
    candidates, properties = find_peaks(log_asd, prominence=0.10, distance=2)
    baseline = median_filter(asd, size=21, mode="nearest")
    peaks: list[dict[str, float]] = []
    for index, prominence in zip(candidates, properties["prominences"]):
        if index not in indices:
            continue
        ratio = float(asd[index] / max(baseline[index], np.finfo(float).tiny))
        if ratio < 1.25:
            continue
        peaks.append(
            {
                "frequency_hz": float(frequency[index]),
                "asd": float(asd[index]),
                "ratio_to_local_baseline": ratio,
                "log10_prominence": float(prominence),
            }
        )
    return sorted(peaks, key=lambda item: item["asd"], reverse=True)


def match_peaks(
    left: list[dict[str, float]],
    right: list[dict[str, float]],
    tolerance_hz: float = 0.75,
) -> list[dict[str, float]]:
    matches: list[dict[str, float]] = []
    for first in left:
        candidates = [
            second
            for second in right
            if abs(second["frequency_hz"] - first["frequency_hz"]) <= tolerance_hz
        ]
        if not candidates:
            continue
        second = min(
            candidates,
            key=lambda item: abs(item["frequency_hz"] - first["frequency_hz"]),
        )
        matches.append(
            {
                "frequency_hz": 0.5
                * (first["frequency_hz"] + second["frequency_hz"]),
                "pipe_asd": first["asd"],
                "sidewalk_asd": second["asd"],
                "pipe_ratio": first["ratio_to_local_baseline"],
                "sidewalk_ratio": second["ratio_to_local_baseline"],
                "score": math.sqrt(
                    first["ratio_to_local_baseline"]
                    * second["ratio_to_local_baseline"]
                ),
            }
        )
    return sorted(matches, key=lambda item: item["score"], reverse=True)


def main() -> None:
    spectra = load_spectra()
    grids = [run["frequency"] for run in spectra.values()]
    reference = grids[0]
    if not all(len(grid) == 513 for grid in grids):
        raise ValueError("One or more manual spectra do not contain 513 ASD bins.")
    frequency_steps = [float(np.median(np.diff(grid))) for grid in grids]

    pipe_peaks = detect_peaks(spectra["Pipe_From_Heating_Plant"])
    sidewalk_peaks = detect_peaks(spectra["Sidewalk_between_Heating_and_Physics"])
    common = match_peaks(pipe_peaks, sidewalk_peaks)

    comparison_locations = {
        "Pipe": "Pipe_From_Heating_Plant",
        "Sidewalk": "Sidewalk_between_Heating_and_Physics",
        "Greek theater": "Greek_Theater_Top_Stair",
        "Courtyard": "Courtyard_between_Mullens_Union",
        "Herzog floor": "PHYS_Herzog_Floor",
        "Titan floor": "PHYS_TITAN_FLOOR",
        "PHYS 245 floor": "PHYS_245_Floor",
        "PHYS 244 floor": "PHYS_244_Floor",
        "PHYS 111 floor": "PHYS_111_Floor",
    }

    candidate_rows: list[dict[str, object]] = []
    for candidate in common[:12]:
        center = candidate["frequency_hz"]
        row: dict[str, object] = {
            "frequency_hz": center,
            "score": candidate["score"],
            "pipe_ratio": candidate["pipe_ratio"],
            "sidewalk_ratio": candidate["sidewalk_ratio"],
        }
        for label, location in comparison_locations.items():
            actual_frequency, amplitude = nearest_value(spectra[location], center)
            row[label] = {
                "frequency_hz": actual_frequency,
                "asd": amplitude,
            }
        candidate_rows.append(row)

    plant_centers = [
        row["frequency_hz"]
        for row in candidate_rows
        if row["frequency_hz"] <= 160.0
        and row["pipe_ratio"] >= 1.5
        and row["sidewalk_ratio"] >= 1.25
    ][:8]

    floor_metrics = []
    for location, room in FLOOR_LOCATIONS.items():
        run = spectra[location]
        frequency_30, amplitude_30 = nearest_value(run, 30.0)
        floor_metrics.append(
            {
                "room": room,
                "location": location,
                "frequency_30_hz": frequency_30,
                "asd_30": amplitude_30,
                "rms_2_250_all_lines": integrated_rms(run),
                "rms_2_250_excluding_principal_plant_lines": integrated_rms(
                    run,
                    excluded_centers=PRINCIPAL_PLANT_LINES_HZ,
                    exclusion_half_width_hz=1.0,
                ),
                "rms_2_20": integrated_rms(run, 2.0, 20.0),
                "rms_20_50": integrated_rms(run, 20.0, 50.0),
            }
        )

    table_metrics = []
    for floor_name, table_name, label, floated in TABLE_COMPARISONS:
        floor_run = spectra[floor_name]
        table_run = spectra[table_name]
        frequency_30, floor_30 = nearest_value(floor_run, 30.0)
        _, table_30 = nearest_value(table_run, 30.0)
        ratio = table_30 / floor_30
        table_metrics.append(
            {
                "label": label,
                "floated": floated,
                "floor_location": floor_name,
                "table_location": table_name,
                "frequency_hz": frequency_30,
                "floor_asd": floor_30,
                "table_asd": table_30,
                "table_to_floor_ratio": ratio,
                "attenuation_db": 20.0 * math.log10(ratio),
            }
        )

    selected_30_locations = [
        "Pipe_From_Heating_Plant",
        "Sidewalk_between_Heating_and_Physics",
        "Greek_Theater_Top_Stair",
        "Courtyard_between_Mullens_Union",
        "PHYS_Herzog_Floor",
        "PHYS_TITAN_FLOOR",
        "PHYS_245_Floor",
    ]
    thirty_hz = {}
    for location in selected_30_locations:
        frequency_30, amplitude_30 = nearest_value(spectra[location], 30.0)
        thirty_hz[location] = {
            "frequency_hz": frequency_30,
            "asd": amplitude_30,
        }

    output = {
        "common_frequency_bins": len(reference),
        "frequency_step_hz_range": [min(frequency_steps), max(frequency_steps)],
        "pipe_top_peaks": pipe_peaks[:20],
        "sidewalk_top_peaks": sidewalk_peaks[:20],
        "plant_peak_candidates": candidate_rows,
        "selected_plant_centers_hz": plant_centers,
        "floor_metrics": floor_metrics,
        "table_metrics": table_metrics,
        "thirty_hz_comparison": thirty_hz,
    }
    OUTPUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("COMMON PIPE/SIDEWALK PEAKS")
    for row in candidate_rows[:12]:
        print(
            f"{row['frequency_hz']:8.3f} Hz  "
            f"score={row['score']:6.2f}  "
            f"pipe={row['Pipe']['asd']:.6g}  "
            f"sidewalk={row['Sidewalk']['asd']:.6g}  "
            f"Greek={row['Greek theater']['asd']:.6g}  "
            f"courtyard={row['Courtyard']['asd']:.6g}"
        )

    print("\nFLOOR METRICS")
    for row in sorted(
        floor_metrics,
        key=lambda item: item["rms_2_250_excluding_principal_plant_lines"],
    ):
        print(
            f"{row['room']:12s} "
            f"30Hz={row['asd_30']:.6g}  "
            f"RMS={row['rms_2_250_all_lines']:.6g}  "
            f"RMS-no-principal-plant-lines="
            f"{row['rms_2_250_excluding_principal_plant_lines']:.6g}"
        )

    print("\nTABLE PERFORMANCE AT 29.815 HZ")
    for row in table_metrics:
        print(
            f"{row['label']:31s} "
            f"ratio={row['table_to_floor_ratio']:.3f}  "
            f"{row['attenuation_db']:+.1f} dB"
        )


if __name__ == "__main__":
    main()
