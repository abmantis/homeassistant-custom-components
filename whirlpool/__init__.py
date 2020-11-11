"""Whirlpool's Sixth Sense integration."""

from whirlpool.auth import Auth
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

DOMAIN = "whirlpool"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    auth = Auth(username, password)
    await auth.load_auth_file()

    hass.data[DOMAIN] = {"auth": auth}

    hass.helpers.discovery.load_platform("climate", DOMAIN, {}, config)

    return True