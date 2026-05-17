"""
Mock SDR Stream — Simulated SDR data generator for testing.
Feeds the middleware pipeline with realistic synthetic data.
"""
import asyncio
import json
import random
import time
import sys
import os
import argparse
import httpx

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:4000")

# Realistic radio network simulation parameters
NETWORKS = [
    {"name": "Metro DMR Net", "protocol": "DMR", "freq_base": 460.0, "channels": 6},
    {"name": "Regional TETRA", "protocol": "TETRA", "freq_base": 390.0, "channels": 4},
    {"name": "County P25", "protocol": "P25", "freq_base": 855.0, "channels": 5},
]

RADIOS = [{"id": 3000001 + i, "gps": i % 3 == 0} for i in range(50)]
TALKGROUPS = [100, 101, 102, 200, 500, 501, 502, 1000, 1001, 2000, 2001]
GPS_CENTER = (33.7490, -84.3880)  # Atlanta, GA


def generate_signal_event():
    net = random.choice(NETWORKS)
    channel = random.randint(0, net["channels"] - 1)
    freq = round(net["freq_base"] + channel * 0.0125, 4)
    radio = random.choice(RADIOS)
    tg = random.choice(TALKGROUPS)

    event = {
        "frequency": freq,
        "bandwidth_khz": 12.5 if net["protocol"] != "TETRA" else 25.0,
        "snr_db": round(random.uniform(8, 35), 1),
        "power_dbm": round(random.uniform(-80, -40), 1),
        "protocol_guess": net["protocol"],
        "protocol_confidence": round(random.uniform(0.6, 0.95), 3),
    }
    return event, net, radio, tg


def generate_metadata_event(net, radio, tg):
    call_types = ["GROUP", "GROUP", "GROUP", "PRIVATE", "EMERGENCY"]
    meta = {
        "radio_id": radio["id"],
        "talkgroup": tg,
        "time_slot": random.choice([1, 2]),
        "call_type": random.choice(call_types),
        "color_code": random.choice([1, 2, 3]),
        "protocol": net["protocol"],
        "frequency": round(net["freq_base"] + random.uniform(0, 0.075), 4),
        "encrypted": random.random() < 0.1,
        "source_decoder": "mock_decoder",
    }
    return meta


def generate_gps_event(radio):
    if not radio["gps"]:
        return None
    if random.random() > 0.3:  # 30% chance of GPS report
        return None
    return {
        "radio_id": radio["id"],
        "latitude": round(GPS_CENTER[0] + random.uniform(-0.3, 0.3), 6),
        "longitude": round(GPS_CENTER[1] + random.uniform(-0.3, 0.3), 6),
        "altitude": round(random.uniform(200, 500), 1),
        "speed_kmh": round(random.uniform(0, 120), 1),
        "heading": round(random.uniform(0, 360), 1),
        "source_protocol": "LRRP" if random.random() > 0.5 else "LIP",
    }


async def run_test_mode(duration: int = 30):
    """Run in test mode: generate events and push to backend."""
    print(f"[MOCK] Starting test mode for {duration}s → {BACKEND_URL}")
    start = time.time()
    stats = {"signals": 0, "metadata": 0, "gps": 0, "errors": 0}

    async with httpx.AsyncClient(timeout=10) as client:
        while time.time() - start < duration:
            try:
                signal_evt, net, radio, tg = generate_signal_event()

                # Push signal log
                resp = await client.post(f"{BACKEND_URL}/api/signals", json=signal_evt)
                if resp.status_code in (200, 201):
                    stats["signals"] += 1

                # Push metadata
                meta = generate_metadata_event(net, radio, tg)
                resp = await client.post(f"{BACKEND_URL}/api/signals/metadata", json=meta)
                if resp.status_code in (200, 201):
                    stats["metadata"] += 1

                # Maybe push GPS
                gps = generate_gps_event(radio)
                if gps:
                    resp = await client.post(f"{BACKEND_URL}/api/gps", json=gps)
                    if resp.status_code in (200, 201):
                        stats["gps"] += 1

                await asyncio.sleep(random.uniform(0.1, 0.5))

            except Exception as e:
                stats["errors"] += 1
                print(f"[MOCK] Error: {e}")
                await asyncio.sleep(1)

    print(f"[MOCK] Test complete. Stats: {json.dumps(stats, indent=2)}")
    return stats


async def run_stdout_mode():
    """Output mock events to stdout as JSON lines."""
    print("[MOCK] Streaming to stdout (Ctrl+C to stop)", file=sys.stderr)
    try:
        while True:
            signal_evt, net, radio, tg = generate_signal_event()
            meta = generate_metadata_event(net, radio, tg)
            combined = {**signal_evt, "metadata": meta}

            gps = generate_gps_event(radio)
            if gps:
                combined["gps"] = gps

            print(json.dumps(combined))
            sys.stdout.flush()
            await asyncio.sleep(random.uniform(0.2, 1.0))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock SDR Stream Generator")
    parser.add_argument("--mode", choices=["test", "stdout"], default="test")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--backend", type=str, default=BACKEND_URL)
    args = parser.parse_args()

    BACKEND_URL = args.backend

    if args.mode == "test":
        asyncio.run(run_test_mode(args.duration))
    else:
        asyncio.run(run_stdout_mode())
