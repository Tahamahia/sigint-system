"""
Mock Metadata Generator — Direct JSON metadata for testing backend API.
"""
import json
import random
import sys

def generate_batch(count=50):
    events = []
    protocols = ["DMR", "TETRA", "P25"]
    for _ in range(count):
        proto = random.choice(protocols)
        events.append({
            "radio_id": random.randint(3000001, 3000050),
            "talkgroup": random.choice([100, 101, 200, 500, 1000, 2000]),
            "time_slot": random.choice([1, 2]),
            "call_type": random.choice(["GROUP", "PRIVATE", "EMERGENCY"]),
            "color_code": random.randint(1, 3),
            "protocol": proto,
            "frequency": round(random.uniform(400, 900), 4),
            "encrypted": random.random() < 0.1,
            "source_decoder": "mock_decoder",
        })
    return events

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    for evt in generate_batch(count):
        print(json.dumps(evt))
