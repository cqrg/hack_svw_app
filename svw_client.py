#!/usr/bin/env python3
"""svw_client.py - 上汽大众超级App（ID.3）车控客户端骨架

状态：**骨架**。真实接口路径、请求格式、白盒密钥、登录/刷新流程在 SecNeo 加固的 dex 中，
需先完成 Frida 脱壳（见 tools/frida-dump/README.md）后按 TODO 补全。

已确认可用的部分：
  - 后端网关域名（proxy-cccdk-vwaf-prod.mos.csvw.com，需 x-app-id）
  - native 加密库可通过 unidbg 调用（tools/vw_crypto_oracle.py）
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

_LOGGER = logging.getLogger(__name__)

# ---- 已确认的后端 ----
GATEWAY = "https://proxy-cccdk-vwaf-prod.mos.csvw.com"
# TODO(脱壳后): 从 dex 提取正确 appId
APP_ID = "<TODO: x-app-id from dex>"


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

    # ---- 基础 ----
    def _headers(self, extra: Optional[dict] = None) -> dict:
        h = {
            "x-app-id": APP_ID,
            "User-Agent": "okhttp/4.9.0",
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
        }
        if self.auth.short_jwt:
            h["Authorization"] = f"Bearer {self.auth.short_jwt}"
        if self.auth.access_token:
            # TODO(脱壳后): 确认 accessToken 的实际头名
            h["accessToken"] = self.auth.access_token
        if extra:
            h.update(extra)
        return h

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = path if path.startswith("http") else f"{GATEWAY}{path}"
        r = self.session.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        try:
            data = r.json()
        except ValueError:
            data = {"raw": r.text}
        _LOGGER.debug("%s %s -> %s", method, url, r.status_code)
        if r.status_code >= 400:
            raise SvwError(f"HTTP {r.status_code}: {data}")
        # TODO(脱壳后): 按真实响应结构处理 code/message
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
        """车辆状态（电量、里程、门窗、空调等）。"""
        raise NotImplementedError("待脱壳后补全")

    def remote_command(self, vin: str, command: str, **params) -> dict:
        """远程控制，command 如 lock/unlock/climate_on/charge_*。"""
        raise NotImplementedError("待脱壳后补全")


def _demo() -> None:
    """演示：验证网关可达性（无需登录）。"""
    c = SvwClient()
    try:
        r = c._request("GET", "/api/")
        print("gateway response:", r)
    except SvwError as e:
        print("gateway response:", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _demo()
