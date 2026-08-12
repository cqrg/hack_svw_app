#!/usr/bin/env python3
"""svw_client.py - 上汽大众超级App（ID.3）车控客户端

状态：一键控车（TSP 场景）SDK 协议已完整（baseUrl/密钥/签名/接口，来自脱壳反编译）；
      VWSDK 核心车控（锁车/空调/充电）接口待登录抓包补全（见 TODO）。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

_LOGGER = logging.getLogger(__name__)

# ---- 一键控车（TSP 场景）SDK ----
ONEHIT_BASE = "https://vw-onehitmobilesdk-af.mos.csvw.com/"
ONEHIT_APP_KEY = "f23b6f2dc6cc47a5bfe3ae102f488826"
ONEHIT_APP_SECRET = "5da28ae18d1e43f8a34d8f90d3c01606"
ONEHIT_SIGN_KEY = "973D5F1269759ECF2312D2F0E9C04671"
ONEHIT_SECRET_KEY = "7D5F81A491CC90C2CB8148A1346557A9"
ONEHIT_ACCOUNT_NO = "acc2025062400270001"


class SvwError(Exception):
    """上汽大众 API 错误。"""


@dataclass
class SvwAuth:
    """认证信息（长/短时效 JWT + accessToken）。"""

    long_jwt: str = ""
    short_jwt: str = ""
    access_token: str = ""
    expires_at: float = 0.0


@dataclass
class SvwClient:
    username: str = ""
    password: str = ""
    session: requests.Session = field(default_factory=requests.Session)
    auth: SvwAuth = field(default_factory=SvwAuth)
    device_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    vin: str = ""
    user_id: str = ""

    # ---- 基础 ----
    def _onehit_sign(self, headers: dict) -> str:
        """一键控车 SDK 签名：SHA256(排序拼接参数 + SIGN_KEY)，大写 hex。"""
        content = "&".join(
            f"{k}={headers[k]}"
            for k in sorted(headers)
            if k not in ("signType", "sign") and headers[k] not in (None, "")
        )
        return hashlib.sha256((content + ONEHIT_SIGN_KEY).encode()).hexdigest().upper()

    def _onehit_headers(self, body: Optional[dict] = None) -> dict:
        ts = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex
        base = {
            "version": "5.0.5",
            "deviceId": self.device_id,
            "timestamp": ts,
            "accountNo": ONEHIT_ACCOUNT_NO,
            "nonce": nonce,
            "requestId": ts,
            "signType": "sha256Hex",
            "x-device-from": "IMAPP",
            "deviceFrom": "svwab",
            "x-sdk-version": "2.0.0",
            "Authorization": f"Bearer {self.auth.access_token}",
            "userId": self.user_id,
            "vin": self.vin,
            "appKey": ONEHIT_APP_KEY,
            "clientType": "APP",
            "business": "ZMAKER",
            "loginVehicleType": "SOA",
            "loginManufacturer": "RACAR",
            "manufacturer": "RACAR",
            "clientName": "SOA",
        }
        if body is not None:
            base["x-body"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        base["sign"] = self._onehit_sign(base)
        return base

    def _onehit_request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        url = path if path.startswith("http") else ONEHIT_BASE + path.lstrip("/")
        headers = self._onehit_headers(body)
        headers["Content-Type"] = "application/json;charset=UTF-8"
        r = self.session.request(method, url, headers=headers, json=body, timeout=30)
        try:
            data = r.json()
        except ValueError:
            data = {"raw": r.text}
        _LOGGER.debug("%s %s -> %s", method, url, r.status_code)
        if r.status_code >= 400:
            raise SvwError(f"HTTP {r.status_code}: {data}")
        if isinstance(data, dict) and data.get("code") not in (None, 0, 200, "0", "200"):
            raise SvwError(f"API code={data.get('code')} msg={data.get('message')}")
        return data

    # ---- 登录/刷新（TODO: 脱壳后补全） ----
    def login(self) -> None:
        """账号密码登录，获取原始长效 JWT。"""
        raise NotImplementedError(
            "登录接口在加固 dex 中，请先脱壳（tools/frida-dump/README.md）"
        )

    def refresh_token(self) -> None:
        """PUT 刷新：短时效 JWT + accessToken。"""
        raise NotImplementedError("待脱壳后补全")

    # ---- 车控业务（TODO: 脱壳后补全路径与参数） ----
    def get_vehicles(self) -> list[dict]:
        """车辆列表。"""
        raise NotImplementedError("待脱壳后补全")

    def get_vehicle_status(self, vin: str) -> dict:
        """车辆状态（一键控车 SDK 已确认接口）。"""
        self.vin = vin
        return self._onehit_request("POST", "/svwcar/ab/vel/vehicle/getValStatus/v1", {"vin": vin})

    def get_ac_status(self, vin: str) -> dict:
        """空调状态（已确认接口）。"""
        self.vin = vin
        return self._onehit_request("POST", "/svwcar/ab/vel/vehicle/svw/getACStatus/v1", {"vin": vin})

    def remote_command(self, vin: str, command: str, **params) -> dict:
        """远程控制，command 如 lock/unlock/climate_on/charge_*（VWSDK 路径待抓包）。"""
        raise NotImplementedError("待脱壳后补全")


def _demo() -> None:
    """演示：打印一键控车签名示例（无需网络）。"""
    c = SvwClient()
    c.auth.access_token = "<accessToken>"
    c.user_id = "<userId>"
    c.vin = "<VIN>"
    h = c._onehit_headers({"vin": c.vin})
    print("onehit headers:", json.dumps(h, ensure_ascii=False, indent=2))
    print("\nsign:", h["sign"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _demo()
