"""Tests for decoder pipeline."""
import pytest
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

os.environ["MOCK_MODE"] = "true"

from decoder_pipeline import DecoderPipeline
import numpy as np

@pytest.fixture
def pipeline():
    return DecoderPipeline()

class TestDecoderPipeline:
    @pytest.mark.asyncio
    async def test_mock_decode_dmr(self, pipeline):
        samples = np.random.randn(8192) + 1j * np.random.randn(8192)
        result = await pipeline.decode(samples, "DMR", 460.1)
        assert result is not None
        assert "metadata" in result
        assert "radio_id" in result["metadata"]
        assert "talkgroup" in result["metadata"]

    @pytest.mark.asyncio
    async def test_mock_decode_tetra(self, pipeline):
        samples = np.random.randn(8192) + 1j * np.random.randn(8192)
        result = await pipeline.decode(samples, "TETRA", 390.1)
        assert result is not None
        assert result["protocol"] == "TETRA"

    @pytest.mark.asyncio
    async def test_mock_decode_p25(self, pipeline):
        samples = np.random.randn(8192) + 1j * np.random.randn(8192)
        result = await pipeline.decode(samples, "P25_P1", 855.1)
        assert result is not None

    @pytest.mark.asyncio
    async def test_decode_has_call_type(self, pipeline):
        samples = np.random.randn(8192) + 1j * np.random.randn(8192)
        result = await pipeline.decode(samples, "DMR", 460.1)
        assert result["metadata"]["call_type"] in ("GROUP", "PRIVATE", "EMERGENCY")

    @pytest.mark.asyncio
    async def test_validate_output(self, pipeline):
        assert pipeline._validate_output({"metadata": {"radio_id": 123}}) == True
        assert pipeline._validate_output({"metadata": {}}) == False
        assert pipeline._validate_output(None) == False
