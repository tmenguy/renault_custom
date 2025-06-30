"""Support for Renault sensors."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, cast

try:
    from .renault_api.kamereon.models import (
        KamereonVehicleBatteryStatusData,
        KamereonVehicleCockpitData,
        KamereonVehicleHvacStatusData,
        KamereonVehicleLocationData,
        KamereonVehicleResStateData,
    )
    from .renault_api.kamereon.enums import ChargeState, PlugState
except Exception:  # pylint: disable=broad-except
    from renault_api.kamereon.models import (
        KamereonVehicleBatteryStatusData,
        KamereonVehicleCockpitData,
        KamereonVehicleHvacStatusData,
        KamereonVehicleLocationData,
        KamereonVehicleResStateData,
    )
    from renault_api.kamereon.enums import ChargeState, PlugState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    ATTR_MODEL_ID, STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import as_utc, parse_datetime

from . import RenaultConfigEntry
from .coordinator import T
from .entity import RenaultDataEntity, RenaultDataEntityDescription
from .renault_vehicle import RenaultVehicleProxy


LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RenaultSensorEntityDescription(
    SensorEntityDescription, RenaultDataEntityDescription, Generic[T]
):
    """Class describing Renault sensor entities."""

    data_key: str
    entity_class: type[RenaultSensor[T]]
    condition_lambda: Callable[[RenaultVehicleProxy], bool] | None = None
    requires_fuel: bool = False
    value_lambda: Callable[[RenaultSensor[T]], StateType | datetime] | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    entities: list[RenaultSensor[Any]] = [
        description.entity_class(vehicle, description)
        for vehicle in config_entry.runtime_data.vehicles.values()
        for description in SENSOR_TYPES
        if description.coordinator in vehicle.coordinators
        and (not description.requires_fuel or vehicle.details.uses_fuel())
        and (not description.condition_lambda or description.condition_lambda(vehicle))
    ]
    async_add_entities(entities)


class RenaultSensor(RenaultDataEntity[T], SensorEntity):
    """Mixin for sensor specific attributes."""

    entity_description: RenaultSensorEntityDescription[T]
    _private_data: dict | None = None

    @property
    def data(self) -> StateType:
        """Return the state of this entity."""
        return self._get_data_attr(self.entity_description.data_key)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of this entity."""
        if self.data is None:
            return None
        if self.entity_description.value_lambda is None:
            return self.data
        return self.entity_description.value_lambda(self)

