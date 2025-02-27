"""DataUpdateCoordinator for the YouTube integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from googleapiclient.discovery import Resource
from googleapiclient.http import HttpRequest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import AsyncConfigEntryAuth
from .const import (
    ATTR_DESCRIPTION,
    ATTR_LATEST_VIDEO,
    ATTR_PUBLISHED_AT,
    ATTR_SUBSCRIBER_COUNT,
    ATTR_THUMBNAIL,
    ATTR_TITLE,
    ATTR_VIDEO_ID,
    CONF_CHANNELS,
    DOMAIN,
    LOGGER,
)


def get_upload_playlist_id(channel_id: str) -> str:
    """Return the playlist id with the uploads of the channel.

    Replacing the UC in the channel id (UCxxxxxxxxxxxx) with UU is the way to do it without extra request (UUxxxxxxxxxxxx).
    """
    return channel_id.replace("UC", "UU", 1)


class YouTubeDataUpdateCoordinator(DataUpdateCoordinator):
    """A YouTube Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, auth: AsyncConfigEntryAuth) -> None:
        """Initialize the YouTube data coordinator."""
        self._auth = auth
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        data = {}
        service = await self._auth.get_resource()
        channels = self.config_entry.options[CONF_CHANNELS]
        channel_request: HttpRequest = service.channels().list(
            part="snippet,statistics", id=",".join(channels), maxResults=50
        )
        response: dict = await self.hass.async_add_executor_job(channel_request.execute)

        async def _compile_data(channel: dict[str, Any]) -> None:
            data[channel["id"]] = {
                ATTR_ID: channel["id"],
                ATTR_TITLE: channel["snippet"]["title"],
                ATTR_ICON: channel["snippet"]["thumbnails"]["high"]["url"],
                ATTR_LATEST_VIDEO: await self._get_latest_video(service, channel["id"]),
                ATTR_SUBSCRIBER_COUNT: int(channel["statistics"]["subscriberCount"]),
            }

        await asyncio.gather(*[_compile_data(channel) for channel in response["items"]])
        return data

    async def _get_latest_video(
        self, service: Resource, channel_id: str
    ) -> dict[str, Any]:
        playlist_id = get_upload_playlist_id(channel_id)
        job: HttpRequest = service.playlistItems().list(
            part="snippet,contentDetails", playlistId=playlist_id, maxResults=1
        )
        response: dict = await self.hass.async_add_executor_job(job.execute)
        video = response["items"][0]
        return {
            ATTR_PUBLISHED_AT: video["snippet"]["publishedAt"],
            ATTR_TITLE: video["snippet"]["title"],
            ATTR_DESCRIPTION: video["snippet"]["description"],
            ATTR_THUMBNAIL: video["snippet"]["thumbnails"]["standard"]["url"],
            ATTR_VIDEO_ID: video["contentDetails"]["videoId"],
        }
