"""
GPS Parser — Extract location data from LRRP (DMR) and LIP (TETRA) packets.
"""
from dataclasses import dataclass, asdict
from typing import Optional, Dict
import struct
import math
import structlog

log = structlog.get_logger()

@dataclass
class GPSFix:
    radio_id: int
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    speed_kmh: Optional[float] = None
    heading: Optional[float] = None
    accuracy_m: Optional[float] = None
    source_protocol: str = "UNKNOWN"

    def to_dict(self) -> dict:
        return asdict(self)

class GPSParser:
    def parse(self, decoded: Dict, protocol: str) -> Optional[GPSFix]:
        if not decoded:
            return None

        meta = decoded.get("metadata", {})
        gps_data = meta.get("gps")

        if not gps_data:
            # Try to find GPS in raw LRRP/LIP data
            raw = meta.get("raw_gps_bytes")
            if raw and protocol in ("DMR", "P25_P1", "P25_P2"):
                return self._parse_lrrp(raw, meta.get("radio_id", 0))
            elif raw and protocol == "TETRA":
                return self._parse_lip(raw, meta.get("radio_id", 0))
            return None

        radio_id = meta.get("radio_id", 0)
        if not radio_id:
            return None

        lat = gps_data.get("latitude")
        lon = gps_data.get("longitude")
        if lat is None or lon is None:
            return None

        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            log.warning("gps.invalid_coords", lat=lat, lon=lon)
            return None

        source = "LRRP" if protocol in ("DMR", "P25_P1", "P25_P2") else "LIP" if protocol == "TETRA" else "UNKNOWN"

        return GPSFix(
            radio_id=radio_id,
            latitude=round(lat, 6),
            longitude=round(lon, 6),
            altitude=gps_data.get("altitude"),
            speed_kmh=gps_data.get("speed"),
            heading=gps_data.get("heading"),
            accuracy_m=gps_data.get("accuracy"),
            source_protocol=source,
        )

    def _parse_lrrp(self, raw_bytes: bytes, radio_id: int) -> Optional[GPSFix]:
        """Parse LRRP (Location Request Response Protocol) for DMR."""
        try:
            if len(raw_bytes) < 8:
                return None

            # LRRP Answer PDU format (simplified)
            # Latitude: 4 bytes, scaled to ±90 degrees
            # Longitude: 4 bytes, scaled to ±180 degrees
            lat_raw = struct.unpack('>i', raw_bytes[0:4])[0]
            lon_raw = struct.unpack('>i', raw_bytes[4:8])[0]

            lat = (lat_raw / 0x7FFFFFFF) * 90.0
            lon = (lon_raw / 0x7FFFFFFF) * 180.0

            speed = None
            heading = None
            if len(raw_bytes) >= 12:
                speed_raw = struct.unpack('>H', raw_bytes[8:10])[0]
                heading_raw = struct.unpack('>H', raw_bytes[10:12])[0]
                speed = speed_raw * 0.036  # Convert to km/h
                heading = heading_raw * (360.0 / 65536)

            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return None

            return GPSFix(
                radio_id=radio_id, latitude=round(lat, 6), longitude=round(lon, 6),
                speed_kmh=round(speed, 1) if speed else None,
                heading=round(heading, 1) if heading else None,
                source_protocol="LRRP"
            )
        except Exception as e:
            log.error("gps.lrrp_parse_error", error=str(e))
            return None

    def _parse_lip(self, raw_bytes: bytes, radio_id: int) -> Optional[GPSFix]:
        """Parse LIP (Location Information Protocol) for TETRA."""
        try:
            if len(raw_bytes) < 8:
                return None

            # TETRA LIP Short Location Report (simplified)
            lat_raw = struct.unpack('>i', raw_bytes[0:4])[0]
            lon_raw = struct.unpack('>i', raw_bytes[4:8])[0]

            lat = (lat_raw / (2**23)) * 180.0 / math.pi
            lon = (lon_raw / (2**24)) * 360.0 / math.pi

            # Clamp to valid range
            lat = max(-90, min(90, lat))
            lon = max(-180, min(180, lon))

            return GPSFix(
                radio_id=radio_id, latitude=round(lat, 6), longitude=round(lon, 6),
                source_protocol="LIP"
            )
        except Exception as e:
            log.error("gps.lip_parse_error", error=str(e))
            return None
