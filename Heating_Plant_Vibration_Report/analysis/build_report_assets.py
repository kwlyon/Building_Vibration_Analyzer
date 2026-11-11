from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm


WORK_DIR = Path(
    r"C:\Users\kwlyon\.codex\visualizations\2026\07\24"
    r"\019f923a-5419-7092-902a-9a4aa6822fb4\manual_report_work"
)
STAGING_DIR = WORK_DIR / "staging"
FIGURE_DIR = STAGING_DIR / "figures"
ANALYSIS_DIR = STAGING_DIR / "analysis"

SPECTRA_JSON = WORK_DIR / "manual_spectra.json"
RESULTS_JSON = WORK_DIR / "analysis_results.json"

NAVY = "#17365D"
BLUE = "#2E75B6"
ORANGE = "#D55E00"
TEAL = "#00897B"
RED = "#A23B3B"
GRAY = "#6B7280"
LIGHT_GRAY = "#E5E7EB"

PLANT_LINES = [29.8149712212212, 98.731544044044, 101.664164164164, 119.993039914915]

ROOM_COLORS = {
    "Titan Lab": NAVY,
    "PHYS 245": ORANGE,
    "PHYS 244": TEAL,
    "PHYS 111": "#7A5195",
    "Herzog Lab": RED,
}

FLOOR_RUNS = [
    ("Titan Lab", "PHYS_TITAN_FLOOR"),
    ("PHYS 245", "PHYS_245_Floor"),
    ("PHYS 244", "PHYS_244_Floor"),
    ("PHYS 111", "PHYS_111_Floor"),
    ("Herzog Lab", "PHYS_Herzog_Floor"),
]

TABLE_RUNS = [
    ("Herzog (unfloated)", "PHYS_Herzog_Floor", "PHYS_Herzog_Optical_Table"),
    ("PHYS 111 far table", "PHYS_111_Floor", "PHYS_111_Far_Optical_Table"),
    (
        "PHYS 111 near door",
        "PHYS_111_Floor",
        "PHYS_111_Near_Door_Optical_Table",
    ),
    ("PHYS 244 rolling", "PHYS_244_Floor", "PHYS_244_Rolling_Table"),
    ("PHYS 245 unfloated", "PHYS_245_Floor", "PHYS_245_Unfloated_Table"),
    ("PHYS 245 floated", "PHYS_245_Floor", "PHYS_245_Floated_Table"),
]

BANDS = [
    ("2-10", 2.0, 10.0),
    ("10-20", 10.0, 20.0),
    ("20-50", 20.0, 50.0),
    ("50-100", 50.0, 100.0),
    ("100-200", 100.0, 200.0),
]


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#D9DEE5",
            "grid.alpha": 0.65,
            "grid.linewidth": 0.6,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def load_inputs() -> tuple[dict[str, dict[str, np.ndarray]], dict]:
    raw = json.loads(SPECTRA_JSON.read_text(encoding="utf-8"))
    spectra = {}
    for entry in raw["spectra"]:
        spectra[entry["location"]] = {
            "frequency": np.asarray(entry["frequencyHz"], dtype=float),
            "asd": np.asarray(entry["asd"], dtype=float),
            "metadata": entry["metadata"],
        }
    results = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    return spectra, results


