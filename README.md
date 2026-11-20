# Hysen / Floureon Wi-Fi Thermostats for Home Assistant

**English** | [Русский](README.ru.md)

A local Home Assistant integration for **Hysen HY02/HY03 Wi-Fi thermostats** using the Broadlink UDP protocol. Thermostats based on this platform are sold under several brands, including **Floureon, Beok (BeOK), Beca / Beca Energy, Decdeal**, and others. Communication stays on your local network; no cloud account is required.

## Compatibility

**The protocol matters, not the brand or appearance.** This integration accepts thermostats reporting **Broadlink device type `0x4EAD`**. A similar-looking device or one sold under a listed brand is not necessarily compatible; other Wi-Fi, Zigbee, or Tuya variants may use different protocols.

Some **Computherm** models (such as E400RF) have been described by other projects as Hysen-based, but **they have not been verified with this integration**. If you test another model, please [open an issue](https://github.com/badigit/floureon-homeassistant/issues) with its exact model and Broadlink device type.

## Features

- Configuration through the Home Assistant UI and a unique ID based on the device MAC address.
- A `climate` entity with automatic, manual heating/cooling (where supported), and off modes.
- Current and target temperatures, plus heating/cooling activity.
- An `away` preset with a separately remembered target temperature.
- Internal or external temperature sensor, weekly schedule layout, and temperature step options.
- Optional `switch` entity for existing setups using Generic Thermostat.
- Shared `DataUpdateCoordinator`, proper unavailable state handling, and diagnostics.
- Automatic import of legacy YAML configuration.

UDP operations use native async I/O. Commands and polling are serialized per device; the transport reconnects automatically after network failures.

## Requirements

- Home Assistant **2026.7.0** or newer.
- A fixed IP address for the thermostat (a DHCP reservation is recommended).
- A compatible thermostat with Broadlink device type **`0x4EAD`**.

## Installation

### HACS

1. Open HACS and select **Custom repositories**.
2. Add `https://github.com/badigit/floureon-homeassistant` as an **Integration**.
3. Install **Hysen Thermostat (Broadlink)** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and find **Hysen Thermostat (Broadlink)**.

### Manual installation

Copy `custom_components/floureon` to the corresponding directory in your Home Assistant configuration folder, then restart Home Assistant Core.

## Configuration

When adding a device, enter its address, UDP timeout, and entity type. The recommended entity type is `climate`. The following options are available:

| Option | Default | Range / meaning |
| --- | --- | --- |
| Polling interval | 30 s | 10–3600 s |
| External sensor | Enabled | External or internal temperature sensor |
| Schedule layout | 0 | `0`: 5+2; `1`: 6+1; `2`: 7 days |
| Temperature step | 0.5 °C | 0.5 or 1.0 °C |
| Cooling | Disabled | Enables `heat_cool` for a suitable controller |

The optional switch mode also lets you choose what happens when switching on or off: physical power off, minimum/maximum temperature, or a specific temperature.

## Migrating from the legacy integration

Legacy `climate: - platform: floureon` and `switch: - platform: floureon` YAML entries are imported into config entries on first startup. Once the device appears successfully, you can remove the old YAML configuration.

The existing name, sensor settings, schedule, temperature precision, and switch behavior are preserved. An old precision of 0.1 °C is converted to 0.5 °C because the Hysen target-temperature register only supports half-degree increments.

## Development

```bash
uv sync --group dev
uv run pytest
```

Home Assistant tests run on Linux because Home Assistant Core imports the POSIX-only `fcntl` module, which is unavailable on Windows. CI also runs hassfest and HACS validation.

## Acknowledgments

The thermostat protocol is implemented by [`broadlink-async`](https://github.com/mjg59/broadlink-async). This project is an independent new integration and does not continue the Git history of the former `hass-floureon` project.

## License

MIT. This project is not affiliated with any of the device manufacturers mentioned above.

## Existing installations and integration ID

The displayed integration name is **Hysen Thermostat (Broadlink)**, but the Home Assistant domain and installation folder remain `floureon`. Existing config entries and entity IDs are preserved; no reinstallation is required. The repository URL is unchanged.
