# """
# Creates sensors for EDP Re:dy power readings
# """
import asyncio
import json
import logging
import requests
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_HOST
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import (async_track_state_change,
                                         async_track_point_in_time)
from homeassistant.helpers.restore_state import async_get_last_state
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers import template as template_helper
from homeassistant.util import dt as dt_util

from html.parser import HTMLParser

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'edp_redy_local'
ATTR_LAST_COMMUNICATION = 'last_communication'
CONF_UPDATE_INTERVAL = 'update_interval'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=30): cv.positive_int,
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    class RedyHTMLParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self._json = ''

        def handle_data(self, data):
            if data.find('REDYMETER') != -1:
                self._json = data

        def json(self):
            return self._json

    sensors = {}
    new_sensors_list = []

    def load_sensor(sensor_id, name, power, last_communication):
        if sensor_id in sensors:
            sensors[sensor_id].update_data(power, last_communication)
            return

        # create new sensor
        sensor = EdpRedyLocalSensor(sensor_id, name, power, last_communication)
        sensors[sensor_id] = sensor
        new_sensors_list.append(sensor)

    def parse_data(json):
        for node in json["REDYMETER"][0]["NODES"]:
            if "EMETER:POWER_APLUS" not in node:
                continue

            node_id = node["ID"]
            node_name = node["NAME"]
            node_power = node["EMETER:POWER_APLUS"]
            load_sensor(node_id, node_name, node_power, None)

        edpbox_json = json["EDPBOX"][0]
        edpbox_id = edpbox_json["SMARTMETER_ID"]
        edpbox_power = edpbox_json["EMETER:POWER_APLUS"]
        edpbox_last_comm = edpbox_json["LAST_COMMUNICATION"]
        load_sensor(edpbox_id, "Smart Meter", edpbox_power, edpbox_last_comm)

    def update(time):
        """Fetch data from the redy box and update sensors."""
        host = config[CONF_HOST]

        # get the data from the box
        data_html = requests.get('http://{}:1234/api/devices'.format(host))

        html_parser = RedyHTMLParser()
        html_parser.feed(data_html.content.decode(data_html.apparent_encoding))
        html_parser.close()
        html_json = html_parser.json()
        j = json.loads(html_json)

        new_sensors_list.clear()
        parse_data(j)
        if len(new_sensors_list) > 0:
            async_add_devices(new_sensors_list)

        # schedule next update
        async_track_point_in_time(hass, update, time + timedelta(
            seconds=config[CONF_UPDATE_INTERVAL]))

    update(dt_util.utcnow())


class EdpRedyLocalSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, node_id, name, power, last_communication):
        """Set up sensor and add update callback to get data from websocket."""
        self._id = node_id
        self._name = 'Power {0}'.format(name)
        self._power = float(power)*1000
        self._last_comm = last_communication

    def update_data(self, power, last_communication):
        """Update the sensor's state."""
        self._power = float(power)*1000
        self._last_comm = last_communication
        self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._power

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return self._id

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return "power"

    # @property
    # def icon(self):
    #     """Return the icon to use in the frontend."""
    #     return self._sensor.sensor_icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return 'W'

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._last_comm:
            attr = {
                ATTR_LAST_COMMUNICATION: self._last_comm,
            }
            return attr
        return None
