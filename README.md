# 上汽大众超级App（ID.3）逆向 → HA 集成

与 [bmw/](../bmw/) 同模式的项目。目标：把 `com.svw.sc.mos`（上汽大众超级App，
ID.3 车控）的私有 API 逆向出来，供 Home Assistant 使用。

> 最新进度（2026-08-14）：**登录验证成功**（账号 bf30c486a87c47f8 + 短信验证码），
> 实测车况/车控走 **MOS API（api.mos.csvw.com/mos/...）**，`svw_mos_client.py` 已打通
> 车况查询 + 空调控制。HA 集成待做。

## 当前状态（2026-08-12，已脱壳）

| 模块 | 状态 |
| --- | --- |
| App 识别 | ✅ v5.0.5，包名 `com.svw.sc.mos` |
| 加固识别 | ✅ **SecNeo（梆梆）** |
| **脱壳** | ✅ **MuMu 模拟器 + frida-dexdump，59 dex / 78MB，jadx 反编译 14827 类** |
| 主业务反编译 | ✅ com.svw.sc.mos.*（VehicleControlApi / ChargeApi / TokenInterceptor 等） |
| 一键控车 SDK | ✅ baseUrl / APP_KEY/SECRET / 接口 / **签名算法**（`svw_client.py` 已实现） |
| 数字钥匙 SDK | ✅ ingeek(nokeeu.com) + kdwl(askdwl.com) |
| VWSDK 车控核心 | ✅ **实测走 MOS API（api.mos.csvw.com/mos/...）**，无需 VWSDK；`svw_mos_client.py` 车况查询+空调控制已打通 |
| native 加密库 | ✅ JNI 接口/密钥结构/init 校验已逆向，unidbg 可调用（`tools/vw_crypto_oracle.py`） |
| 登录验证 | ✅ 密码登录 + 短信验证码（2026-08-14） |
| 车况/车控 API | ✅ 空调/充电/车门/位置查询 + 空调开/关控制全部实测 |
| HA 集成 | ⏳ 待做 |

**一句话：** 模拟器脱壳已成功，主 App 与一键控车 SDK 全部反编译到手；
只差 VWSDK 车控核心（锁车/空调/充电）——它需要登录账号后才加载，登录后抓包即可补全。

## 目录

```
svw/
├── REVERSE_NOTES.md            # 逆向全过程、坑、结论
├── API_REFERENCE.md            # 后端域名、网关、错误码
├── APP_PROTOCOL.md             # 加密库协议、密钥结构、认证流程
├── svw_client.py               # 客户端骨架（TODO 标注待补全处）
├── custom_components/
│   └── id3_tracker/            # HA 集成骨架
└── tools/
    ├── unidbg-runner/          # unidbg 调用真实 so（CallVwCryptoTool / DbgVwCrypto）
    ├── vw_crypto_oracle.py     # Python 封装：加解密 oracle
    ├── frida-dump/             # 真机脱壳工具包（最快解锁路径）
    └── kd_client.p12           # mTLS 网关客户端证书（密码待提取）
```

## 快速开始

```powershell
# 1. 验证 native 加密库可调用（自检）
python tools/vw_crypto_oracle.py

# 2. 验证一键控车签名（自检）
python svw_client.py

# 3. （已脱壳）需要重新脱壳时：MuMu 模拟器 + frida-dexdump
#    adb: D:\Program Files\Netease\MuMu\nx_device\15.0\shell\adb.exe
#    python -m frida_dexdump -U -p <pid>
```

## 已确认的关键事实

- 一键控车（TSP 场景）生产 API：`vw-onehitmobilesdk-af.mos.csvw.com`，
  APP_KEY/SECRET/SIGN_KEY 已提取，接口 `/svwcar/ab/...`，签名 = SHA256(排序参数+SIGN_KEY)。
- `libvwappwbox2025_crypto_tool.so` 的 JNI：`(data, keyHex, byte[])`，
  密钥带 4 字节头（魔数 `a7 26`），`key[0]^key[3]` 选变体，实际密钥
  `newkey[i]=key[i+4]^key[i%3]`，自定义白盒 cipher（非标准 AES）。
- 白盒密钥由服务端 `WhiteBoxKeyServiceImpl` 下发，必须在 dex 中提取。
- 车控认证链：MOS 账号 → MOS PAT（MosPatRefreshHelper）→ VWSDK(TSP) → 车控命令。

