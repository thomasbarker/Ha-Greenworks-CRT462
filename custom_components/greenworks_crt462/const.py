"""Constants for the Greenworks CRT4262 integration."""

DOMAIN = "greenworks_crt462"

# Xlink/Gelibo IoT API (extracted from com.greenworks.tools v4.4.0 APK)
CORP_ID = "100fa2b00b622800"
XAPI_BASE = "https://xapi.globetools.systems"
GUC_BASE = "https://guc.globetools.systems:446"
IDDS_BASE = "https://idds.globetools.systems"

# GUC OAuth2 shared credentials (from GucLogin.java in the decompiled APK)
GUC_CLIENT_ID = "GreenGuide"
GUC_CLIENT_SECRET = "351fc703-85f8-4fda-815a-6c2b1699b05a"
GUC_SCOPE = (
    "GimsSignalR IotDDSApi DeviceDbApi LicenseServiceApi "
    "PnmsCacheApi GfuApi openid offline_access profile GIotProductServiceApi"
)

# Product identity for CRT4262 ZTR mower (from APPconfig.java)
ZTR_PRODUCT_ID = "163e82bf913a1f41163e82bf913a0401"
MOWER_MODEL = "CRT4262"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60  # minutes
