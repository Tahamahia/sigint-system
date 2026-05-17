"""
Decoder Pipeline — Sequential decoder chain with fallback.
Wraps external decoders (DSDcc, OP25, Telive) as headless subprocesses.
"""
import asyncio
import json
import os
import tempfile
import numpy as np
from typing import Optional, Dict, List
import structlog

log = structlog.get_logger()

MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:4000")

# Decoder configurations
DECODERS = {
    "DMR": [
        {"name": "dsdcc", "cmd": "dsdcc", "args": ["-i", "-", "-fd"], "format": "text"},
        {"name": "dsd", "cmd": "dsd", "args": ["-i", "-", "-fd"], "format": "text"},
    ],
    "TETRA": [
        {"name": "telive", "cmd": "telive_decoder", "args": [], "format": "json"},
    ],
    "P25_P1": [
        {"name": "op25", "cmd": "op25_decoder", "args": ["--phase1"], "format": "json"},
        {"name": "dsdcc", "cmd": "dsdcc", "args": ["-i", "-", "-fp"], "format": "text"},
    ],
    "P25_P2": [
        {"name": "op25", "cmd": "op25_decoder", "args": ["--phase2"], "format": "json"},
    ],
    "NXDN": [
        {"name": "dsdcc", "cmd": "dsdcc", "args": ["-i", "-", "-fn"], "format": "text"},
    ],
}

