#!/usr/bin/env python
"""Short, peak-centered analysis of FinalReportData.xlsx.

Only the numerical frequency and acceleration-ASD columns are used.  The
workbook's precomputed peak list is deliberately ignored.  The source workbook
is opened read-only and is never modified.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from openpyxl import load_workbook
from scipy.ndimage import median_filter
from scipy.signal import find_peaks


LOW_CUT_HZ = 2.0
MAINS_LOW_HZ = 58.0
MAINS_HIGH_HZ = 62.0
FREEZER_MATCH_TOLERANCE_HZ = 1.6
FREEZER_REPLACEMENT_HALF_WIDTH_HZ = 1.5

ROOM_ORDER = ["Titan Lab", "PHYS 111", "Herzog Lab", "PHYS 244", "PHYS 245"]
REPRESENTATIVE_LOCATION = {
    "Titan Lab": "Lab Floor (carpet hole)",
    "PHYS 111": "Floor",
    "Herzog Lab": "Floor",
    "PHYS 244": "Floor",
    "PHYS 245": "Floor",
}
COLORS = {
    "Titan Lab": "#0072B2",
    "PHYS 111": "#E69F00",
    "Herzog Lab": "#D55E00",
    "PHYS 244": "#009E73",
    "PHYS 245": "#CC79A7",
}
BANDS = [
    ("2-10 Hz", 2.0, 10.0),
    ("10-20 Hz", 10.0, 20.0),
    ("20-50 Hz", 20.0, 50.0),
    ("62-100 Hz", 62.0, 100.0),
    ("100-250 Hz", 100.0, 250.1),
]
TABLE_COMPARISONS = [
    ("PHYS 245", "Floor", "Floated Table (AFM)", "PHYS 245: floated"),
    (
        "PHYS 245",
        "Floor",
        "Unfloated Table (Oliver Laser)",
        "PHYS 245: unfloated",
    ),
    ("Herzog Lab", "Floor", "Optical Table", "Herzog: optical table"),
    ("PHYS 111", "Floor", "Optical Table Wall", "PHYS 111: table at wall"),
]


@dataclass
class SpectrumRun:
    room: str
    location: str
    frequency_hz: np.ndarray
    asd: np.ndarray

    @property
    def run_id(self) -> str:
        return f"{self.room} - {self.location}"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def parse_workbook(path: Path) -> list[SpectrumRun]:
    """Detect numerical spectrum blocks from the actual data-column headers."""
    workbook = load_workbook(path, data_only=True, read_only=False)
    runs: list[SpectrumRun] = []
    for sheet in workbook.worksheets:
        for label_col in range(1, sheet.max_column - 4):
            if (
                sheet.cell(1, label_col + 4).value == "frequency_hz"
                and sheet.cell(1, label_col + 5).value
                == "r_spectral_asd_mps2_per_sqrt_hz"
                and sheet.cell(1, label_col).value
            ):
                frequency: list[float] = []
                amplitude: list[float] = []
                for row in range(2, sheet.max_row + 1):
                    f_value = sheet.cell(row, label_col + 4).value
                    a_value = sheet.cell(row, label_col + 5).value
                    if isinstance(f_value, (int, float)) and isinstance(
                        a_value, (int, float)
                    ):
                        frequency.append(float(f_value))
                        amplitude.append(float(a_value))
                if len(frequency) >= 10:
                    order = np.argsort(frequency)
                    runs.append(
                        SpectrumRun(
                            room=sheet.title,
                            location=str(sheet.cell(1, label_col).value).strip(),
                            frequency_hz=np.asarray(frequency)[order],
                            asd=np.asarray(amplitude)[order],
                        )
                    )
    workbook.close()
    return runs


def find_run(runs: list[SpectrumRun], room: str, location: str) -> SpectrumRun:
    for run in runs:
        if run.room == room and run.location == location:
            return run
    raise KeyError(f"Missing run: {room} / {location}")


def analysis_mask(frequency: np.ndarray, low: float = LOW_CUT_HZ, high: float = 250.1):
    return (
        (frequency >= low)
        & (frequency < high)
        & ~((frequency >= MAINS_LOW_HZ) & (frequency <= MAINS_HIGH_HZ))
    )


def rms_from_asd(
    frequency: np.ndarray,
    asd: np.ndarray,
    low: float = LOW_CUT_HZ,
    high: float = 250.1,
) -> float:
    mask = analysis_mask(frequency, low, high)
    if not np.any(mask):
        return float("nan")
    df = float(np.median(np.diff(frequency)))
    return float(np.sqrt(np.sum(np.square(asd[mask])) * df))


def broadband_baseline(asd: np.ndarray) -> np.ndarray:
    """Median-filter log ASD over about 10 Hz to suppress narrow lines."""
    safe = np.clip(asd, np.finfo(float).tiny, None)
    return np.power(10.0, median_filter(np.log10(safe), size=21, mode="nearest"))


def detect_peaks(run: SpectrumRun, max_peaks: int = 20) -> pd.DataFrame:
    """Detect peaks from the unsmoothed numerical ASD; ignore workbook peak tables."""
    f = run.frequency_hz
    a = run.asd
    valid = (f >= LOW_CUT_HZ) & (f <= 250.1) & np.isfinite(a) & (a > 0)
    fv = f[valid]
    av = a[valid]
    log_a = np.log10(av)
    indices, properties = find_peaks(log_a, prominence=0.10, distance=2)
    baseline = broadband_baseline(av)
    if not len(indices):
        return pd.DataFrame(
            columns=[
                "room",
                "location",
                "frequency_hz",
                "asd_mps2_per_sqrt_hz",
                "local_baseline_asd",
                "peak_to_baseline_ratio",
                "log10_prominence",
            ]
        )
    frame = pd.DataFrame(
        {
            "room": run.room,
            "location": run.location,
            "frequency_hz": fv[indices],
            "asd_mps2_per_sqrt_hz": av[indices],
            "local_baseline_asd": baseline[indices],
            "peak_to_baseline_ratio": av[indices] / baseline[indices],
            "log10_prominence": properties["prominences"],
        }
    )
    frame = frame[
        ~frame["frequency_hz"].between(MAINS_LOW_HZ, MAINS_HIGH_HZ)
        & (frame["peak_to_baseline_ratio"] >= 1.30)
    ]
    return (
        frame.sort_values("asd_mps2_per_sqrt_hz", ascending=False)
        .head(max_peaks)
        .reset_index(drop=True)
    )


def metrics_for(run: SpectrumRun, asd: np.ndarray | None = None) -> dict:
    spectrum = run.asd if asd is None else asd
    mask = analysis_mask(run.frequency_hz)
    baseline = broadband_baseline(spectrum)
    temporary = SpectrumRun(run.room, run.location, run.frequency_hz, spectrum)
    peaks = detect_peaks(temporary, 40)
    if peaks.empty:
        peak_frequency = float("nan")
        peak_asd = float("nan")
        peak_ratio = float("nan")
    else:
        largest = peaks.iloc[0]
        peak_frequency = float(largest["frequency_hz"])
        peak_asd = float(largest["asd_mps2_per_sqrt_hz"])
        peak_ratio = float(largest["peak_to_baseline_ratio"])
    mains_mask = (run.frequency_hz >= MAINS_LOW_HZ) & (
        run.frequency_hz <= MAINS_HIGH_HZ
    )
    return {
        "room": run.room,
        "location": run.location,
        "raw_rms_2_250_ex58_62_mps2": rms_from_asd(
            run.frequency_hz, spectrum
        ),
        "broadband_rms_estimate_mps2": rms_from_asd(
            run.frequency_hz, baseline
        ),
        "median_asd_ex58_62_mps2_per_sqrthz": float(np.median(spectrum[mask])),
        "largest_peak_frequency_hz": peak_frequency,
        "largest_peak_asd_mps2_per_sqrthz": peak_asd,
        "largest_peak_to_baseline_ratio": peak_ratio,
        "prominent_peak_count": int(
            np.sum(peaks["peak_to_baseline_ratio"].to_numpy() >= 1.5)
        ),
        "max_58_62_asd_mps2_per_sqrthz": float(np.max(spectrum[mains_mask])),
    }


def match_freezer_signature(
    target: SpectrumRun,
    freezer: SpectrumRun,
    distant_floors: list[SpectrumRun],
) -> pd.DataFrame:
    target_peaks = detect_peaks(target, 30)
    freezer_peaks = detect_peaks(freezer, 40)
    distant_peaks = [detect_peaks(run, 30) for run in distant_floors]
    rows: list[dict] = []
    for target_peak in target_peaks.itertuples():
        differences = np.abs(
            freezer_peaks["frequency_hz"].to_numpy(dtype=float)
            - float(target_peak.frequency_hz)
        )
        if not len(differences) or float(np.min(differences)) > FREEZER_MATCH_TOLERANCE_HZ:
            continue
        freezer_peak = freezer_peaks.iloc[int(np.argmin(differences))]
        if float(freezer_peak["peak_to_baseline_ratio"]) < 3.0:
            continue
        if float(target_peak.peak_to_baseline_ratio) < 1.8:
            continue
        broad_hits = 0
        for peaks in distant_peaks:
            if not peaks.empty and np.any(
                np.abs(peaks["frequency_hz"].to_numpy() - target_peak.frequency_hz)
                <= 1.0
            ):
                broad_hits += 1
        likely_freezer_specific = broad_hits < 2
        rows.append(
            {
                "room": target.room,
                "location": target.location,
                "room_peak_frequency_hz": float(target_peak.frequency_hz),
                "room_peak_asd_mps2_per_sqrt_hz": float(
                    target_peak.asd_mps2_per_sqrt_hz
                ),
                "freezer_peak_frequency_hz": float(freezer_peak["frequency_hz"]),
                "freezer_peak_asd_mps2_per_sqrt_hz": float(
                    freezer_peak["asd_mps2_per_sqrt_hz"]
                ),
                "room_peak_to_baseline_ratio": float(
                    target_peak.peak_to_baseline_ratio
                ),
                "freezer_peak_to_baseline_ratio": float(
                    freezer_peak["peak_to_baseline_ratio"]
                ),
                "distant_floor_matches": broad_hits,
                "classification": (
                    "likely freezer-related local line"
                    if likely_freezer_specific
                    else "broadly shared line; retained"
                ),
                "removed_from_adjusted_floor": likely_freezer_specific,
            }
        )
    return pd.DataFrame(rows)


def replace_narrow_lines(
    run: SpectrumRun, matches: pd.DataFrame
) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Replace selected narrow lines by log-linear local interpolation."""
    adjusted = run.asd.copy()
    replaced: list[tuple[float, float]] = []
    if matches.empty:
        return adjusted, replaced
    centers = matches.loc[
        matches["removed_from_adjusted_floor"], "room_peak_frequency_hz"
    ].to_numpy(dtype=float)
    for center in centers:
        band = np.abs(run.frequency_hz - center) <= FREEZER_REPLACEMENT_HALF_WIDTH_HZ
        left = np.where(
            run.frequency_hz < center - FREEZER_REPLACEMENT_HALF_WIDTH_HZ
        )[0]
        right = np.where(
            run.frequency_hz > center + FREEZER_REPLACEMENT_HALF_WIDTH_HZ
        )[0]
        if not np.any(band) or not len(left) or not len(right):
            continue
        left_index = int(left[-1])
        right_index = int(right[0])
        adjusted[band] = np.power(
            10.0,
            np.interp(
                run.frequency_hz[band],
                [run.frequency_hz[left_index], run.frequency_hz[right_index]],
                [np.log10(run.asd[left_index]), np.log10(run.asd[right_index])],
            ),
        )
        replaced.append(
            (
                float(run.frequency_hz[band][0]),
                float(run.frequency_hz[band][-1]),
            )
        )
    return adjusted, replaced


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.titlesize": 13,
            "savefig.bbox": "tight",
        }
    )


