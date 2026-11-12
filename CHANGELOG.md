# Changelog

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