class DecoderPipeline:
    def __init__(self):
        self.available_decoders = self._check_available()
        self._key_cache = {}  # network_id -> {type, key}

    def _check_available(self) -> set:
        if MOCK_MODE:
            return {"mock_decoder"}
        available = set()
        for decoder_list in DECODERS.values():
            for dec in decoder_list:
                try:
                    import shutil
                    if shutil.which(dec["cmd"]):
                        available.add(dec["name"])
                except Exception:
                    pass
        log.info("decoders.available", decoders=list(available))
        return available

    async def decode(self, samples: np.ndarray, protocol: str,
                     frequency: float, network_id: str = None) -> Optional[Dict]:
        if MOCK_MODE:
            return self._mock_decode(protocol, frequency)

        decoders = DECODERS.get(protocol, [])
        if not decoders:
            decoders = DECODERS.get("DMR", [])  # Fallback to DMR decoder

        for decoder_config in decoders:
            if decoder_config["name"] not in self.available_decoders:
                continue

            # Fetch encryption key if network is known
            key_args = []
            if network_id:
                key_info = await self._get_network_key(network_id)
                if key_info and key_info.get("encryption_key"):
                    key_args = self._build_key_args(decoder_config["name"],
                                                    key_info["encryption_type"],
                                                    key_info["encryption_key"])

            result = await self._run_decoder(decoder_config, samples, frequency, key_args)
            if result and self._validate_output(result):
                log.info("decoder.success", decoder=decoder_config["name"],
                         protocol=protocol, freq=frequency)
                return result
            else:
                log.debug("decoder.fallback", decoder=decoder_config["name"],
                          protocol=protocol)

        # All decoders failed — try universal fallback
        log.warning("decoder.all_failed", protocol=protocol, freq=frequency)
        return None

    async def _run_decoder(self, config: dict, samples: np.ndarray,
                           frequency: float, key_args: list = None) -> Optional[Dict]:
        try:
            # Convert IQ samples to raw bytes for decoder stdin
            raw_bytes = self._iq_to_raw(samples)

            cmd_args = config["args"] + (key_args or [])
            proc = await asyncio.create_subprocess_exec(
                config["cmd"], *cmd_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=raw_bytes), timeout=10
            )

            output = stdout.decode('utf-8', errors='replace')

            if config["format"] == "json":
                return self._parse_json_output(output)
            else:
                return self._parse_text_output(output, config["name"])

        except asyncio.TimeoutError:
            log.warning("decoder.timeout", decoder=config["name"])
            return None
        except FileNotFoundError:
            log.warning("decoder.not_found", cmd=config["cmd"])
            return None
        except Exception as e:
            log.error("decoder.error", decoder=config["name"], error=str(e))
            return None

    def _iq_to_raw(self, samples: np.ndarray) -> bytes:
        """Convert complex IQ samples to interleaved int8 bytes."""
        interleaved = np.zeros(len(samples) * 2, dtype=np.int8)
        interleaved[0::2] = np.clip(samples.real * 128, -128, 127).astype(np.int8)
        interleaved[1::2] = np.clip(samples.imag * 128, -128, 127).astype(np.int8)
        return interleaved.tobytes()

    def _parse_json_output(self, output: str) -> Optional[Dict]:
        for line in output.strip().split('\n'):
            line = line.strip()
            if line.startswith('{'):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return None

    def _parse_text_output(self, output: str, decoder_name: str) -> Optional[Dict]:
        result = {"decoder": decoder_name, "raw_lines": [], "metadata": {}}
        for line in output.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            result["raw_lines"].append(line)

            # Parse common DSD-style output fields
            if "Slot" in line and ("TG" in line or "RID" in line):
                parts = line.split()
                meta = result["metadata"]
                for i, part in enumerate(parts):
                    if part == "Slot" and i + 1 < len(parts):
                        meta["time_slot"] = int(parts[i+1].rstrip(':,'))
                    elif part == "TG" and i + 1 < len(parts):
                        meta["talkgroup"] = int(parts[i+1].rstrip(':,'))
                    elif part == "RID" and i + 1 < len(parts):
                        meta["radio_id"] = int(parts[i+1].rstrip(':,'))
                    elif part in ("Group", "Private", "Emergency"):
                        meta["call_type"] = part.upper()
                    elif part == "Enc" or part == "Encrypted":
                        meta["encrypted"] = True

        return result if result["metadata"] else None

    def _validate_output(self, result: Dict) -> bool:
        """Check if decoder output contains useful metadata."""
        if not result:
            return False
        meta = result.get("metadata", {})
        return bool(meta.get("radio_id") or meta.get("talkgroup"))

    def _mock_decode(self, protocol: str, frequency: float) -> Dict:
        """Generate realistic mock decoder output."""
        import random
        radio_id = random.randint(3000001, 3000050)
        tg = random.choice([100, 101, 102, 200, 500, 501, 1000, 1001, 2000])
        call_types = ["GROUP", "PRIVATE", "GROUP", "GROUP", "EMERGENCY"]

        result = {
            "decoder": "mock_decoder",
            "protocol": protocol,
            "frequency": frequency,
            "metadata": {
                "radio_id": radio_id,
                "talkgroup": tg,
                "time_slot": random.choice([1, 2]),
                "call_type": random.choice(call_types),
                "color_code": random.choice([1, 2, 3]),
                "encrypted": random.random() < 0.15,
            },
            "raw_lines": [f"Mock {protocol} decode at {frequency} MHz"]
        }

        # 20% chance of GPS data
        if random.random() < 0.2:
            result["metadata"]["gps"] = {
                "latitude": 32.9 + random.uniform(-0.5, 0.5),
                "longitude": 13.18 + random.uniform(-0.3, 0.3),
                "altitude": random.uniform(10, 200),
                "speed": random.uniform(0, 80),
                "heading": random.uniform(0, 360),
            }

        # Mock decrypted audio (8kHz mono PCM, ~0.5s)
        if not result["metadata"].get("encrypted", False):
            result["audio_pcm"] = self._generate_mock_audio()

        return result

    async def _get_network_key(self, network_id: str) -> Optional[Dict]:
        """Fetch encryption key from backend API (cached)."""
        if network_id in self._key_cache:
            return self._key_cache[network_id]
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{BACKEND_URL}/api/networks/{network_id}/key"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._key_cache[network_id] = data
                        return data
        except Exception as e:
            log.warning("key_fetch.error", network_id=network_id, error=str(e))
        return None

    def _build_key_args(self, decoder_name: str, enc_type: str, enc_key: str) -> list:
        """Build CLI arguments for key injection per decoder."""
        if not enc_key:
            return []
        if decoder_name in ("dsdcc", "dsd"):
            return ["-K", enc_key]
        elif decoder_name == "op25":
            return ["--key", enc_key]
        elif decoder_name == "telive":
            return ["-k", enc_key]
        else:
            return ["--key", enc_key]

    def _generate_mock_audio(self) -> bytes:
        """Generate mock 8kHz mono PCM audio (tone burst ~0.5s)."""
        import struct
        sample_rate = 8000
        duration = 0.5
        freq = 440 + np.random.randint(-100, 100)
        t = np.arange(int(sample_rate * duration)) / sample_rate
        pcm = (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16)
        return pcm.tobytes()

    def invalidate_key_cache(self, network_id: str = None):
        """Clear cached keys (call when user updates a key)."""
        if network_id:
            self._key_cache.pop(network_id, None)
        else:
            self._key_cache.clear()
