# ElectroS EV Charger — Local Network Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Local network Home Assistant integration for **ElectroS EV** chargers.

> **Fork** of [podzolkov/electros-ev-local-ha](https://github.com/podzolkov/electros-ev-local-ha) (from v1.5.2). It adds the charger's own timer, clock and event log. Same domain and entity IDs as the original, so it can replace it without losing entities or history. Changes: [CHANGELOG.md](CHANGELOG.md).

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
3. Add `https://github.com/halupa-lab/electros-ev-local-ha`, category: **Integration**
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
| Charging timer | Sensor | Timer stored in the charger, e.g. `23:00–07:00`, or `вимкнено` (off). Attributes `enabled`, `start`, `end` |
| Charger clock offset | Sensor (s, diagnostic) | How far the charger clock is ahead (+) or behind (−) of HA; the timer runs on this clock. Attribute `charger_time` |
| Last charger event | Sensor | Last entry of the charger's event log (timer allow / forbid, programming, errors). Attributes `code`, `event_en` (language-independent name, e.g. `timer_charging_blocked`), `time`, `recent` |

## How it works

Connects directly to the charger's built-in WebSocket server (`ws://<ip>/ws`).
No login required. Commands:
- Start: `start\n{index}\n0`
- Stop: `stop`
- Timer (used by the charger's web page; not sent by this integration yet): `datetime\n<D.MM.YYYYTHH:MM:SS>\n<HH:MM start>\n<HH:MM stop>\n`, empty times = timer off. The same command also sets the charger clock.

Fields of the state frame, counted from the line `electros.org.ua`: +3 configured amps, +4 status code, +6 voltage, +8 power ×10, +11 charger clock, +22 / +23 timer start / stop, +26 event log (`HH:MM:SS code ...`).

## Disclaimer

This is an unofficial community integration, not affiliated with ElectroS.
Use at your own risk. The authors are not responsible for any damage.

## License

MIT
