"""Tests for metadata extractor and GPS parser."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from metadata_extractor import MetadataExtractor, ExtractedMetadata
from gps_parser import GPSParser, GPSFix

@pytest.fixture
def extractor():
    return MetadataExtractor()

@pytest.fixture
def gps_parser():
    return GPSParser()

class TestMetadataExtractor:
    def test_extract_valid(self, extractor):
        decoded = {
            "decoder": "dsdcc",
            "frequency": 460.1,
            "metadata": {
                "radio_id": 3000001,
                "talkgroup": 100,
                "time_slot": 1,
                "call_type": "GROUP",
                "color_code": 1,
                "encrypted": False,
            }
        }
        result = extractor.extract(decoded, "DMR")
        assert isinstance(result, ExtractedMetadata)
        assert result.radio_id == 3000001
        assert result.talkgroup == 100
        assert result.call_type == "GROUP"

    def test_extract_no_radio_id(self, extractor):
        decoded = {"metadata": {"talkgroup": 100}}
        result = extractor.extract(decoded, "DMR")
        assert result is None

    def test_extract_none(self, extractor):
        assert extractor.extract(None, "DMR") is None

    def test_extract_empty_metadata(self, extractor):
        assert extractor.extract({"metadata": {}}, "DMR") is None

    def test_to_dict(self, extractor):
        decoded = {
            "decoder": "mock",
            "metadata": {"radio_id": 123, "talkgroup": 200, "call_type": "private"}
        }
        result = extractor.extract(decoded, "TETRA")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["radio_id"] == 123
        assert d["call_type"] == "PRIVATE"

class TestGPSParser:
    def test_parse_gps_from_metadata(self, gps_parser):
        decoded = {
            "metadata": {
                "radio_id": 3000003,
                "gps": {
                    "latitude": 33.749,
                    "longitude": -84.388,
                    "altitude": 300,
                    "speed": 45.0,
                    "heading": 180.0,
                }
            }
        }
        result = gps_parser.parse(decoded, "DMR")
        assert isinstance(result, GPSFix)
        assert result.latitude == 33.749
        assert result.longitude == -84.388
        assert result.source_protocol == "LRRP"

    def test_parse_tetra_gps(self, gps_parser):
        decoded = {
            "metadata": {
                "radio_id": 3000010,
                "gps": {"latitude": 51.5074, "longitude": -0.1278}
            }
        }
        result = gps_parser.parse(decoded, "TETRA")
        assert result.source_protocol == "LIP"

    def test_invalid_coords(self, gps_parser):
        decoded = {
            "metadata": {
                "radio_id": 1,
                "gps": {"latitude": 999, "longitude": -999}
            }
        }
        result = gps_parser.parse(decoded, "DMR")
        assert result is None

    def test_no_gps_data(self, gps_parser):
        decoded = {"metadata": {"radio_id": 1}}
        assert gps_parser.parse(decoded, "DMR") is None

    def test_none_input(self, gps_parser):
        assert gps_parser.parse(None, "DMR") is None

    def test_gps_fix_to_dict(self, gps_parser):
        fix = GPSFix(radio_id=1, latitude=33.0, longitude=-84.0)
        d = fix.to_dict()
        assert d["radio_id"] == 1
        assert d["latitude"] == 33.0
