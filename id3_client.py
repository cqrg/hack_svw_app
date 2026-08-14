# -*- coding: utf-8 -*-
"""VW ID.3 (上汽大众) MOS API client - from live capture 2026-08-14."""
import requests, time, uuid, json

BASE = "https://api.mos.csvw.com"

USER_ID = "2166661271071268864"
VIN = "LSVFB6E93P2082137"
DEVICE_ID = "vwa0a1b298a1598603"
DID = "VW_APP_23117RK66C_51c26dffc16c41dcb22954f3de72ab7c_15_5.0.5"
COP_ACCESS_TOKEN = "zBCZKXP0QcsAF82dU_7SW4JOs40_iQau"
AUTH_JWT = ("Bearer eyJraWQiOiI4OTY0NTMwOTYyMDkwNzcxNzEzIiwidHlwIjoiSldUIiwiYWxnIjoiRVMyNTYifQ."
            "eyJzc29pZCI6IjEwMmM0OGZjLTRiYzUtNDVkNS1iNTk4LWU1YmZlNmRmMjllNCIsInNjcCI6WyJvcGVuaWQiXSwic3ViIjoiMjE2NjY2MTI3MTA3MTI2ODg2NCIsInZlciI6IjEuMCIsImlzcyI6Im1vcy5jc3Z3LmNvbSIsImNjaCI6ImFwcCIsInR5cCI6IkFUIiwiaWR0LWlkIjoiYzYwN2NjNGQtMGIwZS00ZGZhLWJjNDQtMjU1ZWUwYWE0ZmQyIiwiaG9zIjoiVlciLCJyb2wiOiJQUklNQVJZX1VTRVIiLCJzdHlwIjoiVDMiLCJhdWQiOiJ3d3cuc3Z3LmNvbS5jbiIsInZpbiI6IkxTVkZCNkU5M1AyMDgyMTM3IiwidG50IjoidnciLCJleHAiOjE3ODY2OTczOTcsImlhdCI6MTc4NjY5MDE5NywicnQtaWQiOiI3YmI0YmEzNi05MmYxLTQ1NjQtYmYwZC1kMGYzNzhhZTc1NTciLCJsY3MiOltdLCJqdGkiOiIyOGUyNzljNS1jNzgzLTQ1NzEtYjE2Yy00NmU5OTk5OTIzNTYifQ."
            "JJ_ieEm3bKB50e7YOQlpu48E-mZ9YEuu1GpYrxjH8p6f2qcTmy5KTZE8QDgBf-MWzmqpNoJvQN-JEuUkMddOuA")


class ID3Client:
    def __init__(self, user_id=USER_ID, vin=VIN, auth_jwt=AUTH_JWT, cop_token=COP_ACCESS_TOKEN,
                 device_id=DEVICE_ID, did=DID):
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
    def climatisation_status(self):
        return self._get(f"/mos/rcs/api/v2/users/{self.user_id}/vehicles/{self.vin}/climatisation/status")

    def charging_status(self):
        return self._get(f"/mos/rcs/api/v2/users/{self.user_id}/vehicles/{self.vin}/charging/status")

    def access_lights_status(self):
        return self._get(f"/mos/rcs/api/v1/users/{self.user_id}/vehicles/{self.vin}/access-lights/status")

    def vehicle_location(self):
        return self._get(f"/mos/vdis/api/v1/users/{self.user_id}/vehicles/{self.vin}/location/latest")

    def user_info(self):
        return self._get(f"/mos/user/api/v5/customer/userInfo?userId={self.user_id}&vin={self.vin}")

    def climatisation_start(self, target_temp=15.5, window_heating=False):
        body = {
            "climatisationWithoutExternalPower": True,
            "targetTemperatureC": str(target_temp),
            "windowHeatingEnabled": window_heating,
            "zoneFrontLeftEnabled": False, "zoneFrontRightEnabled": False,
            "zoneRearLeftEnabled": False, "zoneRearRightEnabled": False,
        }
        return self._post(f"/mos/rcs/api/v1/users/{self.user_id}/vehicles/{self.vin}/climatisation/actions/start", body)

    def climatisation_stop(self):
        return self._post(f"/mos/rcs/api/v1/users/{self.user_id}/vehicles/{self.vin}/climatisation/actions/stop", {})

    def request_status(self, request_id):
        return self._get(f"/mos/rcs/api/v1/users/{self.user_id}/vehicles/{self.vin}/requests/{request_id}")


if __name__ == "__main__":
    import sys
    c = ID3Client()
    if len(sys.argv) > 1 and sys.argv[1] == "ac-start":
        r = c.climatisation_start()
        print("AC start:", json.dumps(r, ensure_ascii=False)[:300])
        rid = r.get("data", {}).get("requestId")
        if rid:
            time.sleep(3)
            print("status:", json.dumps(c.request_status(rid), ensure_ascii=False)[:300])
    elif len(sys.argv) > 1 and sys.argv[1] == "ac-stop":
        print("AC stop:", json.dumps(c.climatisation_stop(), ensure_ascii=False)[:300])
    else:
        for name, fn in [("climatisation", c.climatisation_status), ("charging", c.charging_status),
                         ("access_lights", c.access_lights_status), ("location", c.vehicle_location)]:
            try:
                d = fn().get("data", {})
                print(f"--- {name} ---")
                print(json.dumps(d, ensure_ascii=False)[:350])
            except Exception as e:
                print(f"{name} ERR: {e}")

