"""Platform for climate integration."""
from whirlpool.aircon import Aircon, Mode as AirconMode, FanSpeed as AirconFanSpeed
from whirlpool.auth import Auth

import logging

from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    FAN_HIGH,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_HORIZONTAL,
    SWING_OFF,
)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return
    auth: Auth = hass.data[DOMAIN]["auth"]
    said_list = auth.get_said_list()
    if not said_list:
        return
    devices = []
    for key in range(len(said_list)):
        aircon = AirConEntity(said_list[key], auth)
        await aircon._async_connect()
        devices.append(aircon)
        
    async_add_entities(devices, True)


class AirConEntity(ClimateEntity):
    """Representation of an air conditioner."""

    def __init__(self, said, auth: Auth):
        """Initialize the entity."""
        self._aircon = Aircon(auth, said, self.schedule_update_ha_state)

        self._supported_features = SUPPORT_TARGET_TEMPERATURE
        self._supported_features |= SUPPORT_FAN_MODE
        self._supported_features |= SUPPORT_SWING_MODE

    async def _async_connect(self):
        """Connect aircon to the cloud."""
        await self._aircon.connect()

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 16

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 30

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def name(self):
        """Return the name of the aircon."""
        return self._aircon._said  # TODO: return user-given-name from the API

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._aircon._said

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._aircon.get_online()

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._aircon.get_current_temp()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._aircon.get_temp()

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self._aircon.set_temp(kwargs.get(ATTR_TEMPERATURE))

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._aircon.get_current_humidity()

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._aircon.get_humidity()

    @property
    def target_humidity_step(self):
        """Return the supported step of target humidity."""
        return 10

    async def async_set_humidity(self, **kwargs):
        """Set new target humidity."""
        await self._aircon.set_humidity(kwargs.get(ATTR_HUMIDITY))

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return [HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_FAN_ONLY, HVAC_MODE_OFF]

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, fan."""
        if not self._aircon.get_power_on():
            return HVAC_MODE_OFF

        mode: AirconMode = self._aircon.get_mode()
        if mode == AirconMode.Cool:
            return HVAC_MODE_COOL
        elif mode == AirconMode.Heat:
            return HVAC_MODE_HEAT
        elif mode == AirconMode.Fan:
            return HVAC_MODE_FAN_ONLY

        return None

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._aircon.set_power_on(False)

        mode = None
        if hvac_mode == HVAC_MODE_COOL:
            mode = AirconMode.Cool
        elif hvac_mode == HVAC_MODE_HEAT:
            mode = AirconMode.Heat
        elif hvac_mode == HVAC_MODE_FAN_ONLY:
            mode = AirconMode.Fan

        if not mode:
            return

        await self._aircon.set_mode(mode)
        if not self._aircon.get_power_on():
            await self._aircon.set_power_on(True)

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return [FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def fan_mode(self):
        """Return the fan setting."""
        fanspeed = self._aircon.get_fanspeed()
        if fanspeed == AirconFanSpeed.Auto:
            return FAN_AUTO
        elif fanspeed == AirconFanSpeed.Low:
            return FAN_LOW
        elif fanspeed == AirconFanSpeed.Medium:
            return FAN_MEDIUM
        elif fanspeed == AirconFanSpeed.High:
            return FAN_HIGH
        return FAN_OFF

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        fanspeed = None
        if fan_mode == FAN_AUTO:
            fanspeed = AirconFanSpeed.Auto
        elif fan_mode == FAN_LOW:
            fanspeed = AirconFanSpeed.Low
        elif fan_mode == FAN_MEDIUM:
            fanspeed = AirconFanSpeed.Medium
        elif fan_mode == FAN_HIGH:
            fanspeed = AirconFanSpeed.High
        if not fanspeed:
            return
        await self._aircon.set_fanspeed(fanspeed)

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return [SWING_HORIZONTAL, SWING_OFF]

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return SWING_HORIZONTAL if self._aircon.get_h_louver_swing() else SWING_OFF

    async def async_set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        if swing_mode == SWING_HORIZONTAL:
            await self._aircon.set_h_louver_swing(True)
        else:
            await self._aircon.set_h_louver_swing(False)

    async def async_turn_on(self):
        """Turn device on."""
        await self._aircon.set_power_on(True)

    async def async_turn_off(self):
        """Turn device off."""
        await self._aircon.set_power_on(False)