def save_figure(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIGURE_DIR / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / f"{stem}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def add_common_frequency_marks(axis: plt.Axes, labels: bool = False) -> None:
    axis.axvline(PLANT_LINES[0], color=RED, linestyle="--", linewidth=0.9, alpha=0.75)
    axis.axvspan(98.0, 102.5, color=RED, alpha=0.07, linewidth=0)
    axis.axvline(PLANT_LINES[3], color=RED, linestyle="--", linewidth=0.9, alpha=0.75)
    if labels:
        top = axis.get_ylim()[1]
        axis.text(
            PLANT_LINES[0] + 1.0,
            top / 1.8,
            "29.8 Hz\nplant-coupled",
            color=RED,
            fontsize=8,
            va="top",
        )
        axis.text(
            100.2,
            top / 1.8,
            "98.7-101.7",
            color=RED,
            fontsize=8,
            ha="center",
            va="top",
        )
        axis.text(
            PLANT_LINES[3] + 1.0,
            top / 1.8,
            "120.0 Hz",
            color=RED,
            fontsize=8,
            va="top",
        )


def nearest_asd(run: dict[str, np.ndarray], target_hz: float) -> tuple[float, float]:
    index = int(np.argmin(np.abs(run["frequency"] - target_hz)))
    return float(run["frequency"][index]), float(run["asd"][index])


def band_rms(run: dict[str, np.ndarray], low_hz: float, high_hz: float) -> float:
    frequency = run["frequency"]
    asd = run["asd"]
    mask = (frequency >= low_hz) & (frequency < high_hz)
    df = float(np.median(np.diff(frequency)))
    return float(np.sqrt(np.sum(np.square(asd[mask])) * df))


def make_source_distance_figure(spectra: dict[str, dict[str, np.ndarray]]) -> None:
    runs = [
        ("Pipe leaving heating plant", "Pipe_From_Heating_Plant", RED),
        (
            "Sidewalk between plant and Physics",
            "Sidewalk_between_Heating_and_Physics",
            ORANGE,
        ),
        ("Greek Theater top step", "Greek_Theater_Top_Stair", BLUE),
        ("Mullins-Union courtyard", "Courtyard_between_Mullens_Union", GRAY),
    ]
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(7.25, 7.1),
        gridspec_kw={"height_ratios": [2.8, 1.25], "hspace": 0.32},
    )
    axis = axes[0]
    for label, location, color in runs:
        run = spectra[location]
        mask = (run["frequency"] >= 2.0) & (run["frequency"] <= 160.0)
        axis.semilogy(
            run["frequency"][mask],
            run["asd"][mask],
            color=color,
            linewidth=1.25,
            label=label,
        )
    axis.set_xlim(2, 160)
    axis.set_ylim(1.0e-4, 2.5e-1)
    axis.set_ylabel(r"Acceleration ASD ($m\,s^{-2}/\sqrt{Hz}$)")
    axis.set_title(
        "The same heating-plant-coupled 29.8 Hz line weakens with distance"
    )
    add_common_frequency_marks(axis, labels=True)
    axis.legend(loc="upper right", frameon=True, framealpha=0.95)

    amplitudes = [nearest_asd(spectra[location], 30.0)[1] for _, location, _ in runs]
    positions = np.arange(len(runs))
    axes[1].semilogy(
        positions,
        amplitudes,
        color=NAVY,
        marker="o",
        markersize=6,
        linewidth=1.4,
    )
    axes[1].set_xticks(
        positions,
        ["Pipe", "Sidewalk", "Greek\nTheater", "Courtyard"],
    )
    axes[1].set_ylim(1.5e-4, 4.0e-1)
    axes[1].set_ylabel(r"ASD of same 29.8 Hz line")
    axes[1].set_title(
        "Same 29.8 Hz line: amplitude falls with distance from the heating plant"
    )
    reference = amplitudes[0]
    for position, amplitude in zip(positions, amplitudes):
        relative_db = 20.0 * math.log10(amplitude / reference)
        axes[1].annotate(
            f"{amplitude:.2g}\n{relative_db:+.0f} dB",
            (position, amplitude),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=NAVY,
        )
    fig.suptitle(
        "Near-source and control measurements",
        fontsize=14,
        fontweight="bold",
        color=NAVY,
        y=0.99,
    )
    save_figure(fig, "source_distance_evidence")


def make_floor_figure(spectra: dict[str, dict[str, np.ndarray]]) -> None:
    fig, axes = plt.subplots(
        len(FLOOR_RUNS),
        1,
        figsize=(7.25, 9.2),
        sharex=True,
        sharey=True,
        gridspec_kw={"hspace": 0.12},
    )
    for index, (room, location) in enumerate(FLOOR_RUNS):
        run = spectra[location]
        mask = (run["frequency"] >= 2.0) & (run["frequency"] <= 160.0)
        axes[index].semilogy(
            run["frequency"][mask],
            run["asd"][mask],
            color=ROOM_COLORS[room],
            linewidth=1.2,
        )
        axes[index].set_ylim(1.0e-4, 5.0e-2)
        axes[index].set_xlim(2, 160)
        axes[index].text(
            0.012,
            0.86,
            room,
            transform=axes[index].transAxes,
            color=ROOM_COLORS[room],
            fontsize=10,
            fontweight="bold",
            va="top",
        )
        add_common_frequency_marks(axes[index], labels=index == 0)
        axes[index].set_ylabel("ASD")
    axes[-1].set_xlabel("Frequency (Hz)")
    fig.suptitle(
        "Floor spectra in the measured Physics rooms",
        fontsize=14,
        fontweight="bold",
        color=NAVY,
        y=0.995,
    )
    fig.text(
        0.5,
        0.005,
        "Red marks indicate the strongest heating-plant-associated frequencies.",
        ha="center",
        fontsize=8,
        color=GRAY,
    )
    save_figure(fig, "all_floor_spectra")


