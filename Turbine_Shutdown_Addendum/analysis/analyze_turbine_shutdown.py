#!/usr/bin/env python
"""Pair, validate, analyze, and plot turbine-on/off vibration spectra.

The source directory is treated as read-only. All generated artifacts are
written beneath Turbine_Shutdown_Addendum.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import load_workbook


ASD_HEADER_TOKEN = "asd"
FREQUENCY_HEADER_TOKEN = "frequency"
VALID_EXTENSIONS = {".xlsx", ".xlsm", ".csv", ".txt", ".tsv"}
FULL_BAND = (0.5, 250.0)
MID_BAND = (20.0, 50.0)
LINE_FREQUENCIES_HZ = (29.8, 59.6, 98.7, 101.7, 119.7)
REPORT_LINE_FREQUENCIES_HZ = (29.8, 98.7, 101.7, 119.7)
PLOT_FREQUENCY_RANGE_HZ = (15.0, 160.0)

ON_COLOR = "#B23A35"
OFF_COLOR = "#17365D"
FREEZER_COLOR = "#D46A1F"
NAVY = "#17365D"
GRAY = "#666666"
SIGNATURE_COLOR = "#B23A35"


DISPLAY_METADATA = {
    "titanfloor": ("Titan Lab floor", "representative laboratory floor", True),
    "titanentryway": ("Titan Lab entryway", "supplementary building location", False),
    "herzogfloor": ("Herzog Lab floor", "representative laboratory floor", True),
    "herzogopticaltable": (
        "Herzog optical table",
        "supplementary building location",
        False,
    ),
    "244floor": ("PHYS 244 floor", "representative laboratory floor", True),
    "herzogtopofultracold": (
        "Herzog ultra-cold freezer top",
        "diagnostic equipment reference",
        False,
    ),
    "pipefromheatingplant": (
        "Pipe leaving heating plant",
        "source-path measurement",
        True,
    ),
    "sidewalkbetweenheatingandphysics": (
        "Sidewalk between plant and Physics",
        "source-path measurement",
        True,
    ),
    "111floor": ("PHYS 111 floor", "representative laboratory floor", True),
    "245floor": ("PHYS 245 floor", "representative laboratory floor", True),
    "111counteronherzogwall": (
        "PHYS 111 counter on Herzog wall",
        "unpaired building location",
        False,
    ),
    "111faropticaltable": (
        "PHYS 111 far optical table",
        "unpaired building location",
        False,
    ),
    "111neardooropticaltable": (
        "PHYS 111 near-door optical table",
        "unpaired building location",
        False,
    ),
    "244rollingtable": (
        "PHYS 244 rolling table",
        "unpaired building location",
        False,
    ),
    "245floatedtable": (
        "PHYS 245 floated table",
        "unpaired building location",
        False,
    ),
    "245unfloatedtable": (
        "PHYS 245 unfloated table",
        "unpaired building location",
        False,
    ),
    "herzogbackcountertop": (
        "Herzog back counter top",
        "unpaired building location",
        False,
    ),
    "coolingtowers": ("Cooling towers", "unpaired external location", False),
    "courtyardbetweenmullensunion": (
        "Courtyard between Mullens and Union",
        "unpaired external location",
        False,
    ),
    "greektheatertopstair": (
        "Greek Theater top stair",
        "unpaired external location",
        False,
    ),
}

PRIMARY_ORDER = [
    "titanfloor",
    "herzogfloor",
    "244floor",
    "pipefromheatingplant",
    "sidewalkbetweenheatingandphysics",
]
LAB_ORDER = ["titanfloor", "herzogfloor", "244floor"]
SOURCE_ORDER = ["pipefromheatingplant", "sidewalkbetweenheatingandphysics"]


@dataclass
class Spectrum:
    path: Path
    frequency_hz: np.ndarray
    asd_mps2_per_sqrt_hz: np.ndarray
    frequency_header: str
    asd_header: str
    units: str
    parsing_note: str
    exported_utc: str
    validation_errors: list[str]
    validation_warnings: list[str]

    @property
    def n_points(self) -> int:
        return int(len(self.frequency_hz))

    @property
    def min_frequency_hz(self) -> float:
        return float(np.min(self.frequency_hz))

    @property
    def max_frequency_hz(self) -> float:
        return float(np.max(self.frequency_hz))

    @property
    def bin_width_hz(self) -> float:
        if self.n_points < 2:
            return float("nan")
        return float(np.median(np.diff(self.frequency_hz)))

    @property
    def valid(self) -> bool:
        return not self.validation_errors


@dataclass
class Pair:
    key: str
    display_location: str
    category: str
    primary: bool
    on: Spectrum
    off: Spectrum

    @property
    def valid(self) -> bool:
        return self.on.valid and self.off.valid


def normalized_key(path: Path) -> tuple[str, bool]:
    """Return a case-insensitive measurement key and turbine-off flag."""
    compact = re.sub(r"[^a-z0-9]+", "", path.stem.lower())
    is_off = "noturbine" in compact
    tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", path.stem.lower())
        if token
    ]
    removable = {"no", "turbine", "noturbine", "fft", "export"}
    tokens = [token for token in tokens if token not in removable]
    if tokens and tokens[0] == "phys":
        tokens = tokens[1:]
    return "".join(tokens), is_off


def display_metadata(key: str, source_path: Path) -> tuple[str, str, bool]:
    if key in DISPLAY_METADATA:
        return DISPLAY_METADATA[key]
    words = re.sub(r"[_-]+", " ", source_path.stem)
    words = re.sub(r"\b(?:NoTurbine|fft|export)\b", "", words, flags=re.I)
    words = re.sub(r"\s+", " ", words).strip()
    return words, "unclassified candidate", False


def header_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def header_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", header_text(value).lower()).strip("_")


def validate_arrays(frequency: np.ndarray, asd: np.ndarray) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    if len(frequency) != len(asd):
        errors.append("frequency and ASD arrays have different lengths")
        return errors, notes
    if len(frequency) < 3:
        errors.append("fewer than three numerical spectrum points")
        return errors, notes
    if not np.all(np.isfinite(frequency)):
        errors.append("frequency contains NaN or infinite values")
    if not np.all(np.isfinite(asd)):
        errors.append("ASD contains NaN or infinite values")
    if np.any(asd < 0):
        errors.append("ASD contains negative values")
    spacing = np.diff(frequency)
    if np.any(spacing == 0):
        errors.append("duplicate frequency bins")
    if np.any(spacing < 0):
        errors.append("frequency is not monotonically increasing")
    if np.any(spacing <= 0):
        errors.append("zero or negative frequency spacing")
    if not errors:
        median_spacing = float(np.median(spacing))
        if not np.allclose(spacing, median_spacing, rtol=1e-6, atol=1e-9):
            notes.append("nonuniform frequency spacing; trapezoidal integration used")
        else:
            notes.append("uniform frequency spacing")
    if np.any(asd == 0):
        notes.append("zero ASD values present")
    return sorted(set(errors)), notes


def extract_excel_spectrum(path: Path) -> Spectrum:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        workbook = load_workbook(path, read_only=False, data_only=True)

    exported_utc = ""
    if "Summary" in workbook.sheetnames:
        summary = workbook["Summary"]
        for row in summary.iter_rows(values_only=True):
            if row and header_key(row[0]) == "exported_utc" and len(row) > 1:
                exported_utc = header_text(row[1])
                break

    candidates: list[tuple[object, int, int, int, str, str]] = []
    for worksheet in workbook.worksheets:
        max_scan_rows = min(25, worksheet.max_row or 0)
        max_scan_cols = min(100, worksheet.max_column or 0)
        for row_index in range(1, max_scan_rows + 1):
            values = [
                worksheet.cell(row_index, column).value
                for column in range(1, max_scan_cols + 1)
            ]
            keys = [header_key(value) for value in values]
            frequency_columns = [
                index + 1
                for index, key in enumerate(keys)
                if FREQUENCY_HEADER_TOKEN in key and "hz" in key
            ]
            asd_columns = [
                index + 1
                for index, key in enumerate(keys)
                if ASD_HEADER_TOKEN in key and "spectral" in key
            ]
            for frequency_column in frequency_columns:
                for asd_column in asd_columns:
                    candidates.append(
                        (
                            worksheet,
                            row_index,
                            frequency_column,
                            asd_column,
                            header_text(values[frequency_column - 1]),
                            header_text(values[asd_column - 1]),
                        )
                    )

    if not candidates:
        raise ValueError("no frequency/acceleration-ASD header pair found")

    # Prefer the standard PSD_ASD worksheet and the largest numerical block.
    parsed_candidates = []
    for worksheet, header_row, f_col, a_col, f_header, a_header in candidates:
        rows = []
        for row in worksheet.iter_rows(
            min_row=header_row + 1,
            min_col=min(f_col, a_col),
            max_col=max(f_col, a_col),
            values_only=True,
        ):
            frequency_value = row[f_col - min(f_col, a_col)]
            asd_value = row[a_col - min(f_col, a_col)]
            if isinstance(frequency_value, (int, float)) and isinstance(
                asd_value, (int, float)
            ):
                rows.append((float(frequency_value), float(asd_value)))
        parsed_candidates.append(
            (
                worksheet.title == "PSD_ASD",
                len(rows),
                worksheet.title,
                header_row,
                f_header,
                a_header,
                rows,
            )
        )

    _, _, sheet_name, header_row, f_header, a_header, rows = max(
        parsed_candidates, key=lambda item: (item[0], item[1])
    )
    frequency = np.asarray([row[0] for row in rows], dtype=float)
    asd = np.asarray([row[1] for row in rows], dtype=float)
    errors, validation_notes = validate_arrays(frequency, asd)
    units = (
        "m s^-2 Hz^-1/2"
        if "mps2" in header_key(a_header) and "sqrt_hz" in header_key(a_header)
        else "not explicit"
    )
    return Spectrum(
        path=path,
        frequency_hz=frequency,
        asd_mps2_per_sqrt_hz=asd,
        frequency_header=f_header,
        asd_header=a_header,
        units=units,
        parsing_note=f"Excel worksheet '{sheet_name}', header row {header_row}",
        exported_utc=exported_utc,
        validation_errors=errors,
        validation_warnings=validation_notes,
    )


def extract_text_spectrum(path: Path) -> Spectrum:
    if path.suffix.lower() == ".tsv":
        frame = pd.read_csv(path, sep="\t")
    else:
        frame = pd.read_csv(path, sep=None, engine="python")
    keys = {column: header_key(column) for column in frame.columns}
    frequency_columns = [
        column
        for column, key in keys.items()
        if FREQUENCY_HEADER_TOKEN in key and "hz" in key
    ]
    asd_columns = [
        column
        for column, key in keys.items()
        if ASD_HEADER_TOKEN in key and "spectral" in key
    ]
    if len(frequency_columns) != 1 or len(asd_columns) != 1:
        raise ValueError("text table does not contain one unambiguous frequency/ASD pair")
    f_header = frequency_columns[0]
    a_header = asd_columns[0]
    numeric = frame[[f_header, a_header]].apply(pd.to_numeric, errors="coerce").dropna()
    frequency = numeric[f_header].to_numpy(dtype=float)
    asd = numeric[a_header].to_numpy(dtype=float)
    errors, validation_notes = validate_arrays(frequency, asd)
    units = (
        "m s^-2 Hz^-1/2"
        if "mps2" in header_key(a_header) and "sqrt_hz" in header_key(a_header)
        else "not explicit"
    )
    return Spectrum(
        path=path,
        frequency_hz=frequency,
        asd_mps2_per_sqrt_hz=asd,
        frequency_header=str(f_header),
        asd_header=str(a_header),
        units=units,
        parsing_note=f"Delimited text parsed with pandas ({path.suffix.lower()})",
        exported_utc="",
        validation_errors=errors,
        validation_warnings=validation_notes,
    )


def extract_spectrum(path: Path) -> Spectrum:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return extract_excel_spectrum(path)
    return extract_text_spectrum(path)


def discover_files(source_root: Path) -> list[Path]:
    return sorted(
        path
        for path in source_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in VALID_EXTENSIONS
        and not path.name.startswith("~$")
    )


def frequency_grid_matches(first: Spectrum, second: Spectrum) -> bool:
    return first.n_points == second.n_points and np.allclose(
        first.frequency_hz, second.frequency_hz, rtol=0, atol=1e-9
    )


def band_rms(spectrum: Spectrum, low_hz: float, high_hz: float) -> tuple[float, str]:
    mask = (spectrum.frequency_hz >= low_hz) & (spectrum.frequency_hz <= high_hz)
    frequency = spectrum.frequency_hz[mask]
    asd = spectrum.asd_mps2_per_sqrt_hz[mask]
    if len(frequency) < 2:
        return float("nan"), "insufficient bins"
    spacing = np.diff(frequency)
    if np.allclose(spacing, np.median(spacing), rtol=1e-6, atol=1e-9):
        result = float(np.sqrt(np.sum(np.square(asd)) * np.median(spacing)))
        method = "uniform-bin sum"
    else:
        result = float(np.sqrt(np.trapezoid(np.square(asd), frequency)))
        method = "trapezoidal integration"
    return result, method


def nearest_asd(spectrum: Spectrum, target_hz: float) -> tuple[float, float]:
    index = int(np.argmin(np.abs(spectrum.frequency_hz - target_hz)))
    return (
        float(spectrum.frequency_hz[index]),
        float(spectrum.asd_mps2_per_sqrt_hz[index]),
    )


def safe_ratio(off_value: float, on_value: float) -> tuple[float, float, float]:
    ratio = off_value / on_value
    reduction = 100.0 * (1.0 - ratio)
    db_change = 20.0 * math.log10(ratio)
    return ratio, reduction, db_change


def tex_escape(text: str) -> str:
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
    return "".join(replacements.get(character, character) for character in text)


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def configure_plot_style() -> None:
    plt.rcParams.update(
        {
            "font.size": 8.2,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.bbox": "tight",
        }
    )


def common_log_limits(pairs: list[Pair], percentile_floor: float = 0.2) -> tuple[float, float]:
    positive = np.concatenate(
        [
            array[array > 0]
            for pair in pairs
            for array in (
                pair.on.asd_mps2_per_sqrt_hz,
                pair.off.asd_mps2_per_sqrt_hz,
            )
        ]
    )
    low = 10 ** math.floor(math.log10(float(np.percentile(positive, percentile_floor))))
    high = 10 ** math.ceil(math.log10(float(np.max(positive))))
    return low, high


def draw_state(
    ax: plt.Axes,
    spectrum: Spectrum,
    color: str,
    ylim: tuple[float, float],
    location_label: str,
    show_signature_labels: bool = False,
) -> None:
    ax.plot(
        spectrum.frequency_hz,
        spectrum.asd_mps2_per_sqrt_hz,
        color=color,
        lw=1.05,
        zorder=3,
    )
    ax.set_yscale("log")
    ax.set_xlim(*PLOT_FREQUENCY_RANGE_HZ)
    ax.set_ylim(*ylim)
    ax.set_xticks([20, 40, 60, 80, 100, 120, 140, 160])
    ax.grid(True, which="major", color="#D5DCE5", alpha=0.85, lw=0.5)
    ax.axvline(
        29.8, color=SIGNATURE_COLOR, ls=(0, (4, 2)), lw=0.85, alpha=0.85, zorder=1
    )
    ax.axvspan(98.0, 102.3, color=SIGNATURE_COLOR, alpha=0.055, lw=0, zorder=0)
    ax.axvline(
        119.7, color=SIGNATURE_COLOR, ls=(0, (4, 2)), lw=0.85, alpha=0.85, zorder=1
    )
    ax.text(
        0.015,
        0.80,
        location_label,
        transform=ax.transAxes,
        color=NAVY,
        fontweight="bold",
        fontsize=8.5,
        va="top",
    )
    if show_signature_labels:
        transform = ax.get_xaxis_transform()
        ax.text(
            30.7,
            0.96,
            "29.8 Hz",
            transform=transform,
            color=SIGNATURE_COLOR,
            fontsize=6.8,
            va="top",
        )
        ax.text(
            100.1,
            0.96,
            "98.7-101.7",
            transform=transform,
            color=SIGNATURE_COLOR,
            fontsize=6.8,
            ha="center",
            va="top",
        )
        ax.text(
            120.5,
            0.96,
            "120 Hz",
            transform=transform,
            color=SIGNATURE_COLOR,
            fontsize=6.8,
            va="top",
        )


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f"{stem}.pdf")
    fig.savefig(output_dir / f"{stem}.png", dpi=260)
    plt.close(fig)


def plot_laboratories(pair_by_key: dict[str, Pair], output_dir: Path) -> None:
    pairs = [pair_by_key[key] for key in LAB_ORDER if key in pair_by_key]
    ylim = common_log_limits(pairs)
    fig, axes = plt.subplots(
        len(pairs), 2, figsize=(7.2, 6.1), sharex=True, sharey=True
    )
    for row, pair in enumerate(pairs):
        draw_state(
            axes[row, 0],
            pair.on,
            ON_COLOR,
            ylim,
            pair.display_location,
            show_signature_labels=row == 0,
        )
        draw_state(
            axes[row, 1],
            pair.off,
            OFF_COLOR,
            ylim,
            pair.display_location,
            show_signature_labels=row == 0,
        )
        axes[row, 1].tick_params(axis="y", labelleft=False)
    fig.text(
        0.5,
        0.993,
        "Physics floor spectra: turbine operating versus shut down",
        ha="center",
        va="top",
        color=NAVY,
        fontsize=13,
        fontweight="bold",
    )
    fig.text(
        0.315,
        0.945,
        "Turbine operating",
        ha="center",
        va="top",
        color=ON_COLOR,
        fontsize=10,
        fontweight="bold",
    )
    fig.text(
        0.755,
        0.945,
        "Turbine shut down",
        ha="center",
        va="top",
        color=OFF_COLOR,
        fontsize=10,
        fontweight="bold",
    )
    fig.supxlabel("Frequency (Hz)", y=0.018)
    fig.supylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)", x=0.02)
    fig.tight_layout(rect=[0.055, 0.052, 1, 0.905], h_pad=0.55, w_pad=0.7)
    save_figure(fig, output_dir, "laboratory_turbine_comparison")


def plot_source_path(pair_by_key: dict[str, Pair], output_dir: Path) -> None:
    pairs = [pair_by_key[key] for key in SOURCE_ORDER if key in pair_by_key]
    ylim = common_log_limits(pairs)
    fig, axes = plt.subplots(
        len(pairs), 2, figsize=(7.2, 5.1), sharex=True, sharey=True
    )
    for row, pair in enumerate(pairs):
        draw_state(
            axes[row, 0],
            pair.on,
            ON_COLOR,
            ylim,
            pair.display_location,
            show_signature_labels=row == 0,
        )
        draw_state(
            axes[row, 1],
            pair.off,
            OFF_COLOR,
            ylim,
            pair.display_location,
            show_signature_labels=row == 0,
        )
        axes[row, 1].tick_params(axis="y", labelleft=False)
    fig.text(
        0.5,
        0.993,
        "Source-to-building path: turbine operating versus shut down",
        ha="center",
        va="top",
        color=NAVY,
        fontsize=13,
        fontweight="bold",
    )
    fig.text(
        0.315,
        0.938,
        "Turbine operating",
        ha="center",
        va="top",
        color=ON_COLOR,
        fontsize=10,
        fontweight="bold",
    )
    fig.text(
        0.755,
        0.938,
        "Turbine shut down",
        ha="center",
        va="top",
        color=OFF_COLOR,
        fontsize=10,
        fontweight="bold",
    )
    fig.supxlabel("Frequency (Hz)", y=0.018)
    fig.supylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)", x=0.02)
    fig.tight_layout(rect=[0.055, 0.06, 1, 0.89], h_pad=0.7, w_pad=0.7)
    save_figure(fig, output_dir, "source_path_turbine_comparison")


def plot_freezer_herzog_comparison(
    pair_by_key: dict[str, Pair], output_dir: Path
) -> None:
    """Compare turbine-off spectra on the Herzog floor and freezer top."""
    floor = pair_by_key["herzogfloor"].off
    freezer = pair_by_key["herzogtopofultracold"].off
    spectra = (floor, freezer)
    positive = np.concatenate(
        [
            spectrum.asd_mps2_per_sqrt_hz[
                (spectrum.frequency_hz >= PLOT_FREQUENCY_RANGE_HZ[0])
                & (spectrum.frequency_hz <= PLOT_FREQUENCY_RANGE_HZ[1])
                & (spectrum.asd_mps2_per_sqrt_hz > 0)
            ]
            for spectrum in spectra
        ]
    )
    ylim = (
        10 ** math.floor(math.log10(float(np.percentile(positive, 0.2)))),
        10 ** math.ceil(math.log10(float(np.max(positive)))),
    )

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.plot(
        floor.frequency_hz,
        floor.asd_mps2_per_sqrt_hz,
        color=OFF_COLOR,
        lw=1.25,
        label="Herzog floor - turbine off",
        zorder=3,
    )
    ax.plot(
        freezer.frequency_hz,
        freezer.asd_mps2_per_sqrt_hz,
        color=FREEZER_COLOR,
        lw=1.1,
        label="Ultra-cold freezer top - turbine off",
        zorder=2,
    )
    ax.set_yscale("log")
    ax.set_xlim(*PLOT_FREQUENCY_RANGE_HZ)
    ax.set_ylim(*ylim)
    ax.set_xticks([20, 40, 60, 80, 100, 120, 140, 160])
    ax.grid(True, which="major", color="#D5DCE5", alpha=0.85, lw=0.5)
    for frequency, label in ((60.0, "60 Hz"), (120.0, "120 Hz")):
        ax.axvline(
            frequency,
            color=SIGNATURE_COLOR,
            ls=(0, (4, 2)),
            lw=0.95,
            alpha=0.9,
            zorder=1,
        )
        ax.text(
            frequency + 1.0,
            0.965,
            label,
            transform=ax.get_xaxis_transform(),
            color=SIGNATURE_COLOR,
            fontsize=7.4,
            va="top",
        )
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel(r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)")
    fig.suptitle(
        "Persistent Herzog 120 Hz vibration during turbine shutdown",
        color=NAVY,
        fontsize=12.5,
        fontweight="bold",
        y=0.995,
    )
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=2,
        frameon=True,
        framealpha=0.94,
        edgecolor="#C7CED8",
        fontsize=8.1,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.84])
    save_figure(fig, output_dir, "herzog_freezer_shutdown_comparison")


def build_analysis(source_root: Path, output_root: Path) -> None:
    figures_dir = output_root / "figures"
    results_dir = output_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    candidate_files = discover_files(source_root)
    extracted: dict[Path, Spectrum] = {}
    extraction_failures: dict[Path, str] = {}
    for path in candidate_files:
        try:
            extracted[path] = extract_spectrum(path)
        except Exception as exc:
            extraction_failures[path] = f"{type(exc).__name__}: {exc}"

    on_by_key: dict[str, list[Path]] = {}
    off_by_key: dict[str, list[Path]] = {}
    for path in candidate_files:
        key, is_off = normalized_key(path)
        target = off_by_key if is_off else on_by_key
        target.setdefault(key, []).append(path)

    all_keys = sorted(set(on_by_key) | set(off_by_key))
    manifest_rows: list[dict] = []
    pairs: list[Pair] = []
    for key in all_keys:
        on_paths = on_by_key.get(key, [])
        off_paths = off_by_key.get(key, [])
        representative_path = (on_paths or off_paths)[0]
        display, category, primary = display_metadata(key, representative_path)

        on_path = on_paths[0] if len(on_paths) == 1 else None
        off_path = off_paths[0] if len(off_paths) == 1 else None
        reason = ""
        included = False
        matching_note = f"case-insensitive normalized key '{key}'"
        if len(on_paths) != 1:
            reason = (
                "no turbine-on spectrum"
                if not on_paths
                else "ambiguous: multiple turbine-on candidates"
            )
        elif len(off_paths) != 1:
            reason = (
                "no paired turbine-shutdown spectrum"
                if not off_paths
                else "ambiguous: multiple turbine-shutdown candidates"
            )
        elif on_path in extraction_failures:
            reason = f"turbine-on parsing failed: {extraction_failures[on_path]}"
        elif off_path in extraction_failures:
            reason = f"turbine-off parsing failed: {extraction_failures[off_path]}"
        else:
            on_spectrum = extracted[on_path]
            off_spectrum = extracted[off_path]
            if not on_spectrum.valid:
                reason = "turbine-on validation failed: " + "; ".join(
                    on_spectrum.validation_errors
                )
            elif not off_spectrum.valid:
                reason = "turbine-off validation failed: " + "; ".join(
                    off_spectrum.validation_errors
                )
            else:
                included = True
                pair = Pair(
                    key=key,
                    display_location=display,
                    category=category,
                    primary=primary,
                    on=on_spectrum,
                    off=off_spectrum,
                )
                pairs.append(pair)
                matching_note += (
                    "; pairing confirmed by identical headers, compatible ranges, "
                    "point counts, and frequency grids"
                )

        on_spectrum = extracted.get(on_path) if on_path else None
        off_spectrum = extracted.get(off_path) if off_path else None
        grid_match = (
            frequency_grid_matches(on_spectrum, off_spectrum)
            if on_spectrum and off_spectrum and on_spectrum.valid and off_spectrum.valid
            else ""
        )
        manifest_rows.append(
            {
                "display_location": display,
                "category": category,
                "normalized_pair_key": key,
                "turbine_on_source_filename": on_path.name if on_path else "",
                "turbine_off_source_filename": off_path.name if off_path else "",
                "included_in_paired_analysis": included,
                "reason_for_exclusion": reason,
                "on_points": on_spectrum.n_points if on_spectrum else "",
                "off_points": off_spectrum.n_points if off_spectrum else "",
                "on_frequency_min_hz": (
                    on_spectrum.min_frequency_hz if on_spectrum else ""
                ),
                "on_frequency_max_hz": (
                    on_spectrum.max_frequency_hz if on_spectrum else ""
                ),
                "off_frequency_min_hz": (
                    off_spectrum.min_frequency_hz if off_spectrum else ""
                ),
                "off_frequency_max_hz": (
                    off_spectrum.max_frequency_hz if off_spectrum else ""
                ),
                "on_bin_width_hz": on_spectrum.bin_width_hz if on_spectrum else "",
                "off_bin_width_hz": off_spectrum.bin_width_hz if off_spectrum else "",
                "frequency_grids_identical": grid_match,
                "on_frequency_column": (
                    on_spectrum.frequency_header if on_spectrum else ""
                ),
                "on_asd_column": on_spectrum.asd_header if on_spectrum else "",
                "off_frequency_column": (
                    off_spectrum.frequency_header if off_spectrum else ""
                ),
                "off_asd_column": off_spectrum.asd_header if off_spectrum else "",
                "units": (
                    on_spectrum.units
                    if on_spectrum
                    else off_spectrum.units if off_spectrum else ""
                ),
                "on_exported_utc": on_spectrum.exported_utc if on_spectrum else "",
                "off_exported_utc": off_spectrum.exported_utc if off_spectrum else "",
                "validation_notes": "; ".join(
                    (on_spectrum.validation_warnings if on_spectrum else [])
                    + (off_spectrum.validation_warnings if off_spectrum else [])
                ),
                "on_parsing_notes": (
                    on_spectrum.parsing_note if on_spectrum else ""
                ),
                "off_parsing_notes": (
                    off_spectrum.parsing_note if off_spectrum else ""
                ),
                "parsing_and_matching_notes": matching_note,
            }
        )

    manifest_fields = list(manifest_rows[0].keys())
    write_csv(results_dir / "data_manifest.csv", manifest_rows, manifest_fields)

    metrics_rows: list[dict] = []
    line_rows: list[dict] = []
    for pair in sorted(pairs, key=lambda item: item.display_location):
        common_high = min(
            FULL_BAND[1], pair.on.max_frequency_hz, pair.off.max_frequency_hz
        )
        common_low = FULL_BAND[0]
        on_full, on_method = band_rms(pair.on, common_low, common_high)
        off_full, off_method = band_rms(pair.off, common_low, common_high)
        full_ratio, full_reduction, full_db = safe_ratio(off_full, on_full)

        mid_low = max(MID_BAND[0], pair.on.min_frequency_hz, pair.off.min_frequency_hz)
        mid_high = min(
            MID_BAND[1], pair.on.max_frequency_hz, pair.off.max_frequency_hz
        )
        on_mid, on_mid_method = band_rms(pair.on, mid_low, mid_high)
        off_mid, off_mid_method = band_rms(pair.off, mid_low, mid_high)
        mid_ratio, mid_reduction, mid_db = safe_ratio(off_mid, on_mid)

        row = {
            "display_location": pair.display_location,
            "normalized_pair_key": pair.key,
            "category": pair.category,
            "primary_report_pair": pair.primary,
            "turbine_on_source_filename": pair.on.path.name,
            "turbine_off_source_filename": pair.off.path.name,
            "common_band_low_hz": common_low,
            "common_band_high_hz": common_high,
            "on_full_band_rms_mps2": on_full,
            "off_full_band_rms_mps2": off_full,
            "off_on_full_band_rms_ratio": full_ratio,
            "full_band_percent_reduction": full_reduction,
            "full_band_db_change": full_db,
            "on_20_50_hz_rms_mps2": on_mid,
            "off_20_50_hz_rms_mps2": off_mid,
            "off_on_20_50_hz_rms_ratio": mid_ratio,
            "20_50_hz_percent_reduction": mid_reduction,
            "20_50_hz_db_change": mid_db,
            "on_integration_method": on_method,
            "off_integration_method": off_method,
            "on_20_50_integration_method": on_mid_method,
            "off_20_50_integration_method": off_mid_method,
            "notes": (
                "Native frequency grids used; nearest-bin line comparison. "
                "Negative percent reduction denotes an increase."
            ),
        }

        for target in LINE_FREQUENCIES_HZ:
            on_bin, on_asd = nearest_asd(pair.on, target)
            off_bin, off_asd = nearest_asd(pair.off, target)
            ratio, reduction, db_change = safe_ratio(off_asd, on_asd)
            label = str(target).replace(".", "p")
            row[f"line_{label}_on_bin_hz"] = on_bin
            row[f"line_{label}_off_bin_hz"] = off_bin
            row[f"line_{label}_on_asd_mps2_per_sqrt_hz"] = on_asd
            row[f"line_{label}_off_asd_mps2_per_sqrt_hz"] = off_asd
            row[f"line_{label}_off_on_asd_ratio"] = ratio
            row[f"line_{label}_percent_reduction"] = reduction
            row[f"line_{label}_db_change"] = db_change
            line_rows.append(
                {
                    "display_location": pair.display_location,
                    "normalized_pair_key": pair.key,
                    "category": pair.category,
                    "target_frequency_hz": target,
                    "on_nearest_bin_hz": on_bin,
                    "off_nearest_bin_hz": off_bin,
                    "on_asd_mps2_per_sqrt_hz": on_asd,
                    "off_asd_mps2_per_sqrt_hz": off_asd,
                    "off_on_asd_ratio": ratio,
                    "percent_reduction": reduction,
                    "db_change": db_change,
                    "comparison_method": "nearest native-frequency bin in each spectrum",
                    "turbine_on_source_filename": pair.on.path.name,
                    "turbine_off_source_filename": pair.off.path.name,
                }
            )
        metrics_rows.append(row)

    metrics_fields = list(metrics_rows[0].keys())
    line_fields = list(line_rows[0].keys())
    write_csv(
        results_dir / "turbine_shutdown_metrics.csv", metrics_rows, metrics_fields
    )
    write_csv(results_dir / "turbine_line_metrics.csv", line_rows, line_fields)

    metrics_by_key = {row["normalized_pair_key"]: row for row in metrics_rows}
    pair_by_key = {pair.key: pair for pair in pairs}

    configure_plot_style()
    plot_laboratories(pair_by_key, figures_dir)
    plot_source_path(pair_by_key, figures_dir)
    plot_freezer_herzog_comparison(pair_by_key, figures_dir)

    primary_rows = [metrics_by_key[key] for key in PRIMARY_ORDER if key in metrics_by_key]
    with (results_dir / "primary_metrics_table.tex").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write(
            "\\begin{tabular}{lrrrrr}\n"
            "\\toprule\n"
            "Location & \\multicolumn{2}{c}{Full-band RMS ($10^{-3}$ m s$^{-2}$)}"
            " & \\multicolumn{2}{c}{Reduction (\\%)} & 29.8 Hz \\\\\n"
            "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\n"
            " & On & Off & Full & 20--50 Hz & change (dB) \\\\\n"
            "\\midrule\n"
        )
        for row in primary_rows:
            stream.write(
                f"{tex_escape(str(row['display_location']))} & "
                f"{1000 * float(row['on_full_band_rms_mps2']):.3g} & "
                f"{1000 * float(row['off_full_band_rms_mps2']):.3g} & "
                f"{float(row['full_band_percent_reduction']):.1f} & "
                f"{float(row['20_50_hz_percent_reduction']):.1f} & "
                f"{float(row['line_29p8_db_change']):.1f} \\\\\n"
            )
        stream.write("\\bottomrule\n\\end{tabular}\n")

    line_labels = {
        29.8: "29.8",
        59.6: "59.6",
        98.7: "98.7",
        101.7: "101.7",
        119.7: "119.7",
    }
    line_key_order = [
        "pipefromheatingplant",
        "sidewalkbetweenheatingandphysics",
        "titanfloor",
        "herzogfloor",
        "244floor",
    ]
    line_lookup = {
        (row["normalized_pair_key"], float(row["target_frequency_hz"])): row
        for row in line_rows
    }
    with (results_dir / "line_evidence_table.tex").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write(
            "\\begin{tabular}{lrrrrr}\n"
            "\\toprule\n"
            "Line (Hz) & Pipe & Sidewalk & Titan & Herzog & PHYS 244 \\\\\n"
            "\\midrule\n"
        )
        for target in REPORT_LINE_FREQUENCIES_HZ:
            values = [
                float(line_lookup[(key, target)]["db_change"])
                for key in line_key_order
            ]
            stream.write(
                f"{line_labels[target]} & "
                + " & ".join(f"{value:.1f}" for value in values)
                + " \\\\\n"
            )
        stream.write("\\bottomrule\n\\end{tabular}\n")

    primary_reductions = [
        float(row["full_band_percent_reduction"]) for row in primary_rows
    ]
    all_reductions = [
        float(row["full_band_percent_reduction"]) for row in metrics_rows
    ]
    macro_values = {
        "NumCandidateLocations": len(manifest_rows),
        "NumValidPairs": len(pairs),
        "NumPrimaryPairs": len(primary_rows),
        "LargestPrimaryReduction": f"{max(primary_reductions):.1f}\\%",
        "SmallestPrimaryReduction": f"{min(primary_reductions):.1f}\\%",
        "LargestAllReduction": f"{max(all_reductions):.1f}\\%",
        "SmallestAllReduction": f"{min(all_reductions):.1f}\\%",
        "TitanFullReduction": (
            f"{metrics_by_key['titanfloor']['full_band_percent_reduction']:.1f}\\%"
        ),
        "HerzogFullReduction": (
            f"{metrics_by_key['herzogfloor']['full_band_percent_reduction']:.1f}\\%"
        ),
        "PhysTwoFortyFourFullReduction": (
            f"{metrics_by_key['244floor']['full_band_percent_reduction']:.1f}\\%"
        ),
        "PipeFullReduction": (
            f"{metrics_by_key['pipefromheatingplant']['full_band_percent_reduction']:.1f}\\%"
        ),
        "SidewalkFullReduction": (
            f"{metrics_by_key['sidewalkbetweenheatingandphysics']['full_band_percent_reduction']:.1f}\\%"
        ),
        "FreezerFullReduction": (
            f"{metrics_by_key['herzogtopofultracold']['full_band_percent_reduction']:.1f}\\%"
        ),
        "PipeTwentyNineDb": (
            f"{metrics_by_key['pipefromheatingplant']['line_29p8_db_change']:.1f}"
        ),
        "SidewalkTwentyNineDb": (
            f"{metrics_by_key['sidewalkbetweenheatingandphysics']['line_29p8_db_change']:.1f}"
        ),
        "TitanTwentyNineDb": (
            f"{metrics_by_key['titanfloor']['line_29p8_db_change']:.1f}"
        ),
        "HerzogTwentyNineDb": (
            f"{metrics_by_key['herzogfloor']['line_29p8_db_change']:.1f}"
        ),
        "PhysTwoFortyFourTwentyNineDb": (
            f"{metrics_by_key['244floor']['line_29p8_db_change']:.1f}"
        ),
    }
    with (results_dir / "analysis_macros.tex").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write("% Generated by analyze_turbine_shutdown.py\n")
        for name, value in macro_values.items():
            stream.write(f"\\newcommand{{\\{name}}}{{{value}}}\n")

    print(f"Inventoried {len(manifest_rows)} measurement locations.")
    print(f"Validated {len(pairs)} turbine-on/off pairs.")
    print(
        "Primary full-band RMS reduction range: "
        f"{min(primary_reductions):.1f}% to {max(primary_reductions):.1f}%."
    )
    print(f"Outputs written under: {output_root}")


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_output = script_path.parents[1]
    default_source = default_output.parent / "Manual Analysis"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=default_source,
        help="Read-only directory containing turbine-on and turbine-off spectra.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=default_output,
        help="Addendum output directory.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build_analysis(arguments.source_root.resolve(), arguments.output_root.resolve())