def shade_mains(axis: plt.Axes) -> None:
    axis.axvspan(MAINS_LOW_HZ, MAINS_HIGH_HZ, color="#888888", alpha=0.15, lw=0)


def save_figure(figure: plt.Figure, directory: Path, name: str) -> None:
    figure.savefig(directory / f"{name}.pdf")
    figure.savefig(directory / f"{name}.png", dpi=240)
    plt.close(figure)


def plot_representative_floors(runs: list[SpectrumRun], directory: Path) -> None:
    representative = [
        find_run(runs, room, REPRESENTATIVE_LOCATION[room]) for room in ROOM_ORDER
    ]
    positive = np.concatenate([run.asd[run.asd > 0] for run in representative])
    ymin = 10 ** math.floor(math.log10(float(np.percentile(positive, 0.5))))
    ymax = 10 ** math.ceil(math.log10(float(np.max(positive))))
    figure, axes = plt.subplots(3, 2, figsize=(7.2, 8.7), sharex=True, sharey=True)
    for axis, run in zip(axes.flat, representative):
        axis.plot(run.frequency_hz, run.asd, lw=0.8, color=COLORS[run.room])
        shade_mains(axis)
        axis.set_title(f"{run.room}: {run.location}")
        axis.set_yscale("log")
        axis.set_xlim(0, 250)
        axis.set_ylim(ymin, ymax)
        axis.grid(True, which="both", alpha=0.18)
    axes.flat[-1].axis("off")
    figure.supxlabel("Frequency (Hz)")
    figure.supylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)")
    figure.suptitle("Representative floor spectrum for each measured laboratory")
    figure.tight_layout(rect=[0.04, 0.03, 1, 0.97])
    save_figure(figure, directory, "representative_spectra_by_room")


