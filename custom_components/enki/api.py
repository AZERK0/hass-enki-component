"""Enki API."""

import aiohttp
from dataclasses import dataclass
from typing import Any
import time
import uuid

from .const import (
    LOGGER,
    ENKI_OIDC_URL,
    ENKI_URL,
    ENKI_HOME_API_KEY,
    ENKI_BFF_API_KEY,
    ENKI_NODE_API_KEY,
    ENKI_REFERENTIEL_API_KEY,
    ENKI_LIGHTS_API_KEY)

proxy = None
ENKI_USER_AGENT = "Enki/389 CFNetwork/3860.500.112 Darwin/25.4.0"

def _session():
    return aiohttp.ClientSession(
        headers={
            "User-Agent": ENKI_USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "fr-FR,fr;q=0.9",
        },
        skip_auto_headers={"User-Agent"},
    )

@dataclass
class Device:
    """API device."""
    home_id: str
    device_id: str
    node_id: str
    device_name: str

class API:
    """Class for Enki API."""

    def __init__(self, user: str, pwd: str) -> None:
        """Initialise."""
        self.user = user
        self.pwd = pwd

    @property
    def controller_name(self) -> str:
        """Return the name of the controller."""
        return self.user

    async def check_connected(self) -> bool:
        """Tell if token is still valid"""
        if not hasattr(self, '_access_token') or time.time() > self._tokenExpiresTime:
            await self.connect()
        return True

    async def connect(self) -> bool:
        """Connect to the Enki API."""
        try:
            async with _session() as session, session.request(
                method="POST",
                url=ENKI_OIDC_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                         "X-Correlation-Id": f"iOS_{str(uuid.uuid4()).upper()}"},
                data={"grant_type": "password",
                      "client_id": "enki-front",
                      "username": self.user,
                      "password": self.pwd},
                proxy=proxy,) as resp:

                    response = await resp.json()
                    if resp.status == 200:
                        LOGGER.debug("connect : " + str(response))
                        self._access_token = response["access_token"]
                        self._refresh_token = response["refresh_token"]
                        self._token_type = response["token_type"]
                        self._tokenExpiresTime = time.time() + response["expires_in"]
                        return True
                    else:
                        LOGGER.error("Error connecting to api. status %s, response %s", resp.status, str(response))
                        raise APIAuthError("Error connecting to api. Invalid username or password.")
        except APIAuthError:
            raise
        except Exception as e:
            raise APIConnectionError("Error connecting to api : " + repr(e))

