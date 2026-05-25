# ElectroS EV Charger — Local Network Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Local network Home Assistant integration for **ElectroS EV** chargers.

Works **without internet** — connects directly to the charger via WebSocket on your local network.

> For the cloud-based version see: [electros-ev-ha-from-andriy](https://github.com/podzolkov/electros-ev-ha-from-andriy)

## Why local?

- Works when internet is down
- Faster response (local network)
- No dependency on electros.org.ua cloud service

## Requirements

- ElectroS EV charger accessible on your local network (e.g. `http://192.168.1.142/`)
- Home Assistant 2024.1+
- HACS installed

## Installation

### HACS (Custom Repository)

1. Open HACS in Home Assistant
2. Click **⋮** → **Custom repositories**
3. Add this repository URL, category: **Integration**
4. Click **Download**
5. Restart Home Assistant

### Manual

Copy `custom_components/electros_ev_local/` to your HA `config/custom_components/`

## Configuration

1. **Settings → Devices & Services → Add Integration**
2. Search for **ElectroS EV Charger (Local)**
3. Enter the charger's local IP address (e.g. `192.168.1.142`)
4. Port: `80` (default)
5. Update interval: `5` seconds (default)

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| Status | Sensor | Charger status |
| Configured current | Sensor (A) | Set charging amperage |
| Measured current | Sensor (A) | Actual current |
| Mains voltage | Sensor (V) | Grid voltage |
| Charging power | Sensor (W) | Calculated power |
| Charging | Switch | Start / stop charging |
| Charging amps | Number (slider) | Set amperage 6–32 A |

## How it works

Connects directly to the charger's built-in WebSocket server (`ws://<ip>/ws`).
No login required. Commands:
- Start: `start\n{index}\n0`
- Stop: `stop`

## Disclaimer

This is an unofficial community integration, not affiliated with ElectroS.
Use at your own risk. The authors are not responsible for any damage.

## License

MIT