def _get_battery_level(entity: RenaultSensor[T]) -> StateType:
    """Return the battery_level of this entity."""

    percent_value = entity.data

    if percent_value is not None and entity.vehicle.device_info.get(ATTR_MODEL_ID, "") == "X071VE":

        orig_value = percent_value
        if entity._private_data is None:
            entity._private_data = {}

        data = cast(KamereonVehicleBatteryStatusData, entity.coordinator.data)
        charging_status = data.get_charging_status()
        plug_status = data.get_plug_status()
        autonomy = entity._get_data_attr("batteryAutonomy")

        if charging_status is None:
            charging_status = ChargeState.UNAVAILABLE

        if plug_status is None:
            plug_status = PlugState.PLUG_UNKNOWN

        if percent_value >= 100:
            # for the twingo III there is a known issue with the battery level when at 100% : it can be completely erroneous
            # in this case we first check if charge_status is defined

            prev_status = entity._private_data.get("last_charging_available_status", ChargeState.UNAVAILABLE)

            # if charge eneded by the car ... assume the battery is full so 100% is ok!
            if charging_status == ChargeState.CHARGE_ENDED or prev_status == ChargeState.CHARGE_ENDED:
                entity._private_data["had_a_good_100"] = True
            elif entity._private_data.get("had_a_good_100", False) is False:

                # from what we can see, the state WAITING_FOR_CURRENT_CHARGE when at 100% indicates an error
                # same for a bad or unknown plug state
                if (
                    charging_status == ChargeState.WAITING_FOR_CURRENT_CHARGE
                    or charging_status == ChargeState.UNAVAILABLE
                    or plug_status == PlugState.PLUG_UNKNOWN
                ):
                    # if the car is not charging, we assume that the battery is not full
                    LOGGER.warning(f"Twingo III 100% battery fix due to charging status {charging_status} or plug_status {plug_status}")
                    percent_value = None


                if percent_value is not None and entity._private_data.get("last_non_full_battery_value_timestamp") is not None:
                    # we will check that the battery couldn't have been charged to 100% in the meantime
                    delta_h = ((datetime.now() - entity._private_data["last_non_full_battery_value_timestamp"]).total_seconds())/3600

                    # the twingo has a battery of 22kWh and a maximum charging power of 22kW
                    charge_power = (((percent_value - entity._private_data["last_non_full_battery_value"])/100.0)*(22))/delta_h

                    # maximum charging power of 22kW for the twingo
                    if charge_power > 22:
                        LOGGER.warning(
                            f"Twingo III 100% battery fix prev value: {entity._private_data["last_non_full_battery_value"]}% {(datetime.now() - entity._private_data["last_non_full_battery_value_timestamp"])} ago "
                        )
                        percent_value = None


                if percent_value is not None and entity._private_data.get("prev_value") is not None:
                    if entity._private_data.get("prev_value") < 100:
                        # ok we where not at 100% before, we are now : it is a transition ... but shouldn't be if not charging!
                        if prev_status != ChargeState.CHARGE_IN_PROGRESS and charging_status != ChargeState.CHARGE_IN_PROGRESS:
                            # we are not charging and we are at 100% : this is a bad transition
                            # we will set the value to None
                            LOGGER.warning(
                                f"Twingo III 100% battery fix not charging transition: {prev_status} {charging_status} % "
                            )
                            percent_value = None

                if percent_value is not None:
                    if autonomy is None or autonomy < 175:
                        # if the autonomy is less than 175km ... we a 100% vale, we assume that the battery is not full
                        # we can use a direct hard coded constant as the twingo III has a known unique 22kWh battery
                        # and a unique motor and consumption
                        # ex of battery_status with this issue, the renault application shows 100% erroneously too:
                        # {"data":{"id":"VF1AAAAAAAAAAAAAA","attributes":{"timestamp":"2025-05-02T03:16:45Z","batteryLevel":100,"batteryAutonomy":41,"plugStatus":1,"chargingStatus":0.3,"chargingRemainingTime":15}}}
                        LOGGER.warning(f"Twingo III 100% battery fix autonomy: {autonomy}km")
                        percent_value = None

                if prev_status == ChargeState.CHARGE_IN_PROGRESS or charging_status == ChargeState.CHARGE_IN_PROGRESS:
                    entity._private_data["had_a_charge_during_100_period"] = True

                if percent_value is None:
                    entity._private_data["had_abnormal_transition_100"] = True
                elif entity._private_data.get("had_abnormal_transition_100", False) is True:
                    if entity._private_data.get("had_a_charge_during_100_period", False) is True:
                        # so 100 is possible ...even if it was not before
                        pass
                    else:
                        percent_value = None

                # possible value fix
                if autonomy is not None and int(entity._private_data.get(("last_non_full_autonomy_value", 500))) == int(autonomy):
                    # if the autonomy is the same as the last non full autonomy value, we assume that the battery is not full
                    # this is a fix for the twingo III where the autonomy is not updated when at 100%

                    percent_value = entity._private_data.get("last_non_full_battery_value")
                    LOGGER.warning(
                        f"Twingo III 100% battery fix autonomy: {autonomy}km same as last non full autonomy value, return percent_value: {percent_value}% "
                    )

        else:
            entity._private_data["last_non_full_autonomy_value"] = entity._get_data_attr("batteryAutonomy")
            entity._private_data["last_non_full_battery_value"] = orig_value
            entity._private_data["last_non_full_battery_value_timestamp"] = datetime.now()
            entity._private_data["had_abnormal_transition_100"] = False
            entity._private_data["had_a_good_100"] = False
            entity._private_data["had_a_charge_during_100_period"] = False

        if charging_status != ChargeState.UNAVAILABLE:
            entity._private_data["last_charging_available_status"] = charging_status

        entity._private_data["prev_value"] = orig_value


    return percent_value



def _get_charging_power(entity: RenaultSensor[T]) -> StateType:
    """Return the charging_power of this entity."""
    return cast(float, entity.data) / 1000


def _get_charge_state_formatted(entity: RenaultSensor[T]) -> str | None:
    """Return the charging_status of this entity."""
    data = cast(KamereonVehicleBatteryStatusData, entity.coordinator.data)
    charging_status = data.get_charging_status() if data else None
    return charging_status.name.lower() if charging_status else None


def _get_plug_state_formatted(entity: RenaultSensor[T]) -> str | None:
    """Return the plug_status of this entity."""
    data = cast(KamereonVehicleBatteryStatusData, entity.coordinator.data)
    plug_status = data.get_plug_status() if data else None
    return plug_status.name.lower() if plug_status else None


def _get_rounded_value(entity: RenaultSensor[T]) -> float:
    """Return the rounded value of this entity."""
    return round(cast(float, entity.data))


def _get_utc_value(entity: RenaultSensor[T]) -> datetime:
    """Return the UTC value of this entity."""
    original_dt = parse_datetime(cast(str, entity.data))
    if TYPE_CHECKING:
        assert original_dt is not None
    return as_utc(original_dt)


