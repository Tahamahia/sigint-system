"""
Frequency Hopping Engine — State machine for single/multi SDR operation.
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from collections import defaultdict
import structlog

log = structlog.get_logger()

@dataclass
class FrequencyEntry:
    frequency: float
    last_active: float = 0
    hit_count: int = 0
    avg_snr: float = 0.0
    is_active: bool = False
    priority_score: float = 0.0

@dataclass
class HopAssignment:
    device: object  # SDRDevice
    frequency: float
    dwell_ms: int
    mode: str  # 'SWEEP', 'PINNED', 'DISCOVERY'

# Default frequency bands to sweep (MHz)
DEFAULT_BANDS = [
    (136.0, 174.0, 0.0125),   # VHF 12.5kHz steps
    (380.0, 400.0, 0.025),     # TETRA band 25kHz steps
    (450.0, 470.0, 0.0125),    # UHF DMR 12.5kHz steps
    (851.0, 869.0, 0.0125),    # 800MHz P25
]

class HoppingEngine:
    # Dwell times in ms
    DWELL_DEAD = 500
    DWELL_ACTIVE = 3000
    DISCOVERY_INTERVAL = 3600  # Full sweep every hour

    def __init__(self, devices, multi_sdr=False, classifier=None, bands=None):
        self.devices = devices
        self.multi_sdr = multi_sdr
        self.classifier = classifier
        self.bands = bands or DEFAULT_BANDS

        # Build frequency list
        self.frequencies: List[FrequencyEntry] = []
        self._build_frequency_list()

        self.sweep_index = 0
        self.last_discovery = time.time()
        self.active_freqs: Dict[float, FrequencyEntry] = {}
        self.pinned_control: Optional[float] = None
        self._lock = asyncio.Lock()

        log.info("hopping.init", total_frequencies=len(self.frequencies),
                 multi_sdr=multi_sdr, device_count=len(devices))

    def _build_frequency_list(self):
        for band_low, band_high, step in self.bands:
            freq = band_low
            while freq <= band_high:
                self.frequencies.append(FrequencyEntry(frequency=round(freq, 6)))
                freq += step

    async def next_assignment(self) -> Optional[HopAssignment]:
        async with self._lock:
            if not self.devices:
                return None

            now = time.time()

            # Check if background discovery is due
            if now - self.last_discovery > self.DISCOVERY_INTERVAL:
                self.last_discovery = now
                self.sweep_index = 0
                log.info("hopping.discovery_sweep_starting")

            if self.multi_sdr:
                return self._multi_sdr_assignment()
            else:
                return self._single_sdr_assignment()

    def _single_sdr_assignment(self) -> Optional[HopAssignment]:
        if not self.frequencies:
            return None

        device = self.devices[0]
        entry = self.frequencies[self.sweep_index % len(self.frequencies)]

        # Adaptive dwell time
        if entry.is_active:
            dwell = self.DWELL_ACTIVE
        else:
            dwell = self.DWELL_DEAD

        self.sweep_index = (self.sweep_index + 1) % len(self.frequencies)

        device.mode = "SWEEP"
        device.assigned_freq = entry.frequency

        return HopAssignment(
            device=device,
            frequency=entry.frequency,
            dwell_ms=dwell,
            mode="SWEEP"
        )

    def _multi_sdr_assignment(self) -> Optional[HopAssignment]:
        if len(self.devices) < 2:
            return self._single_sdr_assignment()

        # Device 0: pinned to control channel (highest priority active freq)
        # Device 1+: sweep traffic channels
        if self.pinned_control and self.active_freqs:
            primary = self.devices[0]
            primary.mode = "PINNED"
            primary.assigned_freq = self.pinned_control

            # Use secondary device for sweeping
            secondary = self.devices[1]
            entry = self.frequencies[self.sweep_index % len(self.frequencies)]
            dwell = self.DWELL_ACTIVE if entry.is_active else self.DWELL_DEAD
            self.sweep_index = (self.sweep_index + 1) % len(self.frequencies)
            secondary.mode = "SWEEP"
            secondary.assigned_freq = entry.frequency

            return HopAssignment(
                device=secondary,
                frequency=entry.frequency,
                dwell_ms=dwell,
                mode="SWEEP"
            )
        else:
            return self._single_sdr_assignment()

    async def report_activity(self, frequency: float, is_active: bool, snr: float):
        async with self._lock:
            for entry in self.frequencies:
                if abs(entry.frequency - frequency) < 0.001:
                    entry.is_active = is_active
                    entry.hit_count += 1 if is_active else 0
                    entry.avg_snr = (entry.avg_snr * 0.8 + snr * 0.2) if snr > 0 else entry.avg_snr
                    entry.last_active = time.time() if is_active else entry.last_active
                    entry.priority_score = entry.hit_count * entry.avg_snr

                    if is_active:
                        self.active_freqs[frequency] = entry
                        # Auto-pin highest priority as control channel
                        if not self.pinned_control or entry.priority_score > self.active_freqs.get(self.pinned_control, FrequencyEntry(frequency=0)).priority_score:
                            self.pinned_control = frequency
                            log.info("hopping.control_pinned", frequency=frequency)
                    elif frequency in self.active_freqs:
                        del self.active_freqs[frequency]
                    break

    def get_status(self) -> dict:
        return {
            "total_frequencies": len(self.frequencies),
            "active_count": len(self.active_freqs),
            "sweep_index": self.sweep_index,
            "pinned_control": self.pinned_control,
            "multi_sdr": self.multi_sdr,
        }
