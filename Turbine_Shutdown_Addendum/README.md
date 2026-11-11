# Turbine-shutdown addendum

This directory contains a concise, reproducible comparison of acceleration
ASD spectra measured while the neighboring heating-plant turbine was
operating and while it was shut down. The analysis tests the source
attribution of the 29.8 Hz feature and quantifies changes in full-band
(0.5-250 Hz), 20-50 Hz, and selected line amplitudes.

## Source directories

- Original report, read only:
  `../Measurment_Files_Physics/Final_Vibration_Report`
- Spectrum workbooks, read only:
  `../Manual Analysis`

All generated files remain under this `Turbine_Shutdown_Addendum` directory.
The compiled report uses only relative paths to its generated figures and
tables.

## Validated pairs

Eight turbine-on/off pairs passed header, unit, sample-count, frequency-grid,
monotonicity, finite-value, duplicate-bin, and nonnegative-ASD checks:

- Titan Lab floor
- Titan Lab entryway
- Herzog Lab floor
- Herzog optical table
- PHYS 244 floor
- Herzog ultra-cold freezer top (diagnostic equipment reference)
- Pipe leaving the heating plant
- Sidewalk between the heating plant and Physics

The report's primary figures and table use the three paired representative
floors plus the pipe and sidewalk. A third figure overlays the turbine-off
Herzog floor and ultra-cold-freezer-top spectra to investigate the persistent
indoor 120 Hz peak. Supplementary valid pairs are retained in the
machine-readable metrics.

The report figures place turbine-operating and shutdown spectra in adjacent
panels rather than overlaying them. Both states use solid traces, identical
logarithmic y-scales, and a focused 15-160 Hz display range so disappearance
of the 29.8 Hz, 98.7-101.7 Hz, and approximately 120 Hz signatures is directly
visible. The source-path figure shows that the external 120 Hz component is
absent during shutdown, while the freezer comparison shows that a separate
120 Hz peak remains in Herzog and aligns with the operating freezer spectrum.
Full-band numerical metrics continue to use 0.5-250 Hz.

PHYS 111 and PHYS 245 were omitted from the laboratory comparison because
neither representative floor has a turbine-shutdown counterpart. No PHYS 244
data were substituted for PHYS 245.

The remaining turbine-on workbooks are excluded from paired analysis because
no matching shutdown workbook exists. These include the other PHYS 111,
PHYS 244, PHYS 245, and Herzog surfaces, plus the cooling-tower, courtyard,
and Greek Theater measurements. The complete filename-level inventory and
reason for every exclusion are recorded in `results/data_manifest.csv`.

## Outputs

- `main.tex` - styled LaTeX report source
- `Turbine_Shutdown_Addendum.pdf` - compiled addendum
- `analysis/analyze_turbine_shutdown.py` - pairing, validation, integration,
  line comparison, table generation, and plotting
- `figures/*.pdf` - publication-quality vector figures
- `figures/*.png` - high-resolution previews used for visual checking
- `results/data_manifest.csv` - complete candidate inventory and pairing notes
- `results/turbine_shutdown_metrics.csv` - wide pair-level metrics
- `results/turbine_line_metrics.csv` - long-form nearest-bin line results
- `results/*.tex` - generated LaTeX tables and numerical macros

## Rerun the analysis

From this directory:

```powershell
python analysis\analyze_turbine_shutdown.py
```

Optional paths:

```powershell
python analysis\analyze_turbine_shutdown.py `
  --source-root "C:\path\to\Manual Analysis" `
  --output-root "C:\path\to\Turbine_Shutdown_Addendum"
```

Python dependencies are:

```text
numpy
pandas
matplotlib
openpyxl
```

The script detects the frequency and acceleration-ASD columns from headers.
It supports `.xlsx`, `.xlsm`, `.csv`, `.txt`, and `.tsv` candidates. Uniform
grids use the original report's `sqrt(sum(ASD^2 * df))` convention;
nonuniform grids use trapezoidal integration of `ASD^2`. Line comparisons use
the nearest native-frequency bin in each spectrum.

## Compile the report

From this directory:

```powershell
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

If `latexmk` is unavailable:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

LaTeX dependencies are the standard packages listed in `main.tex`, including
`geometry`, `lmodern`, `microtype`, `graphicx`, `booktabs`, `siunitx`,
`fancyhdr`, `titlesec`, and `caption`.

## Data-quality notes

All included ASD spectra contain 513 points on an identical 0-250.25025 Hz
grid with 0.48877002 Hz spacing and explicit
`r_spectral_asd_mps2_per_sqrt_hz` headers. No included spectrum contains
NaN, infinite, negative-ASD, duplicate-frequency, or nonmonotonic-frequency
values.

The measurements are single spectra acquired on different dates, not repeated
or simultaneous trials. The freezer-top diagnostic has 9.0% higher full-band
RMS during turbine shutdown even though its 29.8 Hz line is 38.8 dB lower;
high-frequency local freezer lines dominate its total. During shutdown, the
Herzog floor and freezer-top spectra both have a peak near 119.7 Hz. That
frequency alignment, combined with the disappearance of the outdoor 120 Hz
component, makes the operating freezer the leading candidate for the
remaining indoor line. This is a plausible interpretation rather than a
proven attribution; a repeat measurement with the freezer powered down is
needed. The 59-61 Hz region also remains ambiguous because mechanical motion
and electrical mains pickup cannot be separated from these data alone.
