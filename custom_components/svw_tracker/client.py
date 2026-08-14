"""SVW MOS API client for Home Assistant."""
import time, uuid
import requests

BASE = "https://api.mos.csvw.com"


class SVWError(Exception):
    pass


class SVWMosClient:
    def __init__(self, user_id, vin, auth_jwt, cop_token, device_id, did):
        self.user_id = user_id
        self.vin = vin
        self.auth_jwt = auth_jwt
        self.cop_token = cop_token
        self.device_id = device_id
        self.did = did

    def _headers(self, content_type=True):
        ts = int(time.time() * 1000)
        nonce = str(uuid.uuid4())
        h = {
            "Authorization": self.auth_jwt,
            "X-COP-accessToken": self.cop_token,
            "X-Brand": "VW",
            "OS": "Android",
            "Did": self.did,
            "deviceId": self.device_id,
            "Timestamp": str(ts),
            "Nonce": nonce,
            "TraceId": f"{uuid.uuid4()}_{self.user_id}_{self.did}_{ts}",
            "Accept-Language": "zh",
            "Accept": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/4.12.0",
        }
        if content_type:
            h["Content-Type"] = "application/json; charset=UTF-8"
        return h

    def _get(self, path):
        r = requests.get(BASE + path, headers=self._headers(False), timeout=20)
        return r.json()

    def _post(self, path, body):
        r = requests.post(BASE + path, headers=self._headers(True), json=body, timeout=20)
        return r.json()

    def _check(self, data):
        if data.get("code") != "000000":
            raise SVWError(f"API error {data.get('code')}: {data.get('description')}")
        return data.get("data")

    # ---- 车况查询 ----
    def climatisation_status(self):
        return self._check(self._get(f"/mos/rcs/api/v2/users/{self.user_id}/vehicles/{self.vin}/climatisation/status"))

    def charging_status(self):
        return self._check(self._get(f"/mos/rcs/api/v2/users/{self.user_id}/vehicles/{self.vin}/charging/status"))

    def access_lights_status(self):
        return self._check(self._get(f"/mos/rcs/api/v1/users/{self.user_id}/vehicles/{self.vin}/access-lights/status"))

    def vehicle_location(self):
        return self._check(self._get(f"/mos/vdis/api/v1/users/{self.user_id}/vehicles/{self.vin}/location/latest"))

    def refresh_all(self):
        """拉全量车况，供 HA 轮询。失败不抛，返回部分数据。"""
        out = {}
        for name, fn in (
            ("climatisation", self.climatisation_status),
            ("charging", self.charging_status),
            ("access_lights", self.access_lights_status),
            ("location", self.vehicle_location),
        ):
            try:
                out[name] = fn()
            except Exception as exc:  # noqa: BLE001
                out[name] = {"error": str(exc)}
        return out

    # ---- 空调控制 ----
    def climatisation_start(self, target_temp=15.5, window_heating=False):
        body = {
            "climatisationWithoutExternalPower": True,
            "targetTemperatureC": str(target_temp),
            "windowHeatingEnabled": window_heating,
            "zoneFrontLeftEnabled": False, "zoneFrontRightEnabled": False,
            "zoneRearLeftEnabled": False, "zoneRearRightEnabled": False,
        }
        return self._check(self._post(f"/mos/rcs/api/v1/users/{self.user_id}/vehicles/{self.vin}/climatisation/actions/start", body))

    def climatisation_stop(self):
        return self._check(self._post(f"/mos/rcs/api/v1/users/{self.user_id}/vehicles/{self.vin}/climatisation/actions/stop", {}))
