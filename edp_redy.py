"""
Support for EDP re:dy.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/.../
"""

import aiohttp
import asyncio
import json
import logging

import async_timeout
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
                                 EVENT_HOMEASSISTANT_START)
from homeassistant.core import callback
from homeassistant.helpers import discovery, dispatcher, aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'edp_redy'
EDP_REDY = "edp_redy"
MODULES_UPDATE_TOPIC = '{0}_modules_update'.format(DOMAIN)

UPDATE_INTERVAL = 60
URL_BASE = "https://redy.edp.pt/EdpPortal/"
URL_LOGIN_PAGE = URL_BASE
URL_GET_SWITCH_MODULES = "{0}/HomeAutomation/GetSwitchModules".format(URL_BASE)
URL_SET_STATE_VAR = "{0}/HomeAutomation/SetStateVar".format(URL_BASE)

DEFAULT_TIMEOUT = 30

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


class EdpRedySession:
    """ Representation of a session to the service."""

    def __init__(self, hass, username, password):
        self._username = username
        self._password = password
        self._session = None
        self._hass = hass
        self.modules_dict = {}

    async def async_init_session(self):
        payload_auth = {'username': self._username,
                        'password': self._password,
                        'screenWidth': '1920', 'screenHeight': '1080'}

        try:
            # create session and fetch login page
            session = aiohttp_client.async_get_clientsession(self._hass)
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await session.get(URL_LOGIN_PAGE)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while accessing login page")
            return None

        if resp.status != 200:
            _LOGGER.error("Login page returned status code {0}"
                          .format(resp.status))
            return None

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await session.post(URL_LOGIN_PAGE, data=payload_auth)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while doing login post")
            return None

        if resp.status != 200:
            _LOGGER.error("Login post returned status code {0}"
                          .format(resp.status))
            return None

        return session

    async def async_fetch_data(self):
        if self._session is None:
            self._session = await self.async_init_session()

        if self._session is None:
            return False

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await self._session.post(URL_GET_SWITCH_MODULES,
                                                data={"filter": 1})
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while getting switch modules")
            return False
        if resp.status != 200:
            _LOGGER.error("Getting switch modules returned status code {0}"
                          .format(resp.status))
            return False

        # _LOGGER.debug("Fetched Data:\n" + r.text)

        try:
            raw_modules = json.loads(await resp.text())["Body"]["Modules"]
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Error parsing modules json. Received: \n {0}"
                          .format(await resp.text()))
            return False

        for module in raw_modules:
            self.modules_dict[module['PKID']] = module

        return True

    async def async_set_state_var(self, json_payload):
        if self._session is None:
            return False

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await self._session.post(URL_SET_STATE_VAR,
                                                json=json_payload)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while setting state var")
            return False
        if resp.status != 200:
            _LOGGER.error("Setting state var returned status code {0}"
                          .format(resp.status))
            return False

        return True


async def async_setup(hass, config):
    """Set up the EDP re:dy component."""

    session = EdpRedySession(hass, config[DOMAIN][CONF_USERNAME],
                             config[DOMAIN][CONF_PASSWORD])
    hass.data[EDP_REDY] = session

    async def async_update_and_sched(time):

        await session.async_fetch_data()
        dispatcher.async_dispatcher_send(hass, MODULES_UPDATE_TOPIC)

        # schedule next update
        async_track_point_in_time(hass, async_update_and_sched,
                                  time + timedelta(seconds=UPDATE_INTERVAL))

    async def start_component(event):
        _LOGGER.debug("Starting updates")

        await session.async_fetch_data()

        for component in ['switch']:
            await discovery.async_load_platform(hass, component, DOMAIN, {},
                                                config)

        async_track_point_in_time(hass, async_update_and_sched,
                                  dt_util.utcnow() + timedelta(
                                      seconds=UPDATE_INTERVAL))

    # only start fetching data after HA boots to prevent delaying the boot
    # process
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_component)

    return True


class EdpRedyDevice(Entity):
    """Representation a base re:dy device."""

    def __init__(self, session, device_json):
        """Initialize the device."""
        self._session = session
        self._state = None
        self._is_available = True
        self._device_state_attributes = {}
        self._id = device_json['PKID']
        self._unique_id = self._id
        self._name = device_json['Name'] if len(device_json['Name']) > 0 \
            else self._unique_id

        self._parse_data(device_json)

    async def async_added_to_hass(self):
        dispatcher.async_dispatcher_connect(
            self.hass, MODULES_UPDATE_TOPIC, self._data_updated)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def should_poll(self):
        """Return the polling state. No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes

    @callback
    def _data_updated(self):
        """Update state, trigger updates."""
        self.async_schedule_update_ha_state(True)

    def _parse_data(self, data):
        """Parse data received from the server."""
        raise NotImplementedError()


