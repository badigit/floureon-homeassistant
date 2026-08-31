"""Synchronous client for Floureon/Hysen thermostats.

python-broadlink uses blocking UDP sockets. This module deliberately does not
know about Home Assistant; the coordinator runs every call in its executor.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import broadlink

from .const import DEFAULT_NAME, SUPPORTED_DEVICE_TYPE


@dataclass(frozen=True, slots=True)
class FloureonStatus:
    """A typed thermostat snapshot."""

    power: bool
    active: bool
    temp_manual: bool
    heating_cooling: bool
    room_temp: float | None
    external_temp: float | None
    target_temp: float | None
    auto_mode: int | None
    loop_mode: int | None
    sensor: int | None
    hysteresis: float | None
    max_temp: float | None
    min_temp: float | None
    room_temp_adjustment: float | None
    remote_lock: bool | None
    anti_freeze: bool | None
    power_on_memory: bool | None

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> FloureonStatus:
        """Normalise python-broadlink's status dictionary."""
        return cls(
            power=bool(raw.get("power")),
            active=bool(raw.get("active")),
            temp_manual=bool(raw.get("temp_manual")),
            heating_cooling=bool(raw.get("heating_cooling")),
            room_temp=_number(raw.get("room_temp")),
            external_temp=_number(raw.get("external_temp")),
            target_temp=_number(raw.get("thermostat_temp")),
            auto_mode=_integer(raw.get("auto_mode")),
            loop_mode=_integer(raw.get("loop_mode")),
            sensor=_integer(raw.get("sensor")),
            hysteresis=_number(raw.get("dif")),
            max_temp=_number(raw.get("svh")),
            min_temp=_number(raw.get("svl")),
            room_temp_adjustment=_number(raw.get("room_temp_adj")),
            remote_lock=_optional_bool(raw.get("remote_lock")),
            anti_freeze=_optional_bool(raw.get("fre")),
            power_on_memory=_optional_bool(raw.get("poweron")),
        )


def _number(value: Any) -> float | None:
    """Convert protocol data to a finite float."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    """Convert protocol data to an integer."""
    number = _number(value)
    return None if number is None else int(number)


def _optional_bool(value: Any) -> bool | None:
    """Keep missing flags distinct from false flags."""
    return None if value is None else bool(value)


class FloureonApiClient:
    """Own one authenticated python-broadlink device instance."""

    def __init__(self, device: Any) -> None:
        self.device = device

    @classmethod
    def discover(cls, host: str, timeout: int) -> FloureonApiClient:
        """Discover a thermostat by address."""
        device = broadlink.hello(host, timeout=timeout)
        if device.devtype != SUPPORTED_DEVICE_TYPE:
            raise UnsupportedDeviceError(
                f"Unsupported Broadlink device type: {device.devtype:#06x}"
            )
        device.timeout = timeout
        return cls(device)

    @classmethod
    def from_config(
        cls, *, host: str, mac: str, dev_type: int, timeout: int
    ) -> FloureonApiClient:
        """Recreate a discovered thermostat without broadcasting."""
        device = broadlink.gendevice(
            dev_type,
            (host, 80),
            bytes.fromhex(mac),
            name=DEFAULT_NAME,
        )
        device.timeout = timeout
        return cls(device)

    @property
    def host(self) -> str:
        """Return the current device address."""
        return self.device.host[0]

    @property
    def mac(self) -> str:
        """Return a stable hexadecimal MAC address."""
        return self.device.mac.hex()

    @property
    def dev_type(self) -> int:
        """Return Broadlink's numeric device type."""
        return self.device.devtype

    @property
    def model(self) -> str:
        """Return the reported model."""
        return self.device.model

    @property
    def manufacturer(self) -> str:
        """Return the reported manufacturer."""
        return self.device.manufacturer

    def authenticate(self) -> None:
        """Authenticate once and retain the negotiated key."""
        if self.device.auth() is False:
            raise FloureonAuthenticationError("Device rejected authentication")

    def read_status(self) -> FloureonStatus:
        """Read one full thermostat snapshot."""
        return FloureonStatus.from_api(self.device.get_full_status())

    def set_time(self, now: datetime | None = None) -> None:
        """Set the thermostat clock to local time."""
        value = now or datetime.now(UTC).astimezone()
        self.device.set_time(
            value.hour, value.minute, value.second, value.weekday() + 1
        )

    def set_manual_temperature(
        self, temperature: float, schedule: int, sensor: int
    ) -> None:
        """Atomically switch to manual control and set its target."""
        self.device.set_mode(0, schedule, sensor)
        self.device.set_temp(temperature)

    def set_hvac_mode(
        self, *, power: int, mode: int, schedule: int, sensor: int, cooling: bool
    ) -> None:
        """Set power and the controller mode as one serial operation."""
        self.device.set_power(power, heating_cooling=int(cooling))
        if power:
            self.device.set_mode(mode, schedule, sensor)

    def set_switch_state(
        self,
        *,
        power: int,
        temperature: float | None,
        schedule: int,
        sensor: int,
    ) -> None:
        """Apply the legacy switch semantics as one serial operation."""
        self.device.set_power(power)
        if temperature is not None:
            self.device.set_mode(0, schedule, sensor)
            self.device.set_temp(temperature)

    def set_preset_temperature(
        self,
        temperature: float,
        schedule: int,
        sensor: int,
        *,
        cooling: bool = False,
    ) -> None:
        """Power on and apply a manual preset as one operation."""
        self.device.set_power(1, heating_cooling=int(cooling))
        self.device.set_mode(0, schedule, sensor)
        self.device.set_temp(temperature)


class UnsupportedDeviceError(Exception):
    """The discovered Broadlink device is not a Hysen thermostat."""


class FloureonAuthenticationError(Exception):
    """The thermostat explicitly rejected authentication."""