## 后续（登录后）

1. 在上汽大众超级App 模拟器里登录账号、绑定车辆。
2. mitmproxy 抓包（或 frida hook OkHttp）拿 VWSDK 车控接口 + MOS PAT 获取流程。
3. 补全 `svw_client.py` 的 `remote_command` / 登录 / 车辆列表。
4. 完成 `custom_components/id3_tracker/` 的 HA 集成。



## Home Assistant 集成（id3_tracker）

> 已完成（2026-08-14）：位置追踪 + 传感器（电量/续航/空调/车门）+ 空调开/关按钮。
> token 实测服务端不严格校验（JWT exp 过期仍 200，三个历史 X-COP 均有效），一次配置可长期使用；若过期重新抓取即可（见 REVERSE_NOTES）。

### 安装

```powershell
# 将 custom_components/id3_tracker/ 复制到 HA 的 custom_components/ 下
Copy-Item -Recurse custom_components\svw_tracker <ha_config>/custom_components/
```

### 配置（configuration.yaml）

**可直接粘贴（2026-08-14 实测有效）**：

```yaml
device_tracker:
  - platform: id3_tracker
    name: "ID.3"                              # 可选，默认 SVW ID.3
    user_id: "2166661271071268864"
    vin: "LSVFB6E93P2082137"
    auth_jwt: "Bearer eyJraWQiOiI4OTY0NTMwOTYyMDkwNzcxNzEzIiwidHlwIjoiSldUIiwiYWxnIjoiRVMyNTYifQ.eyJzc29pZCI6IjEwMmM0OGZjLTRiYzUtNDVkNS1iNTk4LWU1YmZlNmRmMjllNCIsInNjcCI6WyJvcGVuaWQiXSwic3ViIjoiMjE2NjY2MTI3MTA3MTI2ODg2NCIsInZlciI6IjEuMCIsImlzcyI6Im1vcy5jc3Z3LmNvbSIsImNjaCI6ImFwcCIsInR5cCI6IkFUIiwiaWR0LWlkIjoiYzYwN2NjNGQtMGIwZS00ZGZhLWJjNDQtMjU1ZWUwYWE0ZmQyIiwiaG9zIjoiVlciLCJyb2wiOiJQUklNQVJZX1VTRVIiLCJzdHlwIjoiVDMiLCJhdWQiOiJ3d3cuc3Z3LmNvbS5jbiIsInZpbiI6IkxTVkZCNkU5M1AyMDgyMTM3IiwidG50IjoidnciLCJleHAiOjE3ODY2OTczOTcsImlhdCI6MTc4NjY5MDE5NywicnQtaWQiOiI3YmI0YmEzNi05MmYxLTQ1NjQtYmYwZC1kMGYzNzhhZTc1NTciLCJsY3MiOltdLCJqdGkiOiIyOGUyNzljNS1jNzgzLTQ1NzEtYjE2Yy00NmU5OTk5OTIzNTYifQ.JJ_ieEm3bKB50e7YOQlpu48E-mZ9YEuu1GpYrxjH8p6f2qcTmy5KTZE8QDgBf-MWzmqpNoJvQN-JEuUkMddOuA"
    cop_token: "mVgQ8toCS3IAF82dU_7SW7SDLQZBMy9e"
    device_id: "vwa0a1b298a1598603"
    did: "VW_APP_23117RK66C_51c26dffc16c41dcb22954f3de72ab7c_15_5.0.5"
```

> token 实测服务端不严格校验（JWT exp 过期仍 200、历史 X-COP 均有效），一次配置可长期使用；若将来失效，重新抓取（见 REVERSE_NOTES）。

### 实体

| 实体 | 类型 | 说明 |
| --- | --- | --- |
| `device_tracker.id3_id3_location` | 位置 | GPS 经纬度 |
| `sensor.id3_id3_电量` | 电量 % | 含续航/充电状态 |
| `sensor.id3_id3_空调` | 状态 | on/off + 剩余时间 |
| `sensor.id3_id3_车门` | 状态 | safe + 车门/车窗明细 |
| `button.id3_id3_空调开` / `空调关` | 按钮 | 远程空调开/关 |