def plot_titan_comparison(runs: list[SpectrumRun], directory: Path) -> None:
    representative = [
        find_run(runs, room, REPRESENTATIVE_LOCATION[room]) for room in ROOM_ORDER
    ]
    titan = find_run(runs, "Titan Lab", "Lab Floor (carpet hole)")
    figure, axis = plt.subplots(figsize=(7.2, 4.4))
    for run in representative:
        axis.plot(
            run.frequency_hz,
            run.asd,
            label=run.room,
            color=COLORS[run.room],
            lw=1.7 if run is titan else 0.8,
            alpha=1.0 if run is titan else 0.65,
        )
    shade_mains(axis)
    axis.set_xlim(0, 100)
    axis.set_yscale("log")
    axis.set_xlabel("Frequency (Hz)")
    axis.set_ylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)")
    axis.set_title("Titan has the cleanest broadband spectrum aside from a 29.8 Hz line")
    axis.grid(True, which="both", alpha=0.2)
    axis.legend(ncol=2)
    save_figure(figure, directory, "titan_vs_other_floors")


def plot_within_herzog(runs: list[SpectrumRun], directory: Path) -> None:
    figure, axis = plt.subplots(figsize=(7.2, 4.3))
    for run in [run for run in runs if run.room == "Herzog Lab"]:
        axis.plot(run.frequency_hz, run.asd, lw=0.9, label=run.location)
    shade_mains(axis)
    axis.set_xlim(0, 160)
    axis.set_yscale("log")
    axis.set_xlabel("Frequency (Hz)")
    axis.set_ylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)")
    axis.set_title("Herzog Lab: comparison of measured locations")
    axis.grid(True, which="both", alpha=0.2)
    axis.legend()
    save_figure(figure, directory, "within_herzog_lab")


