"""
SDR Controller — Device detection and sample capture abstraction.
Supports RTL-SDR, HackRF, and mock mode for testing.
"""
import asyncio
import subprocess
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
import structlog

log = structlog.get_logger()

@dataclass
class SDRDevice:
    serial: str
    device_type: str  # 'RTL-SDR', 'HackRF', 'UNKNOWN'
    index: int = 0
    sample_rate: int = 2400000
    gain_db: float = 40.0
    status: str = "ACTIVE"
    mode: str = "IDLE"
    assigned_freq: Optional[float] = None

class SDRController:
    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode
        self.devices: List[SDRDevice] = []

    async def detect_devices(self) -> List[SDRDevice]:
        if self.mock_mode:
            self.devices = [
                SDRDevice(serial="MOCK-RTL-001", device_type="RTL-SDR", index=0),
                SDRDevice(serial="MOCK-HRF-001", device_type="HackRF", index=1),
            ]
            log.info("sdr.mock_devices_created", count=len(self.devices))
            return self.devices

        devices = []
        # Try RTL-SDR detection
        try:
            result = await asyncio.create_subprocess_exec(
                'rtl_test', '-t',
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5)
            output = (stdout or b'').decode() + (stderr or b'').decode()
            if 'Found' in output:
                # Parse device count from rtl_test output
                idx = 0
                for line in output.split('\n'):
                    if 'Serial number' in line or 'SN:' in line:
                        serial = line.split(':')[-1].strip()
                        devices.append(SDRDevice(
                            serial=serial or f"RTL-{idx}",
                            device_type="RTL-SDR",
                            index=idx
                        ))
                        idx += 1
                if idx == 0 and 'Found 1' in output:
                    devices.append(SDRDevice(serial="RTL-0", device_type="RTL-SDR", index=0))
        except (FileNotFoundError, asyncio.TimeoutError):
            log.info("sdr.rtl_not_found")

        # Try HackRF detection
        try:
            result = await asyncio.create_subprocess_exec(
                'hackrf_info',
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5)
            output = (stdout or b'').decode()
            if 'Serial number' in output:
                for line in output.split('\n'):
                    if 'Serial number' in line:
                        serial = line.split(':')[-1].strip()
                        devices.append(SDRDevice(
                            serial=serial,
                            device_type="HackRF",
                            index=len(devices)
                        ))
        except (FileNotFoundError, asyncio.TimeoutError):
            log.info("sdr.hackrf_not_found")

        if not devices:
            log.warning("sdr.no_devices_found, falling back to mock")
            self.devices = [SDRDevice(serial="MOCK-FALLBACK", device_type="RTL-SDR", index=0)]
            self.mock_mode = True
        else:
            self.devices = devices

        return self.devices

    async def capture(self, device: SDRDevice, frequency: float, duration_ms: int) -> Optional[np.ndarray]:
        num_samples = int(device.sample_rate * duration_ms / 1000)

        if self.mock_mode:
            return self._generate_mock_samples(frequency, num_samples, device.sample_rate)

        try:
            if device.device_type == "RTL-SDR":
                return await self._capture_rtl(device, frequency, num_samples)
            elif device.device_type == "HackRF":
                return await self._capture_hackrf(device, frequency, num_samples)
        except Exception as e:
            log.error("sdr.capture_error", device=device.serial, error=str(e))
            return None

    async def _capture_rtl(self, device: SDRDevice, freq: float, num_samples: int) -> Optional[np.ndarray]:
        cmd = [
            'rtl_sdr', '-f', str(int(freq * 1e6)),
            '-s', str(device.sample_rate),
            '-g', str(int(device.gain_db)),
            '-d', str(device.index),
            '-n', str(num_samples * 2),
            '-'
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if stdout:
            raw = np.frombuffer(stdout, dtype=np.uint8)
            iq = (raw.astype(np.float32) - 127.5) / 127.5
            return iq[0::2] + 1j * iq[1::2]
        return None

    async def _capture_hackrf(self, device: SDRDevice, freq: float, num_samples: int) -> Optional[np.ndarray]:
        import tempfile, os
        tmp = tempfile.mktemp(suffix='.raw')
        cmd = [
            'hackrf_transfer', '-r', tmp,
            '-f', str(int(freq * 1e6)),
            '-s', str(device.sample_rate),
            '-l', str(int(device.gain_db)),
            '-n', str(num_samples * 2)
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)
        if os.path.exists(tmp):
            raw = np.fromfile(tmp, dtype=np.int8)
            os.unlink(tmp)
            iq = raw.astype(np.float32) / 128.0
            return iq[0::2] + 1j * iq[1::2]
        return None

    def _generate_mock_samples(self, frequency: float, num_samples: int, sample_rate: int) -> np.ndarray:
        """Generate mock IQ samples with realistic signal characteristics."""
        t = np.arange(num_samples) / sample_rate
        noise = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * 0.1

        # Determine if this frequency should have a signal (based on hash for consistency)
        freq_hash = int(frequency * 1000) % 100
        has_signal = freq_hash < 30  # 30% of frequencies have signals

        if has_signal:
            # Simulate a digital signal
            bw = 12500 if freq_hash % 2 == 0 else 25000  # DMR or TETRA bandwidth
            symbols = np.random.choice([-1, 1], size=num_samples)
            signal_power = 10 ** (np.random.uniform(10, 30) / 20)
            carrier = signal_power * symbols * np.exp(1j * 2 * np.pi * 1000 * t)
            return carrier + noise
        else:
            return noise