def make_room_choice_figure(results: dict) -> None:
    metrics = {row["room"]: row for row in results["floor_metrics"]}
    order = ["Titan Lab", "PHYS 245", "PHYS 244", "PHYS 111", "Herzog Lab"]
    colors = [ROOM_COLORS[room] for room in order]
    broadband = [
        1.0e3 * metrics[room]["rms_2_250_excluding_principal_plant_lines"]
        for room in order
    ]
    line_30 = [1.0e3 * metrics[room]["asd_30"] for room in order]
    y = np.arange(len(order))

    fig, axes = plt.subplots(1, 2, figsize=(7.25, 4.5), sharey=True)
    axes[0].barh(y, broadband, color=colors, alpha=0.9)
    axes[0].set_yticks(y, order)
    axes[0].invert_yaxis()
    axes[0].set_xlabel(r"RMS ($10^{-3}\ m\,s^{-2}$)")
    axes[0].set_title("Broadband after removing plant lines")
    for index, value in enumerate(broadband):
        axes[0].text(value + 0.05, index, f"{value:.2f}", va="center", fontsize=8)

    axes[1].barh(y, line_30, color=colors, alpha=0.9)
    axes[1].set_xlabel(r"ASD ($10^{-3}\ m\,s^{-2}/\sqrt{Hz}$)")
    axes[1].set_title("Same plant-coupled 29.8 Hz line")
    for index, value in enumerate(line_30):
        axes[1].text(value + 0.25, index, f"{value:.2f}", va="center", fontsize=8)
    axes[1].set_xlim(0, max(line_30) * 1.23)

    fig.suptitle(
        "Titan has the lowest background, but not the smallest plant-coupled 29.8 Hz line",
        fontsize=13,
        fontweight="bold",
        color=NAVY,
        y=0.99,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save_figure(fig, "room_choice_context")


def make_optical_table_figure(
    spectra: dict[str, dict[str, np.ndarray]], results: dict
) -> None:
    labels = [entry[0] for entry in TABLE_RUNS]
    at_30 = {
        row["label"]: row["attenuation_db"] for row in results["table_metrics"]
    }
    result_label_map = {
        "Herzog (unfloated)": "Herzog optical table",
        "PHYS 111 far table": "PHYS 111 far optical table",
        "PHYS 111 near door": "PHYS 111 near-door optical table",
        "PHYS 244 rolling": "PHYS 244 rolling table",
        "PHYS 245 unfloated": "PHYS 245 unfloated table",
        "PHYS 245 floated": "PHYS 245 floated table",
    }
    attenuation_30 = np.array([at_30[result_label_map[label]] for label in labels])

    heatmap = np.zeros((len(TABLE_RUNS), len(BANDS)))
    for row_index, (_, floor_name, table_name) in enumerate(TABLE_RUNS):
        for column_index, (_, low_hz, high_hz) in enumerate(BANDS):
            floor_rms = band_rms(spectra[floor_name], low_hz, high_hz)
            table_rms = band_rms(spectra[table_name], low_hz, high_hz)
            heatmap[row_index, column_index] = 20.0 * math.log10(table_rms / floor_rms)

    fig = plt.figure(figsize=(7.25, 7.0))
    grid = fig.add_gridspec(2, 1, height_ratios=[1.4, 1.6], hspace=0.42)
    axis = fig.add_subplot(grid[0])
    positions = np.arange(len(labels))
    colors = [BLUE if value < 0 else ORANGE for value in attenuation_30]
    axis.barh(positions, attenuation_30, color=colors)
    axis.axvline(0, color="#333333", linewidth=0.9)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlabel("Table / floor change of the plant-coupled 29.8 Hz line (dB)")
    axis.set_title("Negative values are attenuation; positive values are amplification")
    limit = max(16.0, float(np.max(np.abs(attenuation_30))) + 2.0)
    axis.set_xlim(-limit, limit)
    for position, value in zip(positions, attenuation_30):
        axis.text(
            value + (0.35 if value >= 0 else -0.35),
            position,
            f"{value:+.1f}",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=8,
        )

    heat_axis = fig.add_subplot(grid[1])
    norm = TwoSlopeNorm(vmin=-15, vcenter=0, vmax=15)
    image = heat_axis.imshow(heatmap, aspect="auto", cmap="RdBu_r", norm=norm)
    heat_axis.set_yticks(np.arange(len(labels)), labels)
    heat_axis.set_xticks(np.arange(len(BANDS)), [band[0] for band in BANDS])
    heat_axis.set_xlabel("Frequency band (Hz)")
    heat_axis.set_title("Band-integrated RMS change (dB)")
    for row_index in range(heatmap.shape[0]):
        for column_index in range(heatmap.shape[1]):
            value = heatmap[row_index, column_index]
            heat_axis.text(
                column_index,
                row_index,
                f"{value:+.1f}",
                ha="center",
                va="center",
                color="white" if abs(value) > 8 else "#222222",
                fontsize=8,
            )
    colorbar = fig.colorbar(image, ax=heat_axis, fraction=0.035, pad=0.025)
    colorbar.set_label("Table / floor change (dB)")
    fig.suptitle(
        "Measured optical-table performance",
        fontsize=14,
        fontweight="bold",
        color=NAVY,
        y=0.995,
    )
    save_figure(fig, "optical_table_performance")


def make_herzog_figure(
    spectra: dict[str, dict[str, np.ndarray]], results: dict
) -> None:
    floor = spectra["PHYS_Herzog_Floor"]
    table = spectra["PHYS_Herzog_Optical_Table"]
    fig, axis = plt.subplots(figsize=(7.25, 4.5))
    for run, label, color in [
        (floor, "Herzog floor", ORANGE),
        (table, "Herzog optical table (not floated)", BLUE),
    ]:
        mask = (run["frequency"] >= 2.0) & (run["frequency"] <= 160.0)
        axis.semilogy(
            run["frequency"][mask],
            run["asd"][mask],
            color=color,
            linewidth=1.35,
            label=label,
        )
    axis.set_xlim(2, 160)
    axis.set_ylim(1.0e-4, 5.0e-2)
    axis.set_xlabel("Frequency (Hz)")
    axis.set_ylabel(r"Acceleration ASD ($m\,s^{-2}/\sqrt{Hz}$)")
    axis.set_title(
        "The Herzog table attenuates but does not remove the plant-coupled 29.8 Hz line"
    )
    add_common_frequency_marks(axis, labels=True)
    axis.legend(loc="upper right", frameon=True)

    herzog_result = next(
        row
        for row in results["table_metrics"]
        if row["label"] == "Herzog optical table"
    )
    axis.annotate(
        f"{herzog_result['attenuation_db']:+.1f} dB for the same 29.8 Hz line",
        xy=(herzog_result["frequency_hz"], herzog_result["table_asd"]),
        xytext=(46, 1.1e-2),
        arrowprops={"arrowstyle": "->", "color": NAVY, "linewidth": 1.0},
        color=NAVY,
        fontsize=9,
    )
    fig.tight_layout()
    save_figure(fig, "herzog_floor_vs_table")


def write_analysis_tables(results: dict) -> None:
    shutil.copy2(SPECTRA_JSON, ANALYSIS_DIR / "manual_spectra.json")
    shutil.copy2(RESULTS_JSON, ANALYSIS_DIR / "analysis_results.json")

    principal = [29.8149712212212, 98.731544044044, 101.664164164164, 119.993039914915]
    rows = []
    for center in principal:
        candidate = min(
            results["plant_peak_candidates"],
            key=lambda row: abs(row["frequency_hz"] - center),
        )
        rows.append(
            {
                "frequency_hz": candidate["frequency_hz"],
                "pipe_asd": candidate["Pipe"]["asd"],
                "sidewalk_asd": candidate["Sidewalk"]["asd"],
                "greek_theater_asd": candidate["Greek theater"]["asd"],
                "courtyard_asd": candidate["Courtyard"]["asd"],
                "herzog_floor_asd": candidate["Herzog floor"]["asd"],
                "phys111_floor_asd": candidate["PHYS 111 floor"]["asd"],
                "titan_floor_asd": candidate["Titan floor"]["asd"],
                "phys245_floor_asd": candidate["PHYS 245 floor"]["asd"],
                "phys244_floor_asd": candidate["PHYS 244 floor"]["asd"],
            }
        )
    with (ANALYSIS_DIR / "heating_plant_peak_table.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    with (ANALYSIS_DIR / "room_metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(results["floor_metrics"][0])
        )
        writer.writeheader()
        writer.writerows(results["floor_metrics"])

    with (ANALYSIS_DIR / "optical_table_metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(results["table_metrics"][0])
        )
        writer.writeheader()
        writer.writerows(results["table_metrics"])

    metadata = {
        "method": (
            "Welch acceleration ASD values were read from each workbook's PSD_ASD "
            "worksheet. Peaks were detected from the numerical ASD, and frequencies "
            "below 2 Hz were excluded."
        ),
        "principal_heating_plant_lines_hz": principal,
        "source_limitations": (
            "The plant building could not be measured directly because temporary "
            "generators were operating outside. Pipe and sidewalk measurements are "
            "near-source proxies; turbine attribution also uses the reported timing."
        ),
    }
    (ANALYSIS_DIR / "analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    configure_style()
    spectra, results = load_inputs()
    make_source_distance_figure(spectra)
    make_floor_figure(spectra)
    make_room_choice_figure(results)
    make_optical_table_figure(spectra, results)
    make_herzog_figure(spectra, results)
    write_analysis_tables(results)
    print(f"Wrote figures to {FIGURE_DIR}")
    print(f"Wrote analysis tables to {ANALYSIS_DIR}")


if __name__ == "__main__":
    main()
