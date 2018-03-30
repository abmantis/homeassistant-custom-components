# """
# Creates sensors for EDP Re:dy power readings
# """

import aiohttp
import asyncio
import async_timeout
import json
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (ATTR_FRIENDLY_NAME, CONF_HOST,
                                 EVENT_HOMEASSISTANT_START)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=30): cv.positive_int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    class RedyHTMLParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self._json = ''

        def handle_data(self, data):
            if data.find('REDYMETER') != -1:
                self._json = data

        def json(self):
            return self._json

    host = config[CONF_HOST]
    url = 'http://{}:1234/api/devices'.format(host)

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

    def parse_nodes(json_nodes):
        for node in json_nodes:
            if "EMETER:POWER_APLUS" not in node:
                continue

            node_id = node["ID"]
            node_name = node["NAME"]
            node_power = node["EMETER:POWER_APLUS"]
            load_sensor(node_id, node_name, node_power, None)

    def parse_type(json, type_tag):
        if type_tag not in json:
            return

        for device in json[type_tag]:
            if "NODES" not in device:
                continue
            parse_nodes(device["NODES"])

    def parse_json(json):
        parse_type(json, "REDYMETER")
        parse_type(json, "ZBENDPOINT")

        if "EDPBOX" in json:
            edp_box_json = json["EDPBOX"]
            if len(edp_box_json) > 0:
                edpbox_data = edp_box_json[0]
                edpbox_id = edpbox_data["SMARTMETER_ID"]
                edpbox_power = edpbox_data["EMETER:POWER_APLUS"]
                edpbox_last_comm = edpbox_data["LAST_COMMUNICATION"]
                load_sensor(edpbox_id, "Smart Meter", edpbox_power, edpbox_last_comm)

    @asyncio.coroutine
    def async_update(time):
        """Fetch data from the redy box and update sensors."""

        try:
            # get the data from the box
            session = async_get_clientsession(hass)
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=hass.loop):
                resp = yield from session.get(url)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while accessing: %s", url)
            return

        if resp.status != 200:
            _LOGGER.error("%s not available", url)
            return

        data_html = yield from resp.text()

        try:
            html_parser = RedyHTMLParser()
            html_parser.feed(data_html)
            html_parser.close()
            html_json = html_parser.json()
            j = json.loads(html_json)

            new_sensors_list.clear()
            parse_json(j)
            if len(new_sensors_list) > 0:
                async_add_entities(new_sensors_list)

        except Exception as error:
            _LOGGER.error("Failed to load data from redy box: %s", error)

        # schedule next update
        async_track_point_in_time(hass, async_update, time + timedelta(
            seconds=config[CONF_UPDATE_INTERVAL]))

    @asyncio.coroutine
    def start_component(event):
        _LOGGER.debug("Starting updates")
        yield from async_update(dt_util.utcnow())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_component)

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
