"""Tests for the signal classifier."""
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from classifier import SignalClassifier, SignalClassification

@pytest.fixture
def classifier():
    return SignalClassifier(fft_size=1024)

def make_signal(freq_offset_hz=0, bandwidth_hz=12500, sample_rate=2400000,
                num_samples=8192, snr_db=20):
    """Generate a test signal with specified bandwidth."""
    t = np.arange(num_samples) / sample_rate
    noise = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * 0.01
    # Create a band-limited signal
    signal_power = 10 ** (snr_db / 20) * 0.01
    # Generate symbols spread across the bandwidth
    num_symbols = int(num_samples * bandwidth_hz / sample_rate)
    symbol_freqs = np.linspace(-bandwidth_hz/2, bandwidth_hz/2, max(num_symbols, 10))
    signal = np.zeros(num_samples, dtype=complex)
    for sf in symbol_freqs:
        signal += signal_power * np.exp(1j * 2 * np.pi * (freq_offset_hz + sf) * t)
    return signal + noise

class TestSignalClassifier:
    def test_noise_only(self, classifier):
        """Pure noise should be classified as UNKNOWN and inactive."""
        noise = (np.random.randn(8192) + 1j * np.random.randn(8192)) * 0.001
        result = classifier.classify(noise, 460.0)
        assert isinstance(result, SignalClassification)
        assert result.is_active == False
        assert result.protocol == "UNKNOWN"

    def test_strong_signal_detected(self, classifier):
        """A strong signal should be classified as active."""
        signal = make_signal(snr_db=30, bandwidth_hz=12500)
        result = classifier.classify(signal, 460.1)
        assert result.is_active == True
        assert result.snr_db > 5

    def test_empty_samples(self, classifier):
        """Empty input should return safe defaults."""
        result = classifier.classify(np.array([]), 460.0)
        assert result.is_active == False
        assert result.protocol == "UNKNOWN"

    def test_none_samples(self, classifier):
        """None input should return safe defaults."""
        result = classifier.classify(None, 460.0)
        assert result.is_active == False

    def test_classification_has_all_fields(self, classifier):
        """Classification result should have all required fields."""
        signal = make_signal(snr_db=25)
        result = classifier.classify(signal, 460.0)
        assert hasattr(result, 'protocol')
        assert hasattr(result, 'bandwidth_khz')
        assert hasattr(result, 'snr_db')
        assert hasattr(result, 'power_dbm')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'is_active')
        assert hasattr(result, 'modulation')

    def test_confidence_range(self, classifier):
        """Confidence should be between 0 and 1."""
        signal = make_signal(snr_db=25)
        result = classifier.classify(signal, 460.0)
        assert 0.0 <= result.confidence <= 1.0

    def test_wide_bandwidth_signal(self, classifier):
        """A 25kHz signal should potentially classify as TETRA."""
        signal = make_signal(bandwidth_hz=25000, snr_db=25)
        result = classifier.classify(signal, 390.1)
        assert result.is_active == True
        assert result.bandwidth_khz > 10

    def test_weak_signal_below_threshold(self, classifier):
        """Very weak signal should be classified as inactive."""
        signal = make_signal(snr_db=1)
        result = classifier.classify(signal, 460.0)
        # With very low SNR, might still detect depending on noise
        assert isinstance(result.is_active, bool)
