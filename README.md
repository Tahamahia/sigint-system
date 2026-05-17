# SIGINT System — Automated Signals Intelligence for Radio Networks

A fully offline, Docker-deployed SIGINT system for monitoring DMR, TETRA, and P25 radio networks using HackRF/RTL-SDR hardware.

## Quick Start

```bash
# 1. Clone and enter the directory
cd "sdr system"

# 2. Start all services (mock mode by default)
docker compose up -d

# 3. Open the dashboard
open http://localhost:3000

# 4. Run the full test suite
bash scripts/run_tests.sh
```

## Architecture

| Service | Port | Description |
|---------|------|-------------|
| **Frontend** | 3000 | React dashboard with live log, topology graph, and GPS map |
| **Backend** | 4000 | Node.js REST API + WebSocket |
| **Middleware** | 5555 | Python SDR controller, DSP, and decoder pipeline |
| **Database** | 5432 | PostgreSQL with hierarchical radio network schema |

## Mock Mode

Set `MOCK_MODE=true` in `.env` to run without SDR hardware. The middleware generates synthetic DMR/TETRA/P25 data.

## Real SDR Hardware

1. Set `MOCK_MODE=false` in `.env`
2. Uncomment the `devices` and `privileged` lines in `docker compose.yml` under `middleware`
3. Connect your RTL-SDR or HackRF
4. Rebuild: `docker compose up -d --build middleware`

## Dashboard Features

- **📡 Live Feed**: Real-time signal log with protocol color coding (DMR=cyan, TETRA=magenta, P25=amber)
- **🔗 Topology**: D3.js force-directed graph showing Network → Base Station → Talkgroup → Radio hierarchy
- **🗺️ Map**: Leaflet map plotting GPS coordinates from LRRP/LIP packets
- **📻 SDR Status**: Device health, mode, frequency assignment

## Frequency Hopping Logic

- **Single SDR**: 500ms dwell on dead frequencies, 3s on active → full spectrum discovery sweep every hour
- **Multi SDR**: Pin SDR-1 to control channel, SDR-2+ sweep traffic channels dynamically
