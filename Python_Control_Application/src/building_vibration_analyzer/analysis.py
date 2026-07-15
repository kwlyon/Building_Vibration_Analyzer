from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import signal


@dataclass(frozen=True)
class SummaryStats:
    mean: float
    rms: float
    peak: float
    peak_to_peak: float
    crest_factor: float
    std: float


def remove_mean(values):
    values = np.asarray(values, dtype=float)
    return values - np.nanmean(values)


def dynamic_resultant(x_values, y_values, z_values):
    """Return magnitude of mean-removed acceleration components."""
    x = remove_mean(x_values)
    y = remove_mean(y_values)
    z = remove_mean(z_values)
    return np.sqrt(x**2 + y**2 + z**2)


def root_sum_square_spectra(*spectra):
    """Combine same-bin amplitude spectra as a root-sum-square resultant."""
    arrays = [np.asarray(spectrum, dtype=float) for spectrum in spectra]
    return np.sqrt(np.sum([array**2 for array in arrays], axis=0))


def sum_power_spectra(*spectra):
    """Combine same-bin power spectra."""
    arrays = [np.asarray(spectrum, dtype=float) for spectrum in spectra]
    return np.sum(arrays, axis=0)


def detrend_linear(values):
    return signal.detrend(np.asarray(values, dtype=float), type="linear")


def summary_statistics(values) -> SummaryStats:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return SummaryStats(*(float("nan"),) * 6)
    rms = float(np.sqrt(np.mean(finite**2)))
    peak = float(np.max(np.abs(finite)))
    return SummaryStats(
        mean=float(np.mean(finite)),
        rms=rms,
        peak=peak,
        peak_to_peak=float(np.ptp(finite)),
        crest_factor=float(peak / rms) if rms > 0 else float("inf"),
        std=float(np.std(finite, ddof=0)),
    )


def fft_amplitude(values, sample_rate_hz: float, window: str = "hann"):
    values = np.asarray(values, dtype=float)
    n = values.size
    if n < 2:
        raise ValueError("at least two samples are required")
    win = signal.get_window(window, n, fftbins=True)
    coherent_gain = np.sum(win) / n
    spectrum = np.fft.rfft(values * win)
    freq = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)
    amp = np.abs(spectrum) / (n * coherent_gain)
    if amp.size > 2:
        amp[1:-1] *= 2.0
    return freq, amp


def welch_psd(values, sample_rate_hz: float, window: str = "hann", fft_length: int | None = None, overlap: float = 0.5):
    values = np.asarray(values, dtype=float)
    nperseg = min(fft_length or 1024, values.size)
    if nperseg < 2:
        raise ValueError("at least two samples are required")
    noverlap = int(nperseg * overlap)
    freq, psd = signal.welch(
        values,
        fs=sample_rate_hz,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
        detrend="constant",
        scaling="density",
    )
    return freq, psd


def amplitude_spectral_density(psd):
    return np.sqrt(np.asarray(psd, dtype=float))


def spectrogram(values, sample_rate_hz: float, window: str = "hann", fft_length: int = 256, overlap: float = 0.5):
    values = np.asarray(values, dtype=float)
    nperseg = min(fft_length, values.size)
    noverlap = int(nperseg * overlap)
    freq, time_s, spec = signal.spectrogram(
        values,
        fs=sample_rate_hz,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
        scaling="density",
        mode="psd",
    )
    return freq, time_s, spec


def dominant_frequencies(freq, amplitude, count: int = 5, min_frequency: float = 0.0):
    freq = np.asarray(freq, dtype=float)
    amplitude = np.asarray(amplitude, dtype=float)
    mask = freq >= min_frequency
    peaks, _ = signal.find_peaks(amplitude[mask])
    masked_freq = freq[mask]
    masked_amp = amplitude[mask]
    ranked = sorted(((masked_amp[i], masked_freq[i]) for i in peaks), reverse=True)
    return [(float(f), float(a)) for a, f in ranked[:count]]


def harmonic_peaks(freq, amplitude, fundamental_hz: float, harmonics: int = 5, tolerance_hz: float = 0.5):
    freq = np.asarray(freq, dtype=float)
    amplitude = np.asarray(amplitude, dtype=float)
    found = []
    for k in range(1, harmonics + 1):
        target = fundamental_hz * k
        mask = (freq >= target - tolerance_hz) & (freq <= target + tolerance_hz)
        if not np.any(mask):
            continue
        local_idx = np.argmax(amplitude[mask])
        local_freq = freq[mask][local_idx]
        local_amp = amplitude[mask][local_idx]
        found.append((k, float(local_freq), float(local_amp)))
    return found


def band_rms_from_psd(freq, psd, band: tuple[float, float]) -> float:
    freq = np.asarray(freq, dtype=float)
    psd = np.asarray(psd, dtype=float)
    low, high = band
    mask = (freq >= low) & (freq <= high)
    if np.count_nonzero(mask) < 2:
        return 0.0
    power = np.trapezoid(psd[mask], freq[mask])
    return float(np.sqrt(max(power, 0.0)))


def cross_spectral_density(a, b, sample_rate_hz: float, fft_length: int | None = None):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    nperseg = min(fft_length or 1024, a.size, b.size)
    return signal.csd(a, b, fs=sample_rate_hz, nperseg=nperseg, scaling="density")


def coherence(a, b, sample_rate_hz: float, fft_length: int | None = None):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    nperseg = min(fft_length or 1024, a.size, b.size)
    return signal.coherence(a, b, fs=sample_rate_hz, nperseg=nperseg)


def velocity_displacement_spectra(freq, accel_amplitude, low_cutoff_hz: float):
    freq = np.asarray(freq, dtype=float)
    accel = np.asarray(accel_amplitude, dtype=float)
    omega = 2.0 * np.pi * freq
    velocity = np.full_like(accel, np.nan, dtype=float)
    displacement = np.full_like(accel, np.nan, dtype=float)
    mask = freq >= low_cutoff_hz
    velocity[mask] = accel[mask] / omega[mask]
    displacement[mask] = accel[mask] / (omega[mask] ** 2)
    return velocity * 1000.0, displacement * 1_000_000.0


DEFAULT_BUILDING_BANDS = {
    "0.5-5 Hz": (0.5, 5.0),
    "5-20 Hz": (5.0, 20.0),
    "20-80 Hz": (20.0, 80.0),
    "55-65 Hz": (55.0, 65.0),
    "80-200 Hz": (80.0, 200.0),
}
