"""Constants for the Renault component."""

from typing import Final

from homeassistant.const import Platform

DOMAIN = "renault"


class RenaultConfigurationKeys:
    """Configuration keys."""

    KAMEREON_ACCOUNT_ID: Final = "kamereon_account_id"
    LOCALE: Final = "locale"
    LOGIN_TOKEN: Final = "login_token"
    PASSWORD: Final = "password"
    USERNAME: Final = "username"


# normal number of allowed calls per hour to the API
# for a single car and the 7 coordinators, 60 is a scan every 7mn
# We can safely bump it to 100 with the smoothing
MAX_CALLS_PER_HOURS = 100

# If throttled time to pause the updates, in seconds
COOLING_UPDATES_SECONDS = 60 * 15  # 15 minutes

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]
