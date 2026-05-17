"""
Signal Classifier — FFT-based protocol identification.
Analyzes bandwidth signature and modulation to guess protocol.
"""
import numpy as np
from dataclasses import dataclass
from typing import Optional
import structlog

log = structlog.get_logger()

@dataclass
class SignalClassification:
    protocol: str        # DMR, TETRA, P25_P1, P25_P2, NXDN, UNKNOWN
    bandwidth_khz: float
    snr_db: float
    power_dbm: float
    confidence: float    # 0.0 - 1.0
    is_active: bool
    modulation: str      # 4FSK, PI4DQPSK, C4FM, CQPSK, UNKNOWN

# Bandwidth-to-protocol mapping rules
PROTOCOL_RULES = [
    # (bw_min_khz, bw_max_khz, protocol, modulation, confidence_bonus)
    (10.0, 14.0, "DMR", "4FSK", 0.3),
    (22.0, 28.0, "TETRA", "PI4DQPSK", 0.3),
    (10.0, 14.0, "P25_P1", "C4FM", 0.2),
    (5.0, 8.0, "P25_P2", "CQPSK", 0.2),
    (5.0, 8.0, "NXDN", "4FSK", 0.1),
]

NOISE_FLOOR_DB = -120  # dBm reference noise floor
SNR_THRESHOLD = 6.0     # Minimum SNR to consider signal active

class SignalClassifier:
    def __init__(self, fft_size: int = 4096, snr_threshold: float = SNR_THRESHOLD):
        self.fft_size = fft_size
        self.snr_threshold = snr_threshold

    def classify(self, samples: np.ndarray, frequency_mhz: float,
                 sample_rate: int = 2400000) -> SignalClassification:
        if samples is None or len(samples) < self.fft_size:
            return SignalClassification(
                protocol="UNKNOWN", bandwidth_khz=0, snr_db=0,
                power_dbm=NOISE_FLOOR_DB, confidence=0, is_active=False,
                modulation="UNKNOWN"
            )

        # Compute PSD
        psd = self._compute_psd(samples)
        freq_bins = np.fft.fftfreq(self.fft_size, d=1.0/sample_rate) / 1000  # kHz

        # Measure signal power and noise
        noise_floor = np.percentile(psd, 20)
        signal_peak = np.max(psd)
        snr_db = float(signal_peak - noise_floor)
        power_dbm = float(signal_peak + NOISE_FLOOR_DB)

        is_active = snr_db > self.snr_threshold

        if not is_active:
            return SignalClassification(
                protocol="UNKNOWN", bandwidth_khz=0, snr_db=snr_db,
                power_dbm=power_dbm, confidence=0.9, is_active=False,
                modulation="UNKNOWN"
            )

        # Measure occupied bandwidth (-20dB from peak)
        threshold = signal_peak - 20
        active_bins = psd > threshold
        if np.any(active_bins):
            active_freqs = freq_bins[active_bins]
            bandwidth_khz = float(np.max(active_freqs) - np.min(active_freqs))
        else:
            bandwidth_khz = 0.0

        # Classify based on bandwidth
        protocol, modulation, confidence = self._match_protocol(bandwidth_khz, samples, sample_rate)

        return SignalClassification(
            protocol=protocol,
            bandwidth_khz=round(bandwidth_khz, 2),
            snr_db=round(snr_db, 2),
            power_dbm=round(power_dbm, 2),
            confidence=round(confidence, 3),
            is_active=True,
            modulation=modulation
        )

    def _compute_psd(self, samples: np.ndarray) -> np.ndarray:
        # Use Welch-like averaging
        num_segments = max(1, len(samples) // self.fft_size)
        psd_accum = np.zeros(self.fft_size)

        for i in range(num_segments):
            segment = samples[i * self.fft_size:(i + 1) * self.fft_size]
            if len(segment) < self.fft_size:
                segment = np.pad(segment, (0, self.fft_size - len(segment)))

            windowed = segment * np.hanning(self.fft_size)
            spectrum = np.fft.fftshift(np.fft.fft(windowed))
            psd_accum += np.abs(spectrum) ** 2

        psd_accum /= num_segments
        psd_db = 10 * np.log10(psd_accum + 1e-12)
        return psd_db

    def _match_protocol(self, bandwidth_khz: float, samples: np.ndarray,
                        sample_rate: int) -> tuple:
        best_match = ("UNKNOWN", "UNKNOWN", 0.3)
        best_score = 0.0

        for bw_min, bw_max, protocol, modulation, bonus in PROTOCOL_RULES:
            if bw_min <= bandwidth_khz <= bw_max:
                # Base confidence from bandwidth match
                bw_center = (bw_min + bw_max) / 2
                bw_deviation = abs(bandwidth_khz - bw_center) / (bw_max - bw_min)
                confidence = (1.0 - bw_deviation) * 0.5 + bonus

                # Symbol rate analysis for additional confidence
                mod_bonus = self._check_modulation(samples, sample_rate, modulation)
                confidence = min(confidence + mod_bonus, 0.95)

                if confidence > best_score:
                    best_score = confidence
                    best_match = (protocol, modulation, confidence)

        return best_match

    def _check_modulation(self, samples: np.ndarray, sample_rate: int,
                          expected_mod: str) -> float:
        """Estimate modulation type from symbol rate analysis."""
        try:
            # Compute instantaneous frequency deviation
            phase = np.angle(samples)
            freq_dev = np.diff(np.unwrap(phase)) * sample_rate / (2 * np.pi)

            if expected_mod == "4FSK":
                # DMR/NXDN: 4FSK with ~4800 symbols/sec, ±1944 Hz deviation
                symbol_rate = 4800
                expected_dev = 1944
                # Check if freq deviation clusters around ±648, ±1944
                hist, _ = np.histogram(freq_dev, bins=50)
                peak_count = np.sum(hist > np.mean(hist) * 2)
                return 0.15 if 3 <= peak_count <= 6 else 0.0

            elif expected_mod == "PI4DQPSK":
                # TETRA: π/4-DQPSK at 18000 symbols/sec
                return 0.1  # Simplified check

            elif expected_mod == "C4FM":
                # P25: C4FM at 4800 symbols/sec, ±1800 Hz
                return 0.1

            elif expected_mod == "CQPSK":
                # P25 Phase 2: CQPSK at 6000 symbols/sec
                return 0.1

        except Exception:
            pass
        return 0.0
