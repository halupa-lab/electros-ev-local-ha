"""Fixed English entity IDs for the charger's entities."""

from __future__ import annotations


def device_name(host: str) -> str:
    return f"ElectroS Local ({host})"


def suggested_entity_id(domain: str, key: str) -> str:
    """Fixed entity ID, e.g. switch.electros_charging.

    Newer HA versions build the ID of a NEW entity from area + device + name (a charger in area "Двір" got
    sensor.dvir_electros_…), so automations break after the integration is re-added or the device moves.
    An ID set by the integration is used verbatim. It applies when the entity is first registered, and to
    the "regenerate entity ID" button (↻) in the entity settings; existing IDs are not changed by themselves.
    No IP in the ID: there is one charger, and its IP may change. A second charger gets HA's "_2" suffix.
    """
    return f"{domain}.electros_{key}"
