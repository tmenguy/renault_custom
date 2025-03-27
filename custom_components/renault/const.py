"""Constants for the Renault component."""

from homeassistant.const import Platform

DOMAIN = "renault"

CONF_LOCALE = "locale"
CONF_KAMEREON_ACCOUNT_ID = "kamereon_account_id"

# normal number of allowed calls per seconds to the API
MAX_CALLS_PER_HOURS = 100

# If throttled time to pause the updates, in seconds
COOLING_UPDATES_SECONDS = 60*15

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.SENSOR,
]
