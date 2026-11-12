# Changelog

## v1.6.1

- Start, stop and a new charging current now raise an error when the charger does not get the command (before, HA silently treated it as done). Scripts and automations stop at such a step, or can go on with `continue_on_error`.
- The charger clock offset is shown without decimals.

## v1.6.0

- New read-only sensors from the charger's state frame: charging timer, charger clock offset, last charger event (attribute `event_en` with a language-independent event name for automations).
- Tests for the state frame parser and the new sensors (GitHub Actions).
- Fork of podzolkov/electros-ev-local-ha v1.5.2; domain and existing entities unchanged.
