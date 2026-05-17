"""
Metadata Extractor — Parse and normalize decoded metadata from all protocols.
"""
from dataclasses import dataclass, asdict
from typing import Optional, Dict
import structlog

log = structlog.get_logger()

@dataclass
class ExtractedMetadata:
    radio_id: int
    talkgroup: Optional[int] = None
    color_code: Optional[int] = None
    time_slot: Optional[int] = None
    call_type: str = "UNKNOWN"
    protocol: str = "UNKNOWN"
    frequency: float = 0.0
    encrypted: bool = False
    encryption_type: Optional[str] = None
    source_decoder: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)

class MetadataExtractor:
    def extract(self, decoded: Dict, protocol: str) -> Optional[ExtractedMetadata]:
        if not decoded:
            return None

        meta = decoded.get("metadata", {})
        if not meta:
            return None

        radio_id = meta.get("radio_id")
        if not radio_id:
            return None

        return ExtractedMetadata(
            radio_id=int(radio_id),
            talkgroup=meta.get("talkgroup"),
            color_code=meta.get("color_code"),
            time_slot=meta.get("time_slot"),
            call_type=meta.get("call_type", "UNKNOWN").upper(),
            protocol=protocol,
            frequency=decoded.get("frequency", 0.0),
            encrypted=meta.get("encrypted", False),
            encryption_type=meta.get("encryption_type"),
            source_decoder=decoded.get("decoder", "unknown"),
        )
