"""Support for EDP re:dy sensors."""
import logging

from homeassistant.helpers.entity import Entity

try:
    from homeassistant.components.edp_redy import EdpRedyDevice, EDP_REDY
except ImportError:
    from custom_components.edp_redy import EdpRedyDevice, EDP_REDY

_LOGGER = logging.getLogger(__name__)

# Load power in watts (W)
ATTR_ACTIVE_POWER = 'active_power'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for Xiaomi devices."""
    session = hass.data[EDP_REDY]
    devices = []
    for device_pkid, device_json in session.modules_dict.items():
        if "HA_POWER_METER" not in device_json["Capabilities"]:
            continue
        devices.append(EdpRedySensor(session, device_json))

    add_devices(devices)


class EdpRedySensor(EdpRedyDevice, Entity):
    """Representation of a EDP re:dy sensor."""

    def __init__(self, session, device_json):
        """Initialize the sensor."""
        EdpRedyDevice.__init__(self, session, device_json)

        self._active_power = None
        self._name = "Power {0}".format(self._base_name)

        self._parse_data(device_json)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._active_power

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:flash"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return 'W'

    def _data_updated(self):
        if self._id in self._session.modules_dict:
            device_json = self._session.modules_dict[self._id]
            self._parse_data(device_json)
        else:
            self._is_available = False

        super()._data_updated()

    def _parse_data(self, data):
        """Parse data received from the server."""

        _LOGGER.debug("Sensor data: " + str(data))

        for state_var in data["StateVars"]:
            if state_var["Name"] == "ActivePower":
                try:
                    self._active_power = float(state_var["Value"]) * 1000
                except ValueError:
                    _LOGGER.error(
                        "Could not parse power for {0}".format(self._id))
                    self._active_power = 0
                    self._is_available = False
                else:
                    self._is_available = True
