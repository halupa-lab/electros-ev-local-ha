# Changelog

## v1.6.0

- New read-only sensors from the charger's state frame: charging timer, charger clock offset, last charger event (attribute `event_en` with a language-independent event name for automations).
- Tests for the state frame parser and the new sensors (GitHub Actions).
- Fork of podzolkov/electros-ev-local-ha v1.5.2; domain and existing entities unchanged.
