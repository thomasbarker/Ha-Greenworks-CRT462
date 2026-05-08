# Greenworks CRT4262 – Home Assistant Integration

A HACS-compatible Home Assistant integration for the **Greenworks CRT4262 ride-on mower**, using the native Xlink/Gelibo IoT cloud API that powers the official Greenworks Connect app.

---

## Features

### Status & connectivity

| Entity | Type | Notes |
|---|---|---|
| Online | Binary Sensor | Connectivity device class |
| Active | Binary Sensor | Running device class |
| Last Updated | Sensor | Timestamp — when data was last successfully refreshed from the cloud |
| Last Seen | Sensor | Timestamp — last time mower connected to cloud |
| Last Disconnected | Sensor | Timestamp |

### GPS

| Entity | Type | Notes |
|---|---|---|
| Latitude | Sensor | Degrees; GPS timestamp in attributes |
| Longitude | Sensor | Degrees |

### Battery

| Entity | Type | Notes |
|---|---|---|
| Battery | Sensor | %, total charge level |
| Battery Slot 1 – 6 | Sensor | %, per-slot charge level (diagnostic) |

### Mowing statistics

| Entity | Type | Notes |
|---|---|---|
| Total Working Time | Sensor | Minutes, total lifetime |
| Total Working Area | Sensor | m², total lifetime |
| Last Session Duration | Sensor | Minutes; session start/end timestamps in attributes |
| Last Session Area | Sensor | m² |
| Mowing Sessions | Sensor | Count; last 5 sessions (start, end, id) in attributes |
| Remaining Cutting Area | Sensor | m², estimated remaining on current charge |
| Remaining Cutting Time | Sensor | Minutes, estimated remaining on current charge |

### Settings

| Entity | Type | Notes |
|---|---|---|
| Cut Height | Sensor | mm |

### Diagnostics *(hidden by default)*

| Entity | Type | Notes |
|---|---|---|
| Drive Motor A / B | Sensor | RPM (non-zero when mowing) |
| Left / Mid / Right Blade RPM | Sensor | RPM (non-zero when mowing) |
| Firmware Version | Sensor | |
| MCU Version | Sensor | |
| Connection Count | Sensor | Total lifetime cloud connections |
| Status Code (DP 92) | Sensor | Raw datapoint; meaning unconfirmed |

---

## Prerequisites

- A **Greenworks Connect** account that has been successfully paired with your CRT4262 (verify in the app first).
- Home Assistant 2024.1 or later.
- [HACS](https://hacs.xyz/) installed.

---

## Installation

### Via HACS (Custom Repository)

1. In Home Assistant, open **HACS → Integrations**.
2. Click the three-dot menu → **Custom repositories**.
3. Enter the URL of this repository and select category **Integration**.
4. Click **Add**, then find *Greenworks CRT4262* and click **Download**.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/greenworks_crt462/` folder into your HA `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Greenworks CRT4262**.
3. Enter your Greenworks Connect email address and password.
4. Set the desired **update interval** in minutes (default: 60).

### Options

After setup, click **Configure** on the integration card to change the update interval without re-entering credentials.

---

## Notes

- Data is fetched from two Gelibo/Xlink cloud backends — `xapi.globetools.systems` (device status + GPS) and `idds.globetools.systems` (mowing statistics). Both require an active internet connection.
- If a scheduled refresh fails (network outage, temporary API error), entities remain available and continue showing their last known values. The **Last Updated** sensor shows when data was last successfully fetched, making it easy to spot stale readings.
- GPS and RPM datapoints are only non-zero when the mower is powered on and connected.
- The mower must be fully powered on (not just the battery) for Bluetooth pairing and cloud connectivity to function.
- This integration is not affiliated with or endorsed by Greenworks.