def plot_freezer_adjustment(
    freezer: SpectrumRun,
    herzog: SpectrumRun,
    phys111: SpectrumRun,
    adjusted: dict[str, np.ndarray],
    matches: pd.DataFrame,
    directory: Path,
) -> None:
    centers = sorted(
        matches.loc[
            matches["removed_from_adjusted_floor"], "room_peak_frequency_hz"
        ].unique()
    )
    figure, axes = plt.subplots(2, 1, figsize=(7.2, 6.6))
    axes[0].plot(freezer.frequency_hz, freezer.asd, color="#222222", label="Freezer top")
    axes[0].plot(
        herzog.frequency_hz,
        herzog.asd,
        color=COLORS["Herzog Lab"],
        label="Herzog floor",
    )
    axes[0].plot(
        phys111.frequency_hz,
        phys111.asd,
        color=COLORS["PHYS 111"],
        label="PHYS 111 floor",
    )
    axes[0].set_title("Freezer reference and neighboring floor spectra")
    axes[0].set_yscale("log")
    axes[0].set_xlim(0, 160)
    axes[0].legend()

    for run, label, color in [
        (herzog, "Herzog", COLORS["Herzog Lab"]),
        (phys111, "PHYS 111", COLORS["PHYS 111"]),
    ]:
        axes[1].plot(
            run.frequency_hz,
            run.asd,
            color=color,
            lw=1.0,
            label=f"{label} measured",
        )
        axes[1].plot(
            run.frequency_hz,
            adjusted[run.room],
            color=color,
            lw=1.1,
            ls="--",
            label=f"{label} freezer-adjusted",
        )
    axes[1].set_title("Conservative narrow-line replacement")
    axes[1].set_yscale("log")
    axes[1].set_xlim(75, 135)
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].legend(ncol=2)
    for axis in axes:
        shade_mains(axis)
        axis.set_ylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)")
        axis.grid(True, which="both", alpha=0.2)
        for center in centers:
            axis.axvspan(
                center - FREEZER_REPLACEMENT_HALF_WIDTH_HZ,
                center + FREEZER_REPLACEMENT_HALF_WIDTH_HZ,
                color="#009E73",
                alpha=0.10,
                lw=0,
            )
    figure.tight_layout()
    save_figure(figure, directory, "freezer_informed_adjustment")


