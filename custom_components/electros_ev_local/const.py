"""Constants for ElectroS EV Charger Local integration."""

DOMAIN = "electros_ev_local"
DEFAULT_SCAN_INTERVAL = 5  # local network — can poll faster

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 80
DEFAULT_WS_PATH = "/ws"

AMP_TO_INDEX = {
    32: 0,
    30: 1,
    28: 2,
    26: 3,
    24: 4,
    22: 5,
    20: 6,
    18: 7,
    16: 8,
    14: 9,
    12: 10,
    10: 11,
    8: 12,
    6: 13,
}

SUPPORTED_AMPS = sorted(AMP_TO_INDEX)

# Status codes parsed from local WebSocket data
# Will be refined once we see live charging data
STATUS_TEXT = {
    "0": "Очікування авто",
    "1": "Авто підключено",
    "2": "Заряджає",
    "3": "Помилка зарядки",
    "4": "Зарядку заблоковано",
    "5": "Низька напруга мережі",
    "6": "Помилка зв'язку",
    "7": "Офлайн",
    "16": "Витік струму",
}

STATUS_TEXT_EN = {
    "0": "waiting_for_vehicle",
    "1": "vehicle_connected_idle",
    "2": "charging",
    "3": "charging_fault",
    "4": "charging_blocked",
    "5": "mains_voltage_low",
    "6": "charger_communication_fault",
    "7": "offline",
    "16": "leakage_current_fault",
}
