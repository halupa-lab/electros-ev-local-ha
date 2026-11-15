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
| Charging | Switch | Start / stop charging. Fails with an error when the charger does not get the command |
| Charging amps | Number (slider) | Set amperage 6–32 A |
| Charging timer | Sensor | Timer stored in the charger, e.g. `23:00–07:00`, or `вимкнено` (off). Attributes `enabled`, `start`, `end` |
| Charger clock offset | Sensor (s, diagnostic) | How far the charger clock is ahead (+) or behind (−) of HA; the timer runs on this clock. Attribute `charger_time` |
| Last charger event | Sensor | Last entry of the charger's event log (timer allow / forbid, programming, errors). Attributes `code`, `event_en` (language-independent name, e.g. `timer_charging_blocked`), `time`, `recent` |
| Last charger restart | Sensor (timestamp, diagnostic) | When the charger last started up (power cut or self-restart), from its event log, which starts again with "Режим роутера" (code 25). Attributes `count` (restarts seen, kept across HA restarts), `charger_log_start`. The history shows every restart |
| Last command to the charger | Sensor (diagnostic) | The last command HA sent: `почати 16 A`, `зупинити`, `таймер 23:00–07:00`, … Attributes `sent_at`, `delivered` |

Polling: every read is a new WebSocket connection to the charger, one at a time, closed properly. The interval (default 5 s) can be changed in the integration's **Configure** dialog.

Entity IDs are fixed (since v1.8.0): `switch.electros_charging`, `number.electros_charging_current`, `sensor.electros_status`, `sensor.electros_set_current`, `sensor.electros_measured_current`, `sensor.electros_voltage`, `sensor.electros_power`, `sensor.electros_timer`, `sensor.electros_clock_offset`, `sensor.electros_last_event`, `sensor.electros_last_restart`, `sensor.electros_last_command`. An install from before v1.8.0 keeps its old IDs until you press ↻ ("regenerate entity ID") in each entity's settings.

## Actions

| Action | What it does |
|---|---|
| `electros_ev_local.set_timer` | Sets the charging timer (`start`, `end`, e.g. `23:00` and `07:00`; the window may cross midnight) and the charger clock |
| `electros_ev_local.clear_timer` | Turns the timer off (the charger charges at any time) and sets the charger clock |
| `electros_ev_local.sync_clock` | Sets the charger clock and keeps the current timer |

The charger clock is always set to Home Assistant local time: the charger has one command for the clock and the timer together. After the command the integration reads the charger back and the action fails if the timer or the clock (±15 s) is not what was asked, so an automation can retry or notify. `config_entry_id` is needed only with more than one charger.

"Start" (Charging switch on) is a one-off override of the timer: the charger charges at once and the timer reads as off until "stop" or a timer command ends the override (unplugging does not end it); then the stored timer comes back by itself. The charger has no separate command for the current, so a new current while charging is sent with "start" too; when the charger was charging by its timer, the integration sends the same timer right after it, so the charge still stops at the timer end. The charger clock drifts about 15–20 s a day, so call `sync_clock` once a day.

```yaml
action: electros_ev_local.set_timer
data:
  start: "23:00"
  end: "07:00"
```

## How it works

Connects directly to the charger's built-in WebSocket server (`ws://<ip>/ws`).
No login required. Commands:
- Start: `start\n{index}\n0`
- Stop: `stop`
- Timer (the same command as "Задати" on the charger's web page; used by the actions below): `datetime\n<D.MM.YYYYTHH:MM:SS>\n<HH:MM start>\n<HH:MM stop>\n`, empty times = timer off. The same command also sets the charger clock.

Fields of the state frame, counted from the line `electros.org.ua`: +3 configured amps, +4 status code, +6 voltage, +8 power ×10, +11 charger clock, +22 / +23 timer start / stop, +26 event log (`HH:MM:SS code ...`).

## Disclaimer

This is an unofficial community integration, not affiliated with ElectroS.
Use at your own risk. The authors are not responsible for any damage.

## License

MIT