def plot_optical_table_performance(
    runs: list[SpectrumRun], directory: Path
) -> pd.DataFrame:
    rows: list[dict] = []
    labels = ["2-250 Hz"] + [label for label, _, _ in BANDS]
    for room, floor_location, table_location, label in TABLE_COMPARISONS:
        floor = find_run(runs, room, floor_location)
        table = find_run(runs, room, table_location)
        comparisons = [("2-250 Hz", LOW_CUT_HZ, 250.1)] + BANDS
        for band_label, low, high in comparisons:
            floor_rms = rms_from_asd(floor.frequency_hz, floor.asd, low, high)
            table_rms = rms_from_asd(table.frequency_hz, table.asd, low, high)
            rows.append(
                {
                    "comparison": label,
                    "band": band_label,
                    "change_db": 20.0 * math.log10(table_rms / floor_rms),
                }
            )
    frame = pd.DataFrame(rows)
    pivot = frame.pivot(index="comparison", columns="band", values="change_db")
    pivot = pivot[labels]
    values = pivot.to_numpy()
    limit = max(6.0, float(np.nanmax(np.abs(values))))
    figure, axis = plt.subplots(figsize=(7.2, 3.8))
    image = axis.imshow(
        values,
        aspect="auto",
        cmap="RdBu_r",
        norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
    )
    axis.set_xticks(np.arange(len(labels)), labels=labels, rotation=30, ha="right")
    axis.set_yticks(np.arange(len(pivot.index)), labels=pivot.index)
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            axis.text(
                column,
                row,
                f"{values[row, column]:+.1f}",
                ha="center",
                va="center",
                fontsize=8,
            )
    colorbar = figure.colorbar(image, ax=axis, pad=0.02)
    colorbar.set_label("20 log10(table/floor) (dB)")
    axis.set_title("Optical-table change by frequency band (negative is quieter)")
    figure.tight_layout()
    save_figure(figure, directory, "optical_table_performance")
    return frame


