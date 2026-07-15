import math
import pathlib
import sys
import unittest

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from building_vibration_analyzer.analysis import (
    band_rms_from_psd,
    coherence,
    dominant_frequencies,
    dynamic_resultant,
    fft_amplitude,
    harmonic_peaks,
    root_sum_square_spectra,
    sum_power_spectra,
    summary_statistics,
    velocity_displacement_spectra,
    welch_psd,
)


class AnalysisTests(unittest.TestCase):
    def test_sine_fft_frequency_and_amplitude(self):
        fs = 200.0
        duration = 4.0
        freq0 = 12.5
        amp0 = 2.0
        t = np.arange(0, duration, 1 / fs)
        x = amp0 * np.sin(2 * np.pi * freq0 * t)
        freq, amp = fft_amplitude(x, fs, window="boxcar")
        peak_idx = np.argmax(amp[1:]) + 1
        self.assertAlmostEqual(freq[peak_idx], freq0, places=6)
        self.assertAlmostEqual(amp[peak_idx], amp0, places=6)

    def test_psd_band_rms_matches_sine_rms(self):
        fs = 200.0
        t = np.arange(0, 8.0, 1 / fs)
        amp0 = 1.5
        x = amp0 * np.sin(2 * np.pi * 20.0 * t)
        freq, psd = welch_psd(x, fs, window="boxcar", fft_length=len(x), overlap=0.0)
        rms = band_rms_from_psd(freq, psd, (18.0, 22.0))
        self.assertAlmostEqual(rms, amp0 / math.sqrt(2), places=3)

    def test_dominant_and_harmonic_detection(self):
        fs = 500.0
        t = np.arange(0, 4.0, 1 / fs)
        x = np.sin(2 * np.pi * 15 * t) + 0.3 * np.sin(2 * np.pi * 30 * t)
        freq, amp = fft_amplitude(x, fs, window="boxcar")
        dom = dominant_frequencies(freq, amp, count=2, min_frequency=1.0)
        self.assertAlmostEqual(dom[0][0], 15.0, places=6)
        harmonics = harmonic_peaks(freq, amp, 15.0, harmonics=2, tolerance_hz=0.2)
        self.assertEqual([h[0] for h in harmonics], [1, 2])

    def test_summary_and_coherence(self):
        fs = 100.0
        t = np.arange(0, 2.0, 1 / fs)
        x = np.sin(2 * np.pi * 5 * t)
        stats = summary_statistics(x)
        self.assertAlmostEqual(stats.rms, 1 / math.sqrt(2), places=3)
        freq, coh = coherence(x, x, fs, fft_length=128)
        self.assertGreater(np.nanmax(coh), 0.99)

    def test_velocity_displacement_cutoff(self):
        freq = np.array([0.1, 1.0, 10.0])
        accel = np.ones_like(freq)
        velocity, displacement = velocity_displacement_spectra(freq, accel, low_cutoff_hz=1.0)
        self.assertTrue(np.isnan(velocity[0]))
        self.assertTrue(np.isfinite(displacement[1]))

    def test_dynamic_resultant_removes_static_offset(self):
        x = np.array([1.0, 2.0, 1.0, 0.0])
        y = np.array([0.0, 0.0, 0.0, 0.0])
        z = np.array([9.8, 9.8, 9.8, 9.8])
        r = dynamic_resultant(x, y, z)
        self.assertAlmostEqual(float(np.max(r)), 1.0)

    def test_spectral_resultant_helpers(self):
        x = np.array([3.0, 0.0])
        y = np.array([4.0, 1.0])
        z = np.array([0.0, 2.0])
        self.assertTrue(np.allclose(root_sum_square_spectra(x, y, z), np.array([5.0, math.sqrt(5.0)])))
        self.assertTrue(np.allclose(sum_power_spectra(x, y, z), np.array([7.0, 3.0])))


if __name__ == "__main__":
    unittest.main()
