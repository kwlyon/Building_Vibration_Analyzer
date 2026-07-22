from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import math
from xml.sax.saxutils import escape
import zipfile

from .analysis import (
    DEFAULT_BUILDING_BANDS,
    amplitude_spectral_density,
    band_rms_from_psd,
    dominant_frequencies,
    dynamic_resultant,
    fft_amplitude,
    root_sum_square_spectra,
    sum_power_spectra,
    welch_psd,
)
from .csv_log import Session, normalize_elapsed_window, sample_rate_from_samples, select_samples_by_elapsed, samples_to_arrays

BASE_AXES = ("x", "y", "z")
AXIS_LABELS = {
    "x": "X",
    "y": "Y",
    "z": "Z",
    "r_dynamic": "R dynamic",
    "r_spectral": "R spectral RSS",
}


def export_fft_workbook(
    session: Session,
    path: str | Path,
    window: str = "hann",
    time_window: tuple[float, float] | None = None,
    axes: tuple[str, ...] = ("x", "y", "z", "r_dynamic", "r_spectral"),
) -> None:
    """Export selected-session time and frequency data to a single .xlsx workbook."""
    normalized_window = normalize_elapsed_window(session, *time_window) if time_window else (0.0, session.duration_s)
    samples = select_samples_by_elapsed(session, *normalized_window)
    if len(samples) < 5:
        raise ValueError("selected time window must contain at least five samples for FFT export")
    fs = sample_rate_from_samples(samples)
    if fs is None or fs <= 0:
        raise ValueError("selected session does not have valid elapsed_us timing")

    t, data = samples_to_arrays(samples)
    data["r_dynamic"] = dynamic_resultant(data["x"], data["y"], data["z"])
    axes = _normalize_axes(axes)
    if not axes:
        raise ValueError("at least one export axis must be selected")

    nperseg = min(1024, len(samples))
    fft_by_axis = _fft_by_axis(data, fs, window, axes)
    psd_by_axis = _psd_by_axis(data, fs, window, nperseg, axes)
    asd_by_axis = {axis: (freq, amplitude_spectral_density(psd)) for axis, (freq, psd) in psd_by_axis.items()}

    summary_rows = _summary_rows(session, samples, fs, window, nperseg, fft_by_axis, psd_by_axis, normalized_window)
    time_rows = _time_rows(samples, t)
    fft_rows = _fft_rows(fft_by_axis)
    psd_rows = _psd_asd_rows(psd_by_axis, asd_by_axis)

    workbook = {
        "Summary": summary_rows,
        "Time_Data": time_rows,
        "FFT_Amplitude": fft_rows,
        "PSD_ASD": psd_rows,
    }
    _write_xlsx(Path(path), workbook)


def _normalize_axes(axes: tuple[str, ...]) -> tuple[str, ...]:
    normalized = []
    for axis in axes:
        key = axis.lower().strip()
        if key in ("r", "r_dynamic", "rdynamic", "r dynamic"):
            key = "r_dynamic"
        elif key in ("r_spectral", "r_rss", "rss", "r spectral", "r spectral rss", "resultant"):
            key = "r_spectral"
        if key in AXIS_LABELS and key not in normalized:
            normalized.append(key)
    return tuple(normalized)


def _fft_by_axis(data, fs, window, axes):
    fft_cache = {}

    def independent_fft(axis):
        if axis not in fft_cache:
            fft_cache[axis] = fft_amplitude(data[axis], fs, window=window)
        return fft_cache[axis]

    results = {}
    for axis in axes:
        if axis == "r_spectral":
            spectra = [independent_fft(base_axis) for base_axis in BASE_AXES]
            results[axis] = (spectra[0][0], root_sum_square_spectra(*(spectrum[1] for spectrum in spectra)))
        else:
            results[axis] = independent_fft(axis)
    return results


def _psd_by_axis(data, fs, window, nperseg, axes):
    psd_cache = {}

    def independent_psd(axis):
        if axis not in psd_cache:
            psd_cache[axis] = welch_psd(data[axis], fs, window=window, fft_length=nperseg)
        return psd_cache[axis]

    results = {}
    for axis in axes:
        if axis == "r_spectral":
            spectra = [independent_psd(base_axis) for base_axis in BASE_AXES]
            results[axis] = (spectra[0][0], sum_power_spectra(*(spectrum[1] for spectrum in spectra)))
        else:
            results[axis] = independent_psd(axis)
    return results