SENSOR_TYPES: tuple[RenaultSensorEntityDescription[Any], ...] = (
    RenaultSensorEntityDescription(
        key="battery_level",
        coordinator="battery",
        data_key="batteryLevel",
        device_class=SensorDeviceClass.BATTERY,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_lambda=_get_battery_level,
    ),
    RenaultSensorEntityDescription(
        key="charge_state",
        coordinator="battery",
        data_key="chargingStatus",
        translation_key="charge_state",
        device_class=SensorDeviceClass.ENUM,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        options=[
            "not_in_charge",
            "waiting_for_a_planned_charge",
            "charge_ended",
            "waiting_for_current_charge",
            "energy_flap_opened",
            "charge_in_progress",
            "charge_error",
            "unavailable",
        ],
        value_lambda=_get_charge_state_formatted,
    ),
    RenaultSensorEntityDescription(
        key="charging_remaining_time",
        coordinator="battery",
        data_key="chargingRemainingTime",
        device_class=SensorDeviceClass.DURATION,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="charging_remaining_time",
    ),
    RenaultSensorEntityDescription(
        # For vehicles that DO NOT report charging power in watts, this seems to
        # correspond to the maximum power that would be admissible by the car based
        # on the battery state, regardless of the type of charger.
        key="charging_power",
        condition_lambda=lambda a: not a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        data_key="chargingInstantaneousPower",
        device_class=SensorDeviceClass.POWER,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="admissible_charging_power",
    ),
    RenaultSensorEntityDescription(
        # For vehicles that DO report charging power in watts, this is the power
        # effectively being transferred to the car.
        key="charging_power",
        condition_lambda=lambda a: a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        data_key="chargingInstantaneousPower",
        device_class=SensorDeviceClass.POWER,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_lambda=_get_charging_power,
        translation_key="charging_power",
    ),
    RenaultSensorEntityDescription(
        key="plug_state",
        coordinator="battery",
        data_key="plugStatus",
        translation_key="plug_state",
        device_class=SensorDeviceClass.ENUM,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        options=[
            "unplugged",
            "plugged",
            "plugged_waiting_for_charge",
            "plug_error",
            "plug_unknown",
        ],
        value_lambda=_get_plug_state_formatted,
    ),
    RenaultSensorEntityDescription(
        key="battery_autonomy",
        coordinator="battery",
        data_key="batteryAutonomy",
        device_class=SensorDeviceClass.DISTANCE,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_autonomy",
    ),
    RenaultSensorEntityDescription(
        key="battery_available_energy",
        coordinator="battery",
        data_key="batteryAvailableEnergy",
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        translation_key="battery_available_energy",
    ),
    RenaultSensorEntityDescription(
        key="battery_temperature",
        coordinator="battery",
        data_key="batteryTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_temperature",
    ),
    RenaultSensorEntityDescription(
        key="battery_last_activity",
        coordinator="battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="timestamp",
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        entity_registry_enabled_default=False,
        value_lambda=_get_utc_value,
        translation_key="battery_last_activity",
    ),
    RenaultSensorEntityDescription(
        key="mileage",
        coordinator="cockpit",
        data_key="totalMileage",
        device_class=SensorDeviceClass.DISTANCE,
        entity_class=RenaultSensor[KamereonVehicleCockpitData],
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_lambda=_get_rounded_value,
        translation_key="mileage",
    ),
    RenaultSensorEntityDescription(
        key="fuel_autonomy",
        coordinator="cockpit",
        data_key="fuelAutonomy",
        device_class=SensorDeviceClass.DISTANCE,
        entity_class=RenaultSensor[KamereonVehicleCockpitData],
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        requires_fuel=True,
        value_lambda=_get_rounded_value,
        translation_key="fuel_autonomy",
    ),
    RenaultSensorEntityDescription(
        key="fuel_quantity",
        coordinator="cockpit",
        data_key="fuelQuantity",
        device_class=SensorDeviceClass.VOLUME,
        entity_class=RenaultSensor[KamereonVehicleCockpitData],
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
        requires_fuel=True,
        value_lambda=_get_rounded_value,
        translation_key="fuel_quantity",
    ),
    RenaultSensorEntityDescription(
        key="outside_temperature",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TEMPERATURE,
        data_key="externalTemperature",
        entity_class=RenaultSensor[KamereonVehicleHvacStatusData],
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outside_temperature",
    ),
    RenaultSensorEntityDescription(
        key="hvac_soc_threshold",
        coordinator="hvac_status",
        data_key="socThreshold",
        entity_class=RenaultSensor[KamereonVehicleHvacStatusData],
        native_unit_of_measurement=PERCENTAGE,
        translation_key="hvac_soc_threshold",
    ),
    RenaultSensorEntityDescription(
        key="hvac_last_activity",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="lastUpdateTime",
        entity_class=RenaultSensor[KamereonVehicleHvacStatusData],
        entity_registry_enabled_default=False,
        translation_key="hvac_last_activity",
        value_lambda=_get_utc_value,
    ),
    RenaultSensorEntityDescription(
        key="location_last_activity",
        coordinator="location",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="lastUpdateTime",
        entity_class=RenaultSensor[KamereonVehicleLocationData],
        entity_registry_enabled_default=False,
        translation_key="location_last_activity",
        value_lambda=_get_utc_value,
    ),
    RenaultSensorEntityDescription(
        key="res_state",
        coordinator="res_state",
        data_key="details",
        entity_class=RenaultSensor[KamereonVehicleResStateData],
        translation_key="res_state",
    ),
    RenaultSensorEntityDescription(
        key="res_state_code",
        coordinator="res_state",
        data_key="code",
        entity_class=RenaultSensor[KamereonVehicleResStateData],
        entity_registry_enabled_default=False,
        translation_key="res_state_code",
    ),
)
