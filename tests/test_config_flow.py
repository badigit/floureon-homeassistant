"""Tests for setup and migration flows."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from broadlink.exceptions import NetworkTimeoutError
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.floureon.api import (
    FloureonAuthenticationError,
    UnsupportedDeviceError,
)
from custom_components.floureon.const import (
    CONF_ENTITY_TYPE,
    CONF_PRECISION,
    CONF_USE_EXTERNAL_TEMP,
    DOMAIN,
    ENTITY_TYPE_CLIMATE,
    ENTITY_TYPE_SWITCH,
)

from .conftest import HOST, MAC


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """A reachable thermostat creates a stable config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_TIMEOUT: 3, CONF_ENTITY_TYPE: ENTITY_TYPE_CLIMATE},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MAC
    assert result["data"][CONF_HOST] == HOST
    assert result["options"][CONF_ENTITY_TYPE] == ENTITY_TYPE_CLIMATE


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (NetworkTimeoutError(-4000, "timeout", "no response"), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_user_flow_errors_keep_form_open(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_setup_entry: MagicMock,
    side_effect: Exception,
    expected: str,
) -> None:
    """Connection failures are classified and retryable."""
    mock_discovery.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_TIMEOUT: 3, CONF_ENTITY_TYPE: ENTITY_TYPE_CLIMATE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_duplicate_is_aborted(
    hass: HomeAssistant,
    add_entry,
    mock_discovery: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """The same MAC cannot be configured twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_TIMEOUT: 3, CONF_ENTITY_TYPE: ENTITY_TYPE_CLIMATE},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_yaml_import_preserves_options(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Legacy climate YAML becomes an equivalent config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_HOST: HOST,
            CONF_NAME: "Living room",
            CONF_ENTITY_TYPE: ENTITY_TYPE_CLIMATE,
            CONF_USE_EXTERNAL_TEMP: False,
            CONF_PRECISION: 0.1,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["options"][CONF_USE_EXTERNAL_TEMP] is False
    assert result["options"][CONF_PRECISION] == 0.5


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (UnsupportedDeviceError("plug"), "not_supported"),
        (FloureonAuthenticationError("rejected"), "invalid_auth"),
    ],
)
async def test_specific_discovery_errors(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_setup_entry: MagicMock,
    side_effect: Exception,
    expected: str,
) -> None:
    """Unsupported hardware and auth failures get actionable messages."""
    mock_discovery.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_TIMEOUT: 3, CONF_ENTITY_TYPE: ENTITY_TYPE_CLIMATE},
    )
    assert result["errors"] == {"base": expected}


async def test_failed_yaml_import_aborts(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """A powered-off YAML device retries on a later restart without a bad entry."""
    mock_discovery.side_effect = OSError("offline")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_switch_flow_and_entity_type_transition(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_setup_entry: MagicMock,
    add_entry,
) -> None:
    """Switch-specific options appear both at setup and after a type change."""
    result = await hass.config_entries.options.async_init(add_entry.entry_id)
    values = {
        key.schema: key.default()
        for key in result["data_schema"].schema
        if callable(getattr(key, "default", None))
    }
    values[CONF_ENTITY_TYPE] = ENTITY_TYPE_SWITCH
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], values
    )
    assert result["type"] is FlowResultType.FORM
    assert "turn_off_mode" in {key.schema for key in result["data_schema"].schema}


async def test_user_switch_flow(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """A new switch entry receives switch-specific defaults."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_TIMEOUT: 3, CONF_ENTITY_TYPE: ENTITY_TYPE_SWITCH},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["turn_off_mode"] == "min_temp"


async def test_options_flow(add_entry, hass: HomeAssistant) -> None:
    """Runtime options are persisted through Home Assistant's dialog."""
    result = await hass.config_entries.options.async_init(add_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    values = {
        key.schema: key.default()
        for key in result["data_schema"].schema
        if callable(getattr(key, "default", None))
    }
    values["scan_interval"] = 60
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], values
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["scan_interval"] == 60
