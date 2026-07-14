from __future__ import annotations

from pathlib import Path
from html import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from .analysis import DEFAULT_BUILDING_BANDS, band_rms_from_psd, fft_amplitude, summary_statistics, welch_psd
from .csv_log import Session, samples_to_arrays


def generate_html_report(session: Session, path: str | Path, notes: str = "") -> None:
    t, data = samples_to_arrays(session.samples)
    fs = session.sample_rate_hz or 1.0
    stats = {axis: summary_statistics(values) for axis, values in data.items() if axis != "magnitude"}
    freq, psd = welch_psd(data["z"], fs, fft_length=min(1024, len(data["z"])))
    bands = {name: band_rms_from_psd(freq, psd, band) for name, band in DEFAULT_BUILDING_BANDS.items()}
    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>Vibration Report</title></head><body>",
        f"<h1>Building Vibration Report - Session {escape(session.session_id)}</h1>",
        f"<p>Samples: {len(session.samples)}; duration: {session.duration_s:.3f} s; sample rate: {fs:.3f} Hz</p>",
        f"<h2>Notes</h2><p>{escape(notes)}</p>",
        "<h2>Summary Statistics</h2><table border='1'><tr><th>Axis</th><th>Mean</th><th>RMS</th><th>Peak</th><th>Peak-to-peak</th><th>Crest</th><th>Std</th></tr>",
    ]
    for axis, stat in stats.items():
        html.append(
            f"<tr><td>{axis}</td><td>{stat.mean:.6g}</td><td>{stat.rms:.6g}</td>"
            f"<td>{stat.peak:.6g}</td><td>{stat.peak_to_peak:.6g}</td>"
            f"<td>{stat.crest_factor:.6g}</td><td>{stat.std:.6g}</td></tr>"
        )
    html.append("</table><h2>Z-axis Band RMS</h2><ul>")
    for name, value in bands.items():
        html.append(f"<li>{escape(name)}: {value:.6g} m/s^2 RMS</li>")
    html.append("</ul></body></html>")
    Path(path).write_text("\n".join(html), encoding="utf-8")


def generate_pdf_report(session: Session, path: str | Path, notes: str = "") -> None:
    t, data = samples_to_arrays(session.samples)
    fs = session.sample_rate_hz or 1.0
    with PdfPages(path) as pdf:
        fig, ax = plt.subplots(figsize=(10, 5))
        for axis in ("x", "y", "z"):
            ax.plot(t, data[axis], label=axis.upper(), linewidth=0.8)
        ax.set_title(f"Time Domain - Session {session.session_id}")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Acceleration (m/s^2)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 5))
        freq, psd = welch_psd(data["z"], fs, fft_length=min(1024, len(data["z"])))
        ax.semilogy(freq, psd)
        ax.set_title("Z-axis PSD")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("(m/s^2)^2/Hz")
        ax.grid(True, which="both", alpha=0.3)
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.axis("off")
        stats = summary_statistics(data["z"])
        text = (
            f"Session: {session.session_id}\n"
            f"Samples: {len(session.samples)}\n"
            f"Duration: {session.duration_s:.3f} s\n"
            f"Sample rate: {fs:.3f} Hz\n"
            f"Z RMS: {stats.rms:.6g} m/s^2\n"
            f"Z peak: {stats.peak:.6g} m/s^2\n\n"
            f"Notes:\n{notes}"
        )
        ax.text(0.02, 0.95, text, va="top", family="monospace")
        pdf.savefig(fig)
        plt.close(fig)
