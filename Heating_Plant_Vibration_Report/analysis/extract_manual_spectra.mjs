import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputDir =
  "C:/Users/kwlyon/Box/Codex/Building_Vibration_Analyzer/Manual Analysis";
const outputPath =
  "C:/Users/kwlyon/.codex/visualizations/2026/07/24/019f923a-5419-7092-902a-9a4aa6822fb4/manual_report_work/manual_spectra.json";

const filenames = (await fs.readdir(inputDir))
  .filter((name) => name.toLowerCase().endsWith("_fft_export.xlsx"))
  .sort((left, right) => left.localeCompare(right));

if (filenames.length !== 20) {
  throw new Error(`Expected 20 manual-analysis workbooks, found ${filenames.length}`);
}

const spectra = [];
for (const filename of filenames) {
  const workbook = await SpreadsheetFile.importXlsx(
    await FileBlob.load(path.join(inputDir, filename)),
  );
  const psdSheet = workbook.worksheets.getItem("PSD_ASD");
  const summarySheet = workbook.worksheets.getItem("Summary");
  const psdValues = psdSheet.getRange("A1:C514").values;
  const summaryValues = summarySheet.getRange("A1:E40").values;

  const headers = psdValues[0];
  if (
    headers[0] !== "frequency_hz" ||
    headers[2] !== "r_spectral_asd_mps2_per_sqrt_hz"
  ) {
    throw new Error(`Unexpected PSD_ASD headers in ${filename}`);
  }

  const frequencyHz = [];
  const asd = [];
  for (const row of psdValues.slice(1)) {
    if (
      typeof row[0] === "number" &&
      Number.isFinite(row[0]) &&
      typeof row[2] === "number" &&
      Number.isFinite(row[2])
    ) {
      frequencyHz.push(row[0]);
      asd.push(row[2]);
    }
  }
  if (frequencyHz.length !== 513 || asd.length !== 513) {
    throw new Error(
      `Expected 513 PSD/ASD bins in ${filename}, found ${frequencyHz.length}`,
    );
  }

  const summary = Object.fromEntries(
    summaryValues
      .filter((row) => typeof row[0] === "string" && row[0] && row[1] != null)
      .map((row) => [row[0], row[1]]),
  );

  spectra.push({
    filename,
    location: filename.replace(/_fft_export\.xlsx$/i, ""),
    frequencyHz,
    asd,
    metadata: {
      samples: summary["Full-session samples"],
      durationSeconds: summary["Full-session duration (s)"],
      sampleRateHz: summary["Estimated sample rate (Hz)"],
      frequencyResolutionHz: summary["Frequency resolution (Hz)"],
      fftWindow: summary["FFT window"],
      welchNperseg: summary["Welch nperseg"],
      welchOverlap: summary["Welch overlap"],
    },
  });
  console.log(
    `EXTRACTED ${filename}: ${frequencyHz.length} bins, ${summary["Full-session samples"]} samples`,
  );
}

await fs.writeFile(outputPath, JSON.stringify({ spectra }, null, 2));
console.log(`WROTE ${outputPath}`);