def _summary_rows(session, samples, fs, window, nperseg, fft_by_axis, psd_by_axis, time_window):
    rows = [
        ["Building Vibration Analyzer Frequency Export"],
        [],
        ["Exported UTC", datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")],
        ["Session ID", session.session_id],
        ["Full-session samples", len(session.samples)],
        ["Exported samples", len(samples)],
        ["Full-session duration (s)", session.duration_s],
        ["Analysis start (s)", time_window[0]],
        ["Analysis end (s)", time_window[1]],
        ["Analysis duration (s)", time_window[1] - time_window[0]],
        ["Estimated sample rate (Hz)", fs],
        ["Frequency resolution (Hz)", fs / len(samples) if samples else ""],
        ["FFT window", window],
        ["FFT amplitude units", "m/s^2 peak amplitude"],
        ["PSD units", "(m/s^2)^2/Hz"],
        ["ASD units", "m/s^2/sqrt(Hz)"],
        ["Welch nperseg", nperseg],
        ["Welch overlap", "50%"],
        ["Frequency bins exported", len(next(iter(fft_by_axis.values()))[0]) if fft_by_axis else 0],
        ["Exported axes", ", ".join(_axis_label(axis) for axis in fft_by_axis)],
        [],
        ["Dominant FFT Peaks"],
        ["Axis", "Frequency (Hz)", "Amplitude (m/s^2)"],
    ]
    for axis, (freq, amp) in fft_by_axis.items():
        for peak_freq, peak_amp in dominant_frequencies(freq, amp, count=5, min_frequency=0.5):
            rows.append([_axis_label(axis), peak_freq, peak_amp])

    rows.extend([[], ["Band RMS from Welch PSD"], ["Axis", "Band", "Low Hz", "High Hz", "RMS (m/s^2)"]])
    for axis, (freq, psd) in psd_by_axis.items():
        for band_name, band in DEFAULT_BUILDING_BANDS.items():
            rows.append([_axis_label(axis), band_name, band[0], band[1], band_rms_from_psd(freq, psd, band)])
    rows.extend(
        [
            [],
            ["Warnings"],
            ["Velocity/displacement are not exported here; use explicit low-frequency cutoffs before integrating acceleration."],
            ["Static gravity calibration does not provide traceable dynamic vibration calibration."],
        ]
    )
    return rows


def _axis_label(axis):
    return AXIS_LABELS.get(axis, axis.upper())


def _time_rows(samples, t):
    rows = [
        [
            "timestamp_iso8601",
            "elapsed_s",
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
    ]
    for elapsed_s, sample in zip(t, samples):
        rows.append(
            [
                sample.timestamp_iso8601,
                elapsed_s,
                sample.elapsed_us,
                sample.sample_number,
                sample.x_counts,
                sample.y_counts,
                sample.z_counts,
                sample.x_mps2,
                sample.y_mps2,
                sample.z_mps2,
                sample.temperature_c,
                sample.status_flags,
            ]
        )
    return rows


def _fft_rows(fft_by_axis):
    freq = next(iter(fft_by_axis.values()))[0]
    axes = tuple(fft_by_axis)
    rows = [["frequency_hz", *(f"{axis}_fft_mps2" for axis in axes)]]
    for i, f in enumerate(freq):
        rows.append([f, *(fft_by_axis[axis][1][i] for axis in axes)])
    return rows


def _psd_asd_rows(psd_by_axis, asd_by_axis):
    axes = tuple(psd_by_axis)
    freq = psd_by_axis[axes[0]][0]
    header = ["frequency_hz"]
    for axis in axes:
        header.extend([f"{axis}_psd_mps2_2_per_hz", f"{axis}_asd_mps2_per_sqrt_hz"])
    rows = [header]
    for i, f in enumerate(freq):
        row = [f]
        for axis in axes:
            row.extend([psd_by_axis[axis][1][i], asd_by_axis[axis][1][i]])
        rows.append(row)
    return rows


def _write_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types(len(sheets)))
        zf.writestr("_rels/.rels", _root_rels())
        zf.writestr("docProps/app.xml", _app_props())
        zf.writestr("docProps/core.xml", _core_props())
        zf.writestr("xl/workbook.xml", _workbook_xml(list(sheets)))
        zf.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(len(sheets)))
        zf.writestr("xl/styles.xml", _styles_xml())
        for index, rows in enumerate(sheets.values(), start=1):
            zf.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))


def _sheet_xml(rows: list[list[object]]) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r_index, row in enumerate(rows, start=1):
        parts.append(f'<row r="{r_index}">')
        for c_index, value in enumerate(row, start=1):
            if value is None:
                continue
            ref = f"{_column_name(c_index)}{r_index}"
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                parts.append(f'<c r="{ref}"><v>{float(value):.15g}</v></c>')
            else:
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        parts.append("</row>")
    parts.extend(["</sheetData>", "</worksheet>"])
    return "".join(parts)


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def _workbook_xml(names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets></workbook>"
    )


def _workbook_rels(sheet_count: int) -> str:
    rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for i in range(1, sheet_count + 1):
        rels.append(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
        )
    rels.append(
        f'<Relationship Id="rId{sheet_count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    )
    rels.append("</Relationships>")
    return "".join(rels)


def _content_types(sheet_count: int) -> str:
    overrides = [
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    overrides.extend(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{''.join(overrides)}</Types>"
    )


def _root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        "</styleSheet>"
    )


def _core_props() -> str:
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>Building Vibration Analyzer FFT Export</dc:title>"
        "<dc:creator>Building Vibration Analyzer</dc:creator>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _app_props() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Building Vibration Analyzer</Application>"
        "</Properties>"
    )
