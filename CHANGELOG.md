# Changelog

## v1.9.0

- New diagnostic sensor "Останній перезапуск зарядки" (`sensor.electros_last_restart`): when the charger last started up, read from its own event log (cleared at start-up, begins with "Режим роутера", code 25). Attribute `count` counts restarts and survives HA restarts; the history lists every restart. After a restart the charger has no stop: with no timer, or inside the timer window, it charges.
- New diagnostic sensor "Остання команда зарядці" (`sensor.electros_last_command`): the last start / stop / timer HA sent, with `sent_at` and `delivered`, to see whether restarts follow our commands.
- The `set_timer` action description no longer says a start cannot charge outside the window: a start is a one-off override of the timer.

## v1.8.1

- A new current while charging by the timer no longer switches the timer off. The charger takes the current only with "start", and "start" is a one-off override of the timer (it reads as off and the charge does not stop at the timer end). Now the integration sends the same timer right after it, so the charge goes on and stops at the timer end. In a one-off charge (timer already off) only the current is sent.
- README: how "start", "stop" and the timer work together (owner's tests on the real charger).

## v1.8.0

- Fixed English entity IDs without the IP: `switch.electros_charging`, `number.electros_charging_current`, `sensor.electros_status`, `sensor.electros_set_current`, `sensor.electros_measured_current`, `sensor.electros_voltage`, `sensor.electros_power`, `sensor.electros_timer`, `sensor.electros_clock_offset`, `sensor.electros_last_event`. Newer HA versions prefix the ID of a new entity with the device's area (e.g. `sensor.dvir_electros_…`); an ID set by the integration is used as is.
- Existing installs keep their old IDs until they are renamed: entity settings → "regenerate entity ID" (↻) gives the new one. History and statistics follow the rename. Update automations and dashboards that use the old IDs at the same time.

## v1.7.0

- New actions `electros_ev_local.set_timer`, `electros_ev_local.clear_timer` and `electros_ev_local.sync_clock`. Each one also sets the charger clock to Home Assistant time, then reads the charger back and fails with an error if the timer or the clock is not what was asked.
- `sync_clock` keeps the timer that is in the charger and refuses to run when the timer cannot be read (re-sending an unreadable timer would clear it).

## v1.6.1

- Start, stop and a new charging current now raise an error when the charger does not get the command (before, HA silently treated it as done). Scripts and automations stop at such a step, or can go on with `continue_on_error`.
- The charger clock offset is shown without decimals.

## v1.6.0

- New read-only sensors from the charger's state frame: charging timer, charger clock offset, last charger event (attribute `event_en` with a language-independent event name for automations).
- Tests for the state frame parser and the new sensors (GitHub Actions).
- Fork of podzolkov/electros-ev-local-ha v1.5.2; domain and existing entities unchanged.
