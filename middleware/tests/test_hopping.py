"""Tests for hopping engine."""
import asyncio
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hopping_engine import HoppingEngine, HopAssignment
from sdr_controller import SDRDevice

@pytest.fixture
def mock_devices():
    return [
        SDRDevice(serial="TEST-001", device_type="RTL-SDR", index=0),
        SDRDevice(serial="TEST-002", device_type="HackRF", index=1),
    ]

@pytest.fixture
def single_device():
    return [SDRDevice(serial="TEST-001", device_type="RTL-SDR", index=0)]

@pytest.fixture
def small_bands():
    return [(460.0, 460.05, 0.0125)]  # Just 5 frequencies

class TestHoppingEngine:
    @pytest.mark.asyncio
    async def test_single_sdr_sweep(self, single_device, small_bands):
        engine = HoppingEngine(devices=single_device, multi_sdr=False, bands=small_bands)
        assignment = await engine.next_assignment()
        assert assignment is not None
        assert isinstance(assignment, HopAssignment)
        assert assignment.mode == "SWEEP"
        assert assignment.dwell_ms == 500  # Dead frequency default

    @pytest.mark.asyncio
    async def test_active_frequency_dwell(self, single_device, small_bands):
        engine = HoppingEngine(devices=single_device, multi_sdr=False, bands=small_bands)
        # Report first frequency as active
        first = await engine.next_assignment()
        await engine.report_activity(first.frequency, is_active=True, snr=20.0)
        # Sweep back to it
        for _ in range(len(engine.frequencies)):
            await engine.next_assignment()
        assignment = await engine.next_assignment()
        # After full sweep, the active freq should have DWELL_ACTIVE
        found_active = False
        for _ in range(len(engine.frequencies) + 1):
            a = await engine.next_assignment()
            if abs(a.frequency - first.frequency) < 0.001:
                assert a.dwell_ms == 3000
                found_active = True
                break
        assert found_active

    @pytest.mark.asyncio
    async def test_multi_sdr_pinning(self, mock_devices, small_bands):
        engine = HoppingEngine(devices=mock_devices, multi_sdr=True, bands=small_bands)
        # First assignment without any active freqs uses single mode
        a1 = await engine.next_assignment()
        assert a1 is not None

        # Report activity to trigger pinning
        await engine.report_activity(a1.frequency, is_active=True, snr=25.0)
        assert engine.pinned_control == a1.frequency

    @pytest.mark.asyncio
    async def test_frequency_list_built(self, single_device, small_bands):
        engine = HoppingEngine(devices=single_device, bands=small_bands)
        assert len(engine.frequencies) > 0

    @pytest.mark.asyncio
    async def test_status_dict(self, single_device, small_bands):
        engine = HoppingEngine(devices=single_device, bands=small_bands)
        status = engine.get_status()
        assert "total_frequencies" in status
        assert "active_count" in status
        assert status["active_count"] == 0

    @pytest.mark.asyncio
    async def test_no_devices(self):
        engine = HoppingEngine(devices=[], bands=[(460.0, 460.05, 0.0125)])
        assignment = await engine.next_assignment()
        assert assignment is None
