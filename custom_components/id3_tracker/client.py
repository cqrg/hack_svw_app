"""VW ID.3 MOS API client for Home Assistant."""
import time, uuid
import requests

BASE = "https://api.mos.csvw.com"


class ID3Error(Exception):
    pass


class ID3Client:
    def __init__(self, user_id, vin, auth_jwt, cop_token="", device_id="", did=""):
        """实测（2026-08-16）：车控只需 auth_jwt，did/device_id/cop_token 均可省略（空/伪造均 200）。"""
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
            "X-Brand": "VW",
            "OS": "Android",
            "Timestamp": str(ts),
            "Nonce": nonce,
            "TraceId": f"{uuid.uuid4()}_{self.user_id}_{self.did or 'DID'}_{ts}",
            "Accept-Language": "zh",
            "Accept": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/4.12.0",
        }
        if self.cop_token:
            h["X-COP-accessToken"] = self.cop_token
        if self.did:
            h["Did"] = self.did
        if self.device_id:
            h["deviceId"] = self.device_id
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
            raise ID3Error(f"API error {data.get('code')}: {data.get('description')}")
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



    # ---- 账号密码自动登录（2026-08-16 实测）----
    def login_with_password(self, username: str, password: str, did: str) -> dict:
        """pwdlogin -> idToken；再尝试 /app/token 兑换 accessToken。
        注意：/app/token 服务端对非 App 客户端返回 500025（实测），
        若失败请用 token 模式（access_token 配置）或 App 登录后填 accessToken。"""
        ts = int(time.time() * 1000)
        base = {
            "NOT_NEED_TOKEN": "NOT_NEED_TOKEN",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json; charset=UTF-8", "Accept-Language": "zh",
            "X-Brand": "VW", "OS": "Android", "Did": did, "deviceId": self.device_id,
            "Timestamp": str(ts), "Nonce": str(uuid.uuid4()),
            "TraceId": f"{uuid.uuid4()}_sc_{did}_{ts}", "User-Agent": "okhttp/4.12.0",
        }
        r = requests.post(
            BASE + "/mos/security/api/v1/app/actions/pwdlogin",
            json={"brand": "vw", "deviceId": did, "deviceType": "android",
                  "mobile": username, "picContent": "", "picTicket": "",
                  "pwd": password, "scope": "openid"},
            headers=base, timeout=20)
        data = r.json().get("data", {})
        idtoken = data.get("idToken")
        if not idtoken:
            return {"ok": False, "error": r.json().get("description")}
        # 尝试兑换 accessToken
        h = dict(base)
        h["Authorization"] = "Bearer"
        h["X-COP-accessToken"] = ""
        r2 = requests.post(
            BASE + "/mos/security/api/v1/app/token",
            json={"consentTypeList": "app_privacy,app_agreement", "idToken": idtoken},
            headers=h, timeout=20)
        j2 = r2.json()
        if j2.get("code") == "000000":
            d2 = j2["data"]
            self.auth_jwt = "Bearer " + d2["accessToken"]
            return {"ok": True, "accessToken": d2["accessToken"],
                    "refreshToken": d2.get("refreshToken"), "expireIn": d2.get("expireIn")}
        return {"ok": False, "error": f"/app/token {j2.get('code')} {j2.get('description')}（服务端限制，需 token 模式）",
                "idTokenAT": data.get("idTokenAT"), "idTokenRT": data.get("idTokenRT")}

