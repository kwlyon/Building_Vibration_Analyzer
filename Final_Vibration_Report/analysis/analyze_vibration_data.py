#!/usr/bin/env python
"""Reproducible analysis of FinalReportData.xlsx building-vibration spectra.

The workbook is treated as read-only.  Each measurement block is detected from
the paired ``frequency_hz`` and ``r_spectral_asd_mps2_per_sqrt_hz`` headers,
rather than from fixed sheet widths.  Output tables, extracted spectra, plots,
and LaTeX table fragments are regenerated under Final_Vibration_Report.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from openpyxl import load_workbook
from scipy.signal import find_peaks


BANDS = [
    ("0.5-5 Hz", 0.5, 5.0),
    ("5-10 Hz", 5.0, 10.0),
    ("10-20 Hz", 10.0, 20.0),
    ("20-50 Hz", 20.0, 50.0),
    ("50-100 Hz", 50.0, 100.0),
    ("100-250 Hz", 100.0, 250.0),
]
PEAK_MATCH_TOLERANCE_HZ = 1.0

REPRESENTATIVE_LOCATION = {
    "Titan Lab": "Lab Floor (carpet hole)",
    "PHYS 111": "Floor",
    "Herzog Lab": "Floor",
    "PHYS 244": "Floor",
    "PHYS 245": "Floor",
}

COMPARISON_PAIRS = [
    ("PHYS 111", "Floor", "Optical Table Wall", "optical table; float status not recorded"),
    ("PHYS 111", "Floor", "Optical Table Door", "optical table; float status not recorded"),
    ("Herzog Lab", "Floor", "Optical Table", "optical table; float status not recorded"),
    ("PHYS 244", "Floor", "Wooden Table", "wooden table; not an isolation table"),
    ("PHYS 245", "Floor", "Floated Table (AFM)", "explicitly floated optical table"),
    ("PHYS 245", "Floor", "Unfloated Table (Oliver Laser)", "explicitly unfloated optical table"),
]

ROOM_ORDER = ["Titan Lab", "PHYS 111", "Herzog Lab", "PHYS 244", "PHYS 245"]
COLORS = {
    "Titan Lab": "#0072B2",
    "PHYS 111": "#E69F00",
    "Herzog Lab": "#D55E00",
    "PHYS 244": "#009E73",
    "PHYS 245": "#CC79A7",
}


@dataclass
class SpectrumRun:
    room: str
    location: str
    sheet: str
    label_column: int
    frequency_hz: np.ndarray
    asd_mps2_sqrthz: np.ndarray
    excel_peaks: list[tuple[float, float]]
    diagnostic: bool = False
    questionable: bool = False
    location_class: str = ""

    @property
    def run_id(self) -> str:
        return f"{self.room} - {self.location}"


def slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", text.strip()).strip("_")
    return text.lower()


def classify_location(room: str, location: str) -> tuple[str, bool, bool]:
    lower = location.lower()
    diagnostic = "freezer" in lower
    questionable = room == "Titan Lab" and lower == "entry"
    if diagnostic:
        kind = "diagnostic equipment reference"
    elif "unfloated" in lower:
        kind = "unfloated optical table"
    elif "floated" in lower:
        kind = "floated optical table"
    elif "optical table" in lower:
        kind = "optical table (float status not recorded)"
    elif "floor" in lower or lower == "entry":
        kind = "floor"
    elif "counter" in lower:
        kind = "counter"
    elif "wooden table" in lower:
        kind = "wooden table"
    else:
        kind = "other"
    return kind, diagnostic, questionable


def parse_workbook(workbook_path: Path) -> tuple[list[SpectrumRun], list[dict]]:
    """Detect run blocks by headers and extract ASD plus Excel peak tables."""
    wb = load_workbook(workbook_path, data_only=True, read_only=False)
    runs: list[SpectrumRun] = []
    sheets: list[dict] = []

    for ws in wb.worksheets:
        detected = 0
        for col in range(1, ws.max_column + 1):
            # A run label is four columns before frequency and five before ASD.
            if col + 5 > ws.max_column:
                continue
            if (
                ws.cell(1, col + 4).value == "frequency_hz"
                and ws.cell(1, col + 5).value
                == "r_spectral_asd_mps2_per_sqrt_hz"
                and ws.cell(1, col).value
            ):
                location = str(ws.cell(1, col).value).strip()
                frequencies = []
                amplitudes = []
                for row in range(2, ws.max_row + 1):
                    freq = ws.cell(row, col + 4).value
                    amp = ws.cell(row, col + 5).value
                    if isinstance(freq, (int, float)) and isinstance(amp, (int, float)):
                        frequencies.append(float(freq))
                        amplitudes.append(float(amp))

                excel_peaks: list[tuple[float, float]] = []
                # Rows 4 onward contain the workbook's five "Dominant FFT Peaks."
                for row in range(4, min(ws.max_row, 30) + 1):
                    axis = ws.cell(row, col).value
                    freq = ws.cell(row, col + 1).value
                    amp = ws.cell(row, col + 2).value
                    if (
                        axis == "R spectral RSS"
                        and isinstance(freq, (int, float))
                        and isinstance(amp, (int, float))
                    ):
                        excel_peaks.append((float(freq), float(amp)))

                if len(frequencies) < 10:
                    continue
                freq_array = np.asarray(frequencies, dtype=float)
                amp_array = np.asarray(amplitudes, dtype=float)
                order = np.argsort(freq_array)
                freq_array = freq_array[order]
                amp_array = amp_array[order]
                kind, diagnostic, questionable = classify_location(ws.title, location)
                runs.append(
                    SpectrumRun(
                        room=ws.title,
                        location=location,
                        sheet=ws.title,
                        label_column=col,
                        frequency_hz=freq_array,
                        asd_mps2_sqrthz=amp_array,
                        excel_peaks=excel_peaks,
                        diagnostic=diagnostic,
                        questionable=questionable,
                        location_class=kind,
                    )
                )
                detected += 1

        sheets.append(
            {
                "worksheet": ws.title,
                "rows": ws.max_row,
                "columns": ws.max_column,
                "embedded_charts": len(ws._charts),
                "detected_runs": detected,
                "role": "chart-only summary" if detected == 0 and ws._charts else "measurement data",
            }
        )
    return runs, sheets


def band_rms(run: SpectrumRun, low: float, high: float) -> float:
    f = run.frequency_hz
    a = run.asd_mps2_sqrthz
    mask = (f >= low) & (f < high)
    if not np.any(mask):
        return float("nan")
    df = float(np.median(np.diff(f)))
    # ASD squared is acceleration PSD; integrating PSD and taking sqrt gives RMS acceleration.
    return float(np.sqrt(np.sum(np.square(a[mask]) * df)))


def robust_peaks(run: SpectrumRun, max_peaks: int = 12) -> pd.DataFrame:
    """Return prominent unsmoothed ASD peaks using log-domain prominence."""
    f = run.frequency_hz
    a = run.asd_mps2_sqrthz
    valid = (f >= 0.5) & np.isfinite(a) & (a > 0)
    f_valid = f[valid]
    a_valid = a[valid]
    log_a = np.log10(a_valid)
    idx, props = find_peaks(log_a, prominence=0.08, distance=2)
    if len(idx) == 0:
        idx = np.asarray([int(np.argmax(a_valid))])
        prominence = np.asarray([np.nan])
    else:
        prominence = props["prominences"]
    frame = pd.DataFrame(
        {
            "frequency_hz": f_valid[idx],
            "asd_mps2_per_sqrt_hz": a_valid[idx],
            "log10_prominence": prominence,
        }
    )
    frame = frame.sort_values("asd_mps2_per_sqrt_hz", ascending=False).head(max_peaks)
    frame.insert(0, "run_id", run.run_id)
    frame.insert(0, "location", run.location)
    frame.insert(0, "room", run.room)
    frame.insert(3, "peak_rank", np.arange(1, len(frame) + 1))
    return frame.reset_index(drop=True)


def nearest_asd(run: SpectrumRun, frequency: float) -> tuple[float, float]:
    index = int(np.argmin(np.abs(run.frequency_hz - frequency)))
    return float(run.frequency_hz[index]), float(run.asd_mps2_sqrthz[index])


def run_metrics(run: SpectrumRun) -> dict:
    f = run.frequency_hz
    a = run.asd_mps2_sqrthz
    analysis_mask = f >= 0.5
    max_index = np.where(analysis_mask)[0][int(np.argmax(a[analysis_mask]))]
    df = float(np.median(np.diff(f)))
    result = {
        "room": run.room,
        "location": run.location,
        "run_id": run.run_id,
        "location_class": run.location_class,
        "diagnostic_reference": run.diagnostic,
        "questionable": run.questionable,
        "n_bins": len(f),
        "frequency_resolution_hz": df,
        "max_frequency_hz": float(np.max(f)),
        "rms_0p5_250_mps2": band_rms(run, 0.5, 250.0001),
        "rms_0p5_50_mps2": band_rms(run, 0.5, 50.0),
        "median_asd_mps2_per_sqrthz": float(np.median(a[analysis_mask])),
        "p95_asd_mps2_per_sqrthz": float(np.percentile(a[analysis_mask], 95)),
        "max_asd_mps2_per_sqrthz": float(a[max_index]),
        "frequency_of_max_hz": float(f[max_index]),
    }
    for label, low, high in BANDS:
        result[f"rms_{slug(label)}_mps2"] = band_rms(run, low, high)
    return result


def find_run(runs: Iterable[SpectrumRun], room: str, location: str) -> SpectrumRun:
    for run in runs:
        if run.room == room and run.location == location:
            return run
    raise KeyError(f"Missing run: {room} / {location}")


def make_attenuation_tables(runs: list[SpectrumRun]) -> tuple[pd.DataFrame, pd.DataFrame]:
    band_rows: list[dict] = []
    peak_rows: list[dict] = []
    for room, floor_name, table_name, note in COMPARISON_PAIRS:
        floor = find_run(runs, room, floor_name)
        table = find_run(runs, room, table_name)
        for label, low, high in BANDS + [("0.5-250 Hz", 0.5, 250.0001)]:
            floor_rms = band_rms(floor, low, high)
            table_rms = band_rms(table, low, high)
            ratio = table_rms / floor_rms
            band_rows.append(
                {
                    "room": room,
                    "reference_location": floor_name,
                    "comparison_location": table_name,
                    "comparison_type": note,
                    "band": label,
                    "floor_rms_mps2": floor_rms,
                    "table_rms_mps2": table_rms,
                    "amplitude_ratio_table_to_floor": ratio,
                    "percent_reduction": 100.0 * (1.0 - ratio),
                    "attenuation_db": 20.0 * math.log10(ratio),
                }
            )

        floor_peaks = robust_peaks(floor, max_peaks=8).head(5)
        for _, row in floor_peaks.iterrows():
            target = float(row["frequency_hz"])
            matched_frequency, table_asd = nearest_asd(table, target)
            floor_asd = float(row["asd_mps2_per_sqrt_hz"])
            ratio = table_asd / floor_asd
            peak_rows.append(
                {
                    "room": room,
                    "reference_location": floor_name,
                    "comparison_location": table_name,
                    "comparison_type": note,
                    "floor_peak_frequency_hz": target,
                    "table_bin_frequency_hz": matched_frequency,
                    "floor_asd_mps2_per_sqrt_hz": floor_asd,
                    "table_asd_mps2_per_sqrt_hz": table_asd,
                    "amplitude_ratio_table_to_floor": ratio,
                    "percent_reduction": 100.0 * (1.0 - ratio),
                    "attenuation_db": 20.0 * math.log10(ratio),
                }
            )
    return pd.DataFrame(band_rows), pd.DataFrame(peak_rows)


def match_shared_peaks(
    run_a: SpectrumRun,
    run_b: SpectrumRun,
    reference: SpectrumRun,
    other_floor_runs: list[SpectrumRun],
) -> pd.DataFrame:
    peaks_a = robust_peaks(run_a, 15)
    peaks_b = robust_peaks(run_b, 15)
    peaks_ref = robust_peaks(reference, 20)
    rows = []
    used_b: set[int] = set()
    for _, peak_a in peaks_a.iterrows():
        candidates = peaks_b.index[
            np.abs(peaks_b["frequency_hz"] - peak_a["frequency_hz"])
            <= PEAK_MATCH_TOLERANCE_HZ
        ].tolist()
        candidates = [idx for idx in candidates if idx not in used_b]
        if not candidates:
            continue
        best = min(
            candidates,
            key=lambda idx: abs(
                float(peaks_b.loc[idx, "frequency_hz"]) - float(peak_a["frequency_hz"])
            ),
        )
        used_b.add(best)
        frequency = float(
            np.mean([peak_a["frequency_hz"], peaks_b.loc[best, "frequency_hz"]])
        )
        ref_candidates = peaks_ref.index[
            np.abs(peaks_ref["frequency_hz"] - frequency) <= PEAK_MATCH_TOLERANCE_HZ
        ].tolist()
        ref_match = min(
            ref_candidates,
            key=lambda idx: abs(float(peaks_ref.loc[idx, "frequency_hz"]) - frequency),
        ) if ref_candidates else None
        excel_ref_candidates = [
            (fft_frequency, fft_amplitude)
            for fft_frequency, fft_amplitude in reference.excel_peaks
            if abs(fft_frequency - frequency) <= PEAK_MATCH_TOLERANCE_HZ
        ]
        excel_ref_match = (
            min(excel_ref_candidates, key=lambda pair: abs(pair[0] - frequency))
            if excel_ref_candidates
            else None
        )
        if ref_match is not None:
            freezer_frequency = float(peaks_ref.loc[ref_match, "frequency_hz"])
            freezer_asd = float(peaks_ref.loc[ref_match, "asd_mps2_per_sqrt_hz"])
            freezer_basis = "ASD peak"
        elif excel_ref_match is not None:
            freezer_frequency = float(excel_ref_match[0])
            _, freezer_asd = nearest_asd(reference, freezer_frequency)
            freezer_basis = "workbook FFT peak"
        else:
            freezer_frequency = np.nan
            freezer_asd = np.nan
            freezer_basis = ""
        distant_matches = 0
        for other in other_floor_runs:
            other_peaks = robust_peaks(other, 15)
            if np.any(
                np.abs(other_peaks["frequency_hz"].to_numpy(dtype=float) - frequency)
                <= PEAK_MATCH_TOLERANCE_HZ
            ):
                distant_matches += 1
        rows.append(
            {
                "shared_frequency_hz": frequency,
                "herzog_frequency_hz": float(peak_a["frequency_hz"]),
                "herzog_asd_mps2_per_sqrt_hz": float(
                    peak_a["asd_mps2_per_sqrt_hz"]
                ),
                "phys111_frequency_hz": float(peaks_b.loc[best, "frequency_hz"]),
                "phys111_asd_mps2_per_sqrt_hz": float(
                    peaks_b.loc[best, "asd_mps2_per_sqrt_hz"]
                ),
                "freezer_peak_match": ref_match is not None or excel_ref_match is not None,
                "freezer_match_basis": freezer_basis,
                "freezer_frequency_hz": freezer_frequency,
                "freezer_asd_mps2_per_sqrt_hz": freezer_asd,
                "distant_floor_matches_of_3": distant_matches,
            }
        )
    return pd.DataFrame(rows).sort_values(
        "herzog_asd_mps2_per_sqrt_hz", ascending=False
    )


def cluster_floor_peaks(floor_runs: list[SpectrumRun]) -> pd.DataFrame:
    entries = []
    for run in floor_runs:
        peaks = robust_peaks(run, 15)
        for _, peak in peaks.iterrows():
            entries.append(
                {
                    "room": run.room,
                    "frequency_hz": float(peak["frequency_hz"]),
                    "asd": float(peak["asd_mps2_per_sqrt_hz"]),
                }
            )
    entries.sort(key=lambda item: item["frequency_hz"])
    clusters: list[list[dict]] = []
    for entry in entries:
        if not clusters:
            clusters.append([entry])
            continue
        center = float(np.mean([x["frequency_hz"] for x in clusters[-1]]))
        if abs(entry["frequency_hz"] - center) <= PEAK_MATCH_TOLERANCE_HZ:
            clusters[-1].append(entry)
        else:
            clusters.append([entry])
    rows = []
    for cluster in clusters:
        rooms = sorted({entry["room"] for entry in cluster})
        if len(rooms) >= 3:
            rows.append(
                {
                    "cluster_frequency_hz": float(
                        np.average(
                            [entry["frequency_hz"] for entry in cluster],
                            weights=[entry["asd"] for entry in cluster],
                        )
                    ),
                    "room_count": len(rooms),
                    "rooms": "; ".join(rooms),
                    "median_asd_mps2_per_sqrt_hz": float(
                        np.median([entry["asd"] for entry in cluster])
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values(["room_count", "cluster_frequency_hz"], ascending=[False, True])


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.titlesize": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.bbox": "tight",
            "pdf.fonttype": 42,
        }
    )


def save_figure(fig: plt.Figure, figure_dir: Path, name: str) -> None:
    fig.savefig(figure_dir / f"{name}.pdf")
    fig.savefig(figure_dir / f"{name}.png", dpi=240)
    plt.close(fig)


def plot_figures(
    runs: list[SpectrumRun],
    metrics: pd.DataFrame,
    ranking: pd.DataFrame,
    attenuation: pd.DataFrame,
    figure_dir: Path,
) -> None:
    configure_style()
    figure_dir.mkdir(parents=True, exist_ok=True)

    representative_runs = [
        find_run(runs, room, REPRESENTATIVE_LOCATION[room]) for room in ROOM_ORDER
    ]
    positive = np.concatenate([run.asd_mps2_sqrthz[run.asd_mps2_sqrthz > 0] for run in representative_runs])
    ymin = 10 ** math.floor(math.log10(float(np.percentile(positive, 0.5))))
    ymax = 10 ** math.ceil(math.log10(float(np.max(positive))))

    fig, axes = plt.subplots(3, 2, figsize=(7.2, 8.7), sharex=True, sharey=True)
    for ax, run in zip(axes.flat, representative_runs):
        ax.plot(run.frequency_hz, run.asd_mps2_sqrthz, lw=0.8, color=COLORS[run.room])
        ax.set_title(f"{run.room}: {run.location}")
        ax.set_yscale("log")
        ax.set_xlim(0, 250)
        ax.set_ylim(ymin, ymax)
        ax.grid(True, which="both", alpha=0.18)
    axes.flat[-1].axis("off")
    fig.supxlabel("Frequency (Hz)")
    fig.supylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)")
    fig.suptitle("Representative floor spectrum for each measured laboratory")
    fig.tight_layout(rect=[0.04, 0.03, 1, 0.97])
    save_figure(fig, figure_dir, "representative_spectra_by_room")

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for room, location, label, color in [
        ("Herzog Lab", "Freezer Top", "Freezer top", "#000000"),
        ("Herzog Lab", "Floor", "Herzog floor", COLORS["Herzog Lab"]),
    ]:
        run = find_run(runs, room, location)
        ax.plot(run.frequency_hz, run.asd_mps2_sqrthz, label=label, color=color, lw=1.0)
    ax.set_xlim(0, 160)
    ax.set_yscale("log")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)")
    ax.set_title("Herzog floor and ultra-low-temperature freezer")
    ax.grid(True, which="both", alpha=0.2)
    ax.legend()
    save_figure(fig, figure_dir, "herzog_phys111_freezer_comparison")

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for location, color in [
        ("Floor", "#0072B2"),
        ("Floated Table (AFM)", "#D55E00"),
        ("Unfloated Table (Oliver Laser)", "#009E73"),
    ]:
        run = find_run(runs, "PHYS 245", location)
        ax.plot(run.frequency_hz, run.asd_mps2_sqrthz, label=location, color=color, lw=1.0)
    ax.set_xlim(0, 100)
    ax.set_yscale("log")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)")
    ax.set_title("PHYS 245: floated and unfloated table measurements")
    ax.grid(True, which="both", alpha=0.2)
    ax.legend()
    save_figure(fig, figure_dir, "phys245_floated_unfloated_floor")

    optical = attenuation[
        attenuation["comparison_type"].str.contains("optical table")
        & attenuation["band"].isin([label for label, _, _ in BANDS])
    ].copy()
    pivot = optical.pivot(
        index=["room", "comparison_location"], columns="band", values="attenuation_db"
    )
    pivot = pivot[[label for label, _, _ in BANDS]]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    values = pivot.to_numpy()
    limit = max(6.0, float(np.nanmax(np.abs(values))))
    image = ax.imshow(values, aspect="auto", cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit))
    ax.set_xticks(np.arange(len(pivot.columns)), labels=pivot.columns, rotation=35, ha="right")
    ax.set_yticks(
        np.arange(len(pivot.index)),
        labels=[f"{room}: {location}" for room, location in pivot.index],
    )
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            ax.text(col, row, f"{values[row, col]:+.1f}", ha="center", va="center", fontsize=8)
    cbar = fig.colorbar(image, ax=ax, pad=0.02)
    cbar.set_label("20 log10(table/floor) (dB)")
    ax.set_title("Band-limited table-to-floor change (negative is attenuation)")
    fig.tight_layout()
    save_figure(fig, figure_dir, "optical_table_attenuation_heatmap")

def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in str(text))


def write_latex_table(
    path: Path,
    frame: pd.DataFrame,
    columns: list[str],
    headers: list[str],
    formats: dict[str, str] | None = None,
    longtable: bool = False,
    column_spec: str | None = None,
) -> None:
    formats = formats or {}
    environment = "longtable" if longtable else "tabular"
    alignment = column_spec or ("r" + "l" * (len(columns) - 1))
    lines = [f"\\begin{{{environment}}}{{{alignment}}}", "\\toprule"]
    lines.append(" & ".join(headers) + r" \\")
    lines.append("\\midrule")
    if longtable:
        lines.extend([r"\endhead"])
    for _, row in frame.iterrows():
        values = []
        for column in columns:
            value = row[column]
            if pd.isna(value):
                values.append("--")
            elif column in formats:
                values.append(format(value, formats[column]))
            elif isinstance(value, (bool, np.bool_)):
                values.append("yes" if value else "no")
            else:
                values.append(latex_escape(str(value)))
        lines.append(" & ".join(values) + r" \\")
    lines.extend(["\\bottomrule", f"\\end{{{environment}}}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex_fragments(
    report_generated: Path,
    ranking: pd.DataFrame,
    attenuation: pd.DataFrame,
) -> None:
    report_generated.mkdir(parents=True, exist_ok=True)
    write_latex_table(
        report_generated / "room_ranking.tex",
        ranking.sort_values("rank"),
        [
            "rank",
            "room",
            "representative_location",
            "rms_0p5_250_mps2",
            "median_asd_mps2_per_sqrthz",
        ],
        [
            "Rank",
            "Room",
            "Floor location",
            "RMS (m/s$^2$)",
            "Median ASD",
        ],
        formats={
            "rank": ".0f",
            "rms_0p5_250_mps2": ".3g",
            "median_asd_mps2_per_sqrthz": ".3g",
        },
    )
    optical_total = attenuation[
        attenuation["comparison_type"].str.contains("optical table")
        & (attenuation["band"] == "0.5-250 Hz")
    ].copy()
    write_latex_table(
        report_generated / "optical_table_summary.tex",
        optical_total,
        [
            "room",
            "comparison_location",
            "floor_rms_mps2",
            "table_rms_mps2",
            "amplitude_ratio_table_to_floor",
            "percent_reduction",
            "attenuation_db",
        ],
        [
            "Room",
            "Table location",
            "Floor RMS",
            "Table RMS",
            "Ratio",
            "Reduction (\\%)",
            "Change (dB)",
        ],
        formats={
            "floor_rms_mps2": ".3g",
            "table_rms_mps2": ".3g",
            "amplitude_ratio_table_to_floor": ".2f",
            "percent_reduction": "+.1f",
            "attenuation_db": "+.1f",
        },
    )


def main() -> None:
    script_path = Path(__file__).resolve()
    default_root = script_path.parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=default_root.parent / "FinalReportData.xlsx",
        help="Source workbook (read-only).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=default_root,
        help="Final_Vibration_Report output directory.",
    )
    args = parser.parse_args()

    output_root = args.output_root.resolve()
    extracted_dir = output_root / "analysis" / "extracted_data"
    figure_dir = output_root / "figures"
    report_generated = output_root / "report" / "generated"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    report_generated.mkdir(parents=True, exist_ok=True)

    runs, sheet_inventory = parse_workbook(args.workbook.resolve())
    if not runs:
        raise RuntimeError("No spectrum blocks were detected.")

    inventory_rows = []
    for run in runs:
        pd.DataFrame(
            {
                "frequency_hz": run.frequency_hz,
                "r_spectral_asd_mps2_per_sqrt_hz": run.asd_mps2_sqrthz,
            }
        ).to_csv(
            extracted_dir / f"{slug(run.room)}__{slug(run.location)}.csv",
            index=False,
        )
        inventory_rows.append(
            {
                "worksheet": run.sheet,
                "room": run.room,
                "location": run.location,
                "location_class": run.location_class,
                "diagnostic_reference": run.diagnostic,
                "questionable": run.questionable,
                "bins": len(run.frequency_hz),
                "frequency_min_hz": float(np.min(run.frequency_hz)),
                "frequency_max_hz": float(np.max(run.frequency_hz)),
                "frequency_resolution_hz": float(np.median(np.diff(run.frequency_hz))),
                "excel_prominent_peaks": len(run.excel_peaks),
            }
        )
    inventory = pd.DataFrame(inventory_rows)
    inventory.to_csv(output_root / "analysis" / "measurement_inventory.csv", index=False)
    pd.DataFrame(sheet_inventory).to_csv(
        output_root / "analysis" / "worksheet_inventory.csv", index=False
    )

    metrics = pd.DataFrame([run_metrics(run) for run in runs])
    metrics.to_csv(output_root / "analysis" / "summary_metrics.csv", index=False)

    dominant_frames = [robust_peaks(run) for run in runs]
    dominant = pd.concat(dominant_frames, ignore_index=True)
    dominant.to_csv(output_root / "analysis" / "dominant_peaks.csv", index=False)

    crosscheck_rows = []
    for run in runs:
        detected = robust_peaks(run, 30)
        for rank, (frequency, fft_amplitude) in enumerate(run.excel_peaks, start=1):
            nearest_index = int(
                np.argmin(np.abs(detected["frequency_hz"].to_numpy() - frequency))
            )
            nearest = detected.iloc[nearest_index]
            delta = abs(float(nearest["frequency_hz"]) - frequency)
            crosscheck_rows.append(
                {
                    "room": run.room,
                    "location": run.location,
                    "excel_peak_rank": rank,
                    "excel_frequency_hz": frequency,
                    "excel_fft_amplitude_mps2": fft_amplitude,
                    "nearest_detected_asd_peak_hz": float(nearest["frequency_hz"]),
                    "frequency_difference_hz": delta,
                    "matched_within_1hz": delta <= PEAK_MATCH_TOLERANCE_HZ,
                }
            )
    crosscheck = pd.DataFrame(crosscheck_rows)
    crosscheck.to_csv(
        output_root / "analysis" / "excel_peak_crosscheck.csv", index=False
    )

    floor_metrics = []
    floor_runs = []
    for room, location in REPRESENTATIVE_LOCATION.items():
        floor_runs.append(find_run(runs, room, location))
        floor_metrics.append(
            metrics[(metrics["room"] == room) & (metrics["location"] == location)].iloc[0]
        )
    ranking = pd.DataFrame(floor_metrics).copy()
    ranking.insert(0, "representative_location", ranking["location"])
    ranking = ranking.sort_values("rms_0p5_250_mps2").reset_index(drop=True)
    ranking.insert(0, "rank", np.arange(1, len(ranking) + 1))
    quietest = float(ranking.iloc[0]["rms_0p5_250_mps2"])
    ranking["rms_ratio_to_quietest"] = (
        ranking["rms_0p5_250_mps2"] / quietest
    )
    ranking["db_relative_to_quietest"] = 20.0 * np.log10(
        ranking["rms_ratio_to_quietest"]
    )
    ranking.to_csv(output_root / "analysis" / "room_ranking.csv", index=False)

    eligible = metrics[
        ~metrics["diagnostic_reference"] & ~metrics["questionable"]
    ].sort_values("rms_0p5_250_mps2")
    eligible.insert(0, "rank", np.arange(1, len(eligible) + 1))
    eligible.to_csv(
        output_root / "analysis" / "measured_location_ranking.csv", index=False
    )

    attenuation, attenuation_peaks = make_attenuation_tables(runs)
    attenuation.to_csv(
        output_root / "analysis" / "surface_attenuation_by_band.csv", index=False
    )
    attenuation_peaks.to_csv(
        output_root / "analysis" / "attenuation_at_floor_peaks.csv", index=False
    )

    herzog_floor = find_run(runs, "Herzog Lab", "Floor")
    phys111_floor = find_run(runs, "PHYS 111", "Floor")
    freezer = find_run(runs, "Herzog Lab", "Freezer Top")
    distant_floors = [
        find_run(runs, room, REPRESENTATIVE_LOCATION[room])
        for room in ["Titan Lab", "PHYS 244", "PHYS 245"]
    ]
    shared = match_shared_peaks(
        herzog_floor, phys111_floor, freezer, distant_floors
    )
    shared.to_csv(
        output_root / "analysis" / "herzog_phys111_shared_peaks.csv", index=False
    )
    broad = cluster_floor_peaks(floor_runs)
    broad.to_csv(
        output_root / "analysis" / "broad_building_peak_clusters.csv", index=False
    )

    flags = pd.DataFrame(
        [
            {
                "room": "Titan Lab",
                "location": "Entry",
                "flag": "Known potentially contaminated run",
                "basis": "User notes possible door opening and foot traffic; retain for context but exclude from representative ranking.",
                "recommended_action": "Repeat under controlled occupancy.",
            },
            {
                "room": "PHYS 111",
                "location": "Optical Table Door",
                "flag": "Strong anomalous 29.8 Hz line",
                "basis": "Integrated 0.5-250 Hz RMS is far above the PHYS 111 floor and table-wall runs; spectrum alone cannot identify a transient.",
                "recommended_action": "Repeat and capture time series/spectrogram.",
            },
            {
                "room": "PHYS 245",
                "location": "Floated Table (AFM)",
                "flag": "Unexpected table amplification",
                "basis": "The 10-20 Hz and total RMS metrics exceed the floor measurement, with a strong 17.6 Hz feature.",
                "recommended_action": "Check air pressure, leveling, payload, and isolator resonance; repeat simultaneously with the floor.",
            },
            {
                "room": "Herzog Lab",
                "location": "Freezer Top",
                "flag": "Diagnostic reference, not a candidate site",
                "basis": "Deliberately measured on equipment; excluded from room rankings.",
                "recommended_action": "Repeat with compressor on/off to isolate the freezer signature.",
            },
        ]
    )
    flags.to_csv(output_root / "analysis" / "data_quality_flags.csv", index=False)

    metadata = {
        "source_workbook": str(args.workbook.resolve()),
        "source_workbook_modified": False,
        "worksheets_examined": [entry["worksheet"] for entry in sheet_inventory],
        "measurement_runs": len(runs),
        "frequency_grid": {
            "bins": sorted({len(run.frequency_hz) for run in runs}),
            "resolution_hz": sorted(
                {round(float(np.median(np.diff(run.frequency_hz))), 12) for run in runs}
            ),
            "maximum_hz": sorted(
                {round(float(np.max(run.frequency_hz)), 9) for run in runs}
            ),
        },
        "primary_metric": "sqrt(sum(ASD^2 * df)) from 0.5 to 250 Hz",
        "peak_detection": "Local maxima in unsmoothed log10 ASD with prominence >= 0.08 decade and minimum separation of two bins; ranked by ASD.",
        "peak_match_tolerance_hz": PEAK_MATCH_TOLERANCE_HZ,
        "limitations": [
            "Only one spectrum is available for most locations; no time-domain records or repeated trials were supplied.",
            "Acquisition duration, window, overlap, sensor calibration uncertainty, and contemporaneous equipment states are not recorded in the workbook.",
            "Optical-table float status is explicit only for PHYS 245.",
        ],
    }
    (output_root / "analysis" / "analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    plot_figures(runs, metrics, ranking, attenuation, figure_dir)
    write_latex_fragments(report_generated, ranking, attenuation)

    print(f"Examined {len(sheet_inventory)} worksheets and extracted {len(runs)} runs.")
    print(
        "Quietest representative floor by integrated RMS:",
        ranking.iloc[0]["room"],
        f'({ranking.iloc[0]["rms_0p5_250_mps2"]:.6g} m/s^2)',
    )
    print(f"Outputs written under: {output_root}")


if __name__ == "__main__":
    main()