def plot_candidate_rms(candidate_metrics: pd.DataFrame, directory: Path) -> None:
    labels = candidate_metrics["display_name"].tolist()
    y = np.arange(len(labels))
    figure, axis = plt.subplots(figsize=(7.2, 3.8))
    width = 0.35
    axis.barh(
        y - width / 2,
        candidate_metrics["decision_rms_mps2"],
        height=width,
        label="Integrated RMS including remaining lines",
        color="#6BAED6",
    )
    axis.barh(
        y + width / 2,
        candidate_metrics["broadband_rms_estimate_mps2"],
        height=width,
        label="Median-filtered broadband estimate",
        color="#31A354",
    )
    axis.set_yticks(y, labels=labels)
    axis.invert_yaxis()
    axis.set_xscale("log")
    axis.set_xlabel(r"RMS acceleration estimate (m s$^{-2}$)")
    axis.set_title("Narrow lines can dominate an otherwise quiet spectrum")
    axis.grid(True, axis="x", which="both", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    save_figure(figure, directory, "candidate_rms_context")


def plot_mains_line(metrics: pd.DataFrame, directory: Path) -> None:
    ordered = metrics.sort_values("max_58_62_asd_mps2_per_sqrthz")
    labels = [f"{row.room}: {row.location}" for row in ordered.itertuples()]
    figure, axis = plt.subplots(figsize=(7.2, 4.6))
    axis.barh(
        labels,
        ordered["max_58_62_asd_mps2_per_sqrthz"],
        color=["#555555" if "Freezer" in label else "#6BAED6" for label in labels],
    )
    axis.set_xscale("log")
    axis.set_xlabel(r"Maximum ASD from 58-62 Hz (m s$^{-2}$ Hz$^{-1/2}$)")
    axis.set_title("The approximately 60 Hz feature is not constant across measurements")
    axis.grid(True, axis="x", which="both", alpha=0.25)
    figure.tight_layout()
    save_figure(figure, directory, "sixty_hz_feature_comparison")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "FinalReportData.xlsx",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    analysis_dir = output_root / "analysis"
    figure_dir = output_root / "figures"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    runs = parse_workbook(args.workbook.resolve())
    if len(runs) != 15:
        raise RuntimeError(f"Expected 15 numerical spectra; detected {len(runs)}.")

    all_peaks = pd.concat([detect_peaks(run) for run in runs], ignore_index=True)
    all_peaks.to_csv(analysis_dir / "peaks_from_spectra.csv", index=False)

    all_metrics = pd.DataFrame([metrics_for(run) for run in runs])
    all_metrics.to_csv(analysis_dir / "summary_metrics_simple.csv", index=False)

    freezer = find_run(runs, "Herzog Lab", "Freezer Top")
    herzog = find_run(runs, "Herzog Lab", "Floor")
    phys111 = find_run(runs, "PHYS 111", "Floor")
    distant = [
        find_run(runs, "Titan Lab", "Lab Floor (carpet hole)"),
        find_run(runs, "PHYS 244", "Floor"),
        find_run(runs, "PHYS 245", "Floor"),
    ]
    matches = pd.concat(
        [
            match_freezer_signature(herzog, freezer, distant),
            match_freezer_signature(phys111, freezer, distant),
        ],
        ignore_index=True,
    )
    matches.to_csv(analysis_dir / "freezer_peak_matches.csv", index=False)

    adjusted_herzog, herzog_bands = replace_narrow_lines(
        herzog, matches[matches["room"] == "Herzog Lab"]
    )
    adjusted_phys111, phys111_bands = replace_narrow_lines(
        phys111, matches[matches["room"] == "PHYS 111"]
    )
    adjusted = {"Herzog Lab": adjusted_herzog, "PHYS 111": adjusted_phys111}

    candidate_specs = [
        (
            "Titan Lab",
            find_run(runs, "Titan Lab", "Lab Floor (carpet hole)"),
            None,
        ),
        ("PHYS 245", find_run(runs, "PHYS 245", "Floor"), None),
        ("PHYS 111", phys111, adjusted_phys111),
        ("Herzog Lab", herzog, adjusted_herzog),
    ]
    candidate_rows: list[dict] = []
    for display_name, run, adjusted_asd in candidate_specs:
        measured = metrics_for(run)
        decision = metrics_for(run, adjusted_asd) if adjusted_asd is not None else measured
        candidate_rows.append(
            {
                "display_name": display_name,
                "measured_rms_mps2": measured["raw_rms_2_250_ex58_62_mps2"],
                "decision_rms_mps2": decision["raw_rms_2_250_ex58_62_mps2"],
                "broadband_rms_estimate_mps2": decision[
                    "broadband_rms_estimate_mps2"
                ],
                "median_asd_mps2_per_sqrthz": decision[
                    "median_asd_ex58_62_mps2_per_sqrthz"
                ],
                "largest_peak_frequency_hz": decision["largest_peak_frequency_hz"],
                "largest_peak_asd_mps2_per_sqrthz": decision[
                    "largest_peak_asd_mps2_per_sqrthz"
                ],
                "prominent_peak_count": decision["prominent_peak_count"],
                "freezer_adjusted": adjusted_asd is not None,
            }
        )
    candidate_metrics = pd.DataFrame(candidate_rows)
    candidate_metrics.to_csv(analysis_dir / "candidate_room_metrics.csv", index=False)

    configure_style()
    plot_representative_floors(runs, figure_dir)
    plot_titan_comparison(runs, figure_dir)
    plot_within_herzog(runs, figure_dir)
    plot_freezer_adjustment(
        freezer, herzog, phys111, adjusted, matches, figure_dir
    )
    optical = plot_optical_table_performance(runs, figure_dir)
    optical.to_csv(analysis_dir / "optical_table_changes.csv", index=False)
    plot_candidate_rms(candidate_metrics, figure_dir)
    plot_mains_line(all_metrics, figure_dir)

    metadata = {
        "source_workbook": str(args.workbook.resolve()),
        "source_workbook_modified": False,
        "measurement_runs": len(runs),
        "peak_source": (
            "Peaks detected only from numerical frequency_hz and "
            "r_spectral_asd_mps2_per_sqrt_hz columns; worksheet peak tables ignored."
        ),
        "low_frequency_cutoff_hz": LOW_CUT_HZ,
        "mains_exclusion_hz": [MAINS_LOW_HZ, MAINS_HIGH_HZ],
        "freezer_method": (
            "Match unsmoothed numerical ASD peaks within 1.6 Hz; retain lines "
            "seen on at least two distant floors; replace only source-specific "
            "matched lines over +/-1.5 Hz by log-linear local interpolation."
        ),
        "herzog_replaced_bands_hz": herzog_bands,
        "phys111_replaced_bands_hz": phys111_bands,
    }
    (analysis_dir / "analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print(candidate_metrics.to_string(index=False))
    print()
    print(matches.to_string(index=False))


if __name__ == "__main__":
    main()