# *******************************************************
    async def get_homes(self):
        """Get list of homes."""
        await self.check_connected()
        homes = []
        async with _session() as session, session.request(
             method="GET",
             url=f"{ENKI_URL}/api-enki-home-prod/v1/homes",
             headers={"Authorization": f"{self._token_type} {self._access_token}",
                      "X-Gateway-APIKey": ENKI_HOME_API_KEY},
             proxy=proxy,) as resp:

                response = await resp.json()
                if resp.status == 200:
                    LOGGER.debug("get_homes : " + str(response))
                    for home in response["items"]:
                        homes.append(home["id"])
                    return homes
                else:
                    LOGGER.error("Error on get_homes. status %s, response %s", resp.status, str(response))
                    raise ValueError("bad credentials")

    def merge_properties(self, device, properties):
        for prop in properties:
            if prop != "id":
                device[prop] = properties[prop]

    async def get_items_in_section_for_home(self, home_id) -> list[dict[str, Any]]:
        """Get sections in home."""
        await self.check_connected()
        async with _session() as session, session.request(
             method="GET",
             url=f"{ENKI_URL}/api-enki-mobile-bff-prod/v1/dashboard/homes/{home_id}?hasGroups=true",
             headers={"Authorization": f"{self._token_type} {self._access_token}",
                      "X-Gateway-APIKey": ENKI_BFF_API_KEY},
             proxy=proxy,) as resp:
            devices = []
            response = await resp.json()
            if resp.status == 200:
                LOGGER.debug("get_items_in_section_for_home : " + str(response))
                for section in response["sections"]:
                    for item in section["items"]:
                        if 'deviceId' not in item["metadata"].keys():
                            continue
                        device = {
                            "homeId": home_id,
                            "deviceId": item["metadata"]["deviceId"],
                            "nodeId": item["metadata"]["nodeId"],
                            "deviceName": item["title"]["label"],
                            "state": item["state"],
                            "isEnabled": item["isEnabled"]
                        }
                        devices.append(device)

                        node_info = await self.get_node(home_id, device.get("nodeId"))
                        self.merge_properties(device, node_info)

                        device_info = await self.get_device(device.get("deviceId"))
                        self.merge_properties(device, device_info)

                        await self.refresh_device(device)

                        LOGGER.debug("device : " + repr(device))
                return devices
            else:
                LOGGER.error("Error on get_items_in_section_for_home. status %s, response %s", resp.status, str(response))
                raise ValueError("bad credentials")

    async def refresh_device(self, device):
        """Update device details"""
        device_info = await self.get_device(device.get("deviceId"))
        self.merge_properties(device, device_info)
        if device["type"] == "lights" and device["isEnabled"]:
            light_details = await self.get_light_details(device.get("homeId"), device.get("nodeId"))
            self.merge_properties(device, light_details)
        return device

    async def get_node(self, home_id, node_id):
        """Get details on a node."""
        await self.check_connected()
        async with _session() as session, session.request(
            method="GET",
            url=f"{ENKI_URL}/api-enki-node-agg-prod/v1/nodes/{node_id}",
            headers={"Authorization": f"{self._token_type} {self._access_token}",
                    "X-Gateway-APIKey": ENKI_NODE_API_KEY,
                    "homeId": f"{home_id}"},
            proxy=proxy,) as resp:

                response = await resp.json()
                if resp.status == 200:
                    LOGGER.debug("get_node : " + str(response))
                    return response
                else:
                    LOGGER.error("Error on get_node. status %s, response %s", resp.status, str(response))
                    raise ValueError("bad credentials")

    async def get_device(self, id):
        """Get details on a device."""
        await self.check_connected()
        async with _session() as session, session.request(
            method="GET",
            url=f"{ENKI_URL}/api-enki-referentiel-agg-prod/v1/devices/{id}?version=2.15.0",
            headers={"Authorization": f"{self._token_type} {self._access_token}",
                    "X-Gateway-APIKey": ENKI_REFERENTIEL_API_KEY},
            proxy=proxy,) as resp:

                response = await resp.json()
                if resp.status == 200:
                    LOGGER.debug("get_device : " + str(response))
                    return response
                else:
                    LOGGER.error("Error on get_device. status %s, response %s", resp.status, str(response))
                    raise ValueError("bad credentials")

    async def get_light_details(self, home_id, node_id):
        """Get light state"""
        await self.check_connected()
        async with _session() as session, session.request(
             method="GET",
             url=f"{ENKI_URL}/api-enki-lighting-prod/v1/lighting/{node_id}/check-light-state",
             headers={"Authorization": f"{self._token_type} {self._access_token}",
                      "homeId": home_id,
                      "X-Gateway-APIKey": ENKI_LIGHTS_API_KEY},
             proxy=proxy,) as resp:

                response = await resp.json()
                if resp.status == 200:
                    LOGGER.debug("get_light_details : " + str(response))
                    return response
                else:
                    LOGGER.error("Error on get_light_details. status %s, response %s", resp.status, str(response))
                    raise ValueError("bad credentials")

    async def change_light_state(self, home_id, node_id, parameter, value):
        await self.check_connected()

        data = (await self.get_light_details(home_id, node_id))["lastReportedValue"]
        data[parameter] = value

        async with _session() as session, session.request(
            method="POST",
            url=f"{ENKI_URL}/api-enki-lighting-prod/v1/lighting/{node_id}/change-light-state",
            headers={"Authorization": f"{self._token_type} {self._access_token}",
                    "homeId": home_id,
                    "X-Gateway-APIKey": ENKI_LIGHTS_API_KEY},
            proxy=proxy,
            json=data) as resp:

                if resp.status != 202:
                    response = await resp.json()
                    LOGGER.debug(resp.status)
                    LOGGER.error("Error on change_light_state. status %s, response %s", resp.status, str(response))
                    raise ValueError("bad credentials")

# *******************************************************

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get devices on api."""
        homes = await self.get_homes()
        devices = []
        for home in homes:
            devices.extend(await self.get_items_in_section_for_home(home))
        return devices

class APIAuthError(Exception):
    """Exception class for auth error."""

class APIConnectionError(Exception):
    """Exception class for connection error."""
