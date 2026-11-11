# Final building-vibration report

This directory contains a reproducible analysis of `../FinalReportData.xlsx`.
The source workbook is read only and is never modified or overwritten.

## Main outputs

- `report/Building_Vibration_Report.pdf` - compiled professional report
- `report/Building_Vibration_Report.tex` - main LaTeX source
- `analysis/analyze_vibration_data.py` - workbook extraction, analysis, table generation, and plotting
- `analysis/summary_metrics.csv` - metrics for all 15 measurement runs
- `analysis/room_ranking.csv` - representative-floor room ranking
- `analysis/measured_location_ranking.csv` - all eligible measured surfaces, excluding the freezer reference and questionable Titan entry
- `analysis/surface_attenuation_by_band.csv` - floor-to-table and floor-to-surface comparisons
- `analysis/extracted_data/` - one clean CSV spectrum per measurement run
- `figures/` - vector PDF figures and high-resolution PNG previews

## Python requirements

Python 3.10 or newer is recommended. Required packages:

```text
numpy
pandas
scipy
matplotlib
openpyxl
```

Install them in an existing environment if needed:

```powershell
python -m pip install numpy pandas scipy matplotlib openpyxl
```

## Regenerate the analysis

From `Final_Vibration_Report/analysis`:

```powershell
python analyze_vibration_data.py
```

Optional paths:

```powershell
python analyze_vibration_data.py `
  --workbook "C:\path\to\FinalReportData.xlsx" `
  --output-root "C:\path\to\Final_Vibration_Report"
```

The script detects runs from the workbook headers rather than assuming a fixed
number of runs per worksheet. It regenerates extracted CSV files, summary
tables, figures, and the LaTeX table fragments under `report/generated/`.

## Compile the LaTeX report

From `Final_Vibration_Report/report`:

```powershell
pdflatex -interaction=nonstopmode Building_Vibration_Report.tex
pdflatex -interaction=nonstopmode Building_Vibration_Report.tex
```

The final PDF is `report/Building_Vibration_Report.pdf`.

## Analysis conventions

- Numerical spectra are acceleration amplitude spectral density (ASD), labeled
  in the workbook as `m/s^2/sqrt(Hz)`.
- Band RMS acceleration is `sqrt(sum(ASD^2 * df))`.
- The primary room metric integrates the complete 0.5-250 Hz range.
- Table-to-floor amplitude changes use `20 log10(A_table/A_floor)`.
- No smoothing is applied to numerical metrics.
- The freezer-top run is a diagnostic source reference, not a candidate site.
- The Titan entry run is marked questionable and excluded from the
  representative room ranking.

## Important limitations

- Most locations have only one spectrum; there are no repeated trials for
  formal uncertainty estimates.
- Raw time records, acquisition duration, window, overlap, calibration
  uncertainty, and contemporaneous equipment states are not included.
- Optical-table float status is explicit only for the PHYS 245 floated and
  unfloated runs. Other "Optical Table" labels are reported without assuming
  flotation.
