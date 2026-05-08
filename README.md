# Greenworks CRT4262 – Home Assistant Integration

A HACS-compatible Home Assistant integration for the **Greenworks CRT4262 ride-on mower**, using the native Xlink/Gelibo IoT cloud API that powers the official Greenworks Connect app.

---

## Features

| Entity | Type | Notes |
|---|---|---|
| Online | Binary Sensor | Connectivity device class |
| Active | Binary Sensor | Running device class |
| Last Seen | Sensor | Timestamp |
| Last Disconnected | Sensor | Timestamp |
| Latitude / Longitude | Sensor | Last known GPS fix |
| Total Working Time | Sensor | Minutes, total lifetime |
| Total Working Area | Sensor | m², total lifetime |
| Last Session Duration | Sensor | Minutes, with start/end as attributes |
| Last Session Area | Sensor | m² |
| Mowing Sessions | Sensor | Count, last 5 sessions in attributes |
| Cut Height | Sensor | mm |
| Drive Motor A / B | Sensor | RPM (live when mowing), diagnostic |
| Left / Mid / Right Blade RPM | Sensor | RPM (live when mowing), diagnostic |
| Firmware / MCU Version | Sensor | Diagnostic |
| Connection Count | Sensor | Diagnostic |

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
- GPS and RPM datapoints are only non-zero when the mower is powered on and connected.
- The mower must be fully powered on (not just the battery) for Bluetooth pairing and cloud connectivity to function.
- This integration is not affiliated with or endorsed by Greenworks.
