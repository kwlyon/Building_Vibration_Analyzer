# Concise building-vibration report

This directory is a shorter companion to `Final_Vibration_Report`. The full
report and the source workbook remain unchanged.

## Main outputs

- `report/Simple_Building_Vibration_Report.pdf` - compiled concise report
- `report/Simple_Building_Vibration_Report.tex` - LaTeX source
- `analysis/analyze_simple_vibration.py` - numerical analysis and plotting
- `analysis/summary_metrics_simple.csv` - metrics for all numerical spectra
- `analysis/candidate_room_metrics.csv` - peak-centered candidate comparison
- `analysis/peaks_from_spectra.csv` - peaks detected from ASD data columns
- `analysis/freezer_peak_matches.csv` - freezer-reference matching decisions
- `figures/` - vector PDF figures and PNG previews

## Analysis conventions

- Spectra are read from the workbook's `frequency_hz` and
  `r_spectral_asd_mps2_per_sqrt_hz` columns.
- Peak lists already printed in the workbook are ignored.
- Frequencies below 2 Hz and the 58-62 Hz mains band are excluded from the
  peak and RMS comparisons.
- Peak detection uses unsmoothed ASD values.
- A 21-bin median filter in log ASD provides a separate broadband-background
  estimate so that narrow lines do not control the entire room comparison.
- Freezer adjustment is limited to matched, locally specific narrow lines.
  It uses log-linear interpolation over +/-1.5 Hz rather than direct spectral
  subtraction because simultaneous phase/coherence data are unavailable.

## Regenerate the analysis

From the `analysis` directory:

```powershell
python analyze_simple_vibration.py
```

## Compile the report

From the `report` directory:

```powershell
pdflatex -interaction=nonstopmode Simple_Building_Vibration_Report.tex
pdflatex -interaction=nonstopmode Simple_Building_Vibration_Report.tex
```

