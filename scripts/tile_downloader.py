#!/usr/bin/env python3
"""
Tile Downloader — Pre-downloads OSM XYZ tiles for offline use.
Libya Bounding Box: N:33.20, S:32.20, E:13.80, W:12.50 (Zoom 10-14)
"""
import os
import sys
import math
import time
import urllib.request

# Libya bounding box
NORTH, SOUTH = 33.20, 32.20
EAST, WEST = 13.80, 12.50
ZOOM_MIN, ZOOM_MAX = 10, 14
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "map_tiles")
USER_AGENT = "SIGINT-TileDownloader/1.0"

def lat_lon_to_tile(lat, lon, zoom):
    """Convert lat/lon to tile x,y at given zoom."""
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    lat_rad = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
    return x, y

def download_tiles():
    total = 0
    downloaded = 0
    skipped = 0
    errors = 0

    # Count tiles first
    for z in range(ZOOM_MIN, ZOOM_MAX + 1):
        x_min, y_min = lat_lon_to_tile(NORTH, WEST, z)
        x_max, y_max = lat_lon_to_tile(SOUTH, EAST, z)
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                total += 1

    print(f"=== OSM Tile Downloader ===")
    print(f"Area: Libya ({SOUTH}°N–{NORTH}°N, {WEST}°E–{EAST}°E)")
    print(f"Zoom: {ZOOM_MIN}–{ZOOM_MAX}")
    print(f"Total tiles: {total}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    for z in range(ZOOM_MIN, ZOOM_MAX + 1):
        x_min, y_min = lat_lon_to_tile(NORTH, WEST, z)
        x_max, y_max = lat_lon_to_tile(SOUTH, EAST, z)

        z_count = (x_max - x_min + 1) * (y_max - y_min + 1)
        print(f"[Z{z}] x={x_min}-{x_max}, y={y_min}-{y_max} ({z_count} tiles)")

        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                tile_dir = os.path.join(OUTPUT_DIR, str(z), str(x))
                tile_path = os.path.join(tile_dir, f"{y}.png")

                if os.path.exists(tile_path):
                    skipped += 1
                    continue

                os.makedirs(tile_dir, exist_ok=True)
                url = TILE_URL.format(z=z, x=x, y=y)

                try:
                    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        with open(tile_path, 'wb') as f:
                            f.write(resp.read())
                    downloaded += 1

                    pct = ((downloaded + skipped) / total) * 100
                    sys.stdout.write(f"\r  [{pct:5.1f}%] Downloaded: {downloaded} | Skipped: {skipped} | Errors: {errors}")
                    sys.stdout.flush()

                    # Respect OSM rate limit (max 2 req/sec)
                    time.sleep(0.5)

                except Exception as e:
                    errors += 1
                    print(f"\n  ✗ {url}: {e}")

        print()

    print()
    print(f"=== Complete ===")
    print(f"Downloaded: {downloaded} | Skipped: {skipped} | Errors: {errors}")
    print(f"Tiles saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    download_tiles()
