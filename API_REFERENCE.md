# 上汽大众超级App - API 参考

> 状态：**脱壳成功，主 App 全量反编译**。一键控车（TSP 场景）SDK 接口/签名已完整；
> 核心车控（VWSDK com.zone.tsp）需登录后抓包补全。

## 1. 后端域名（已确认）

### 静态资源

| 域名 | 用途 |
| --- | --- |
| `mos-public-prod.mos.csvw.com` | OSS 静态资源（"index for moscore-oss"），如隐私政策 `/prod/richText/richText/<id>.html` |

### API 网关（证书透明日志发现）

| 域名 | 行为 |
| --- | --- |
| `proxy-cccdk-vwaf-prod.mos.csvw.com` | **无 mTLS**。根路径 `{"code":104000,"message":"COMMON_SYS_EXCEPTION"}`；`/api/` 要求 `x-app-id` 头 |
| `proxy-mbb-live.mos.csvw.com` | 要求 mTLS 客户端证书（400 No required SSL certificate） |
| `proxy-mbb-audi.mos.csvw.com` / `proxy-mbb-skd.mos.csvw.com` | 同上（奥迪/斯柯达 MBB） |
| `audi-proxy-bff-prod.mos.csvw.com` | 要求 mTLS（Audi BFF） |
| `hu-api-platform.mos.csvw.com` | 要求 mTLS（车机） |
| `mos-core-live-signature.mos.csvw.com` | 签名服务（当前 DNS 不解析） |

### App 实际使用的 API（脱壳后确认）

| 域名 | 用途 | 来源 |
| --- | --- | --- |
| `https://vw-onehitmobilesdk-af.mos.csvw.com/` | **一键控车（TSP 场景）生产 API** | `HttpProxy.configureCloudEnvironment` |
| `https://acp-es33.z-onesoft.com/` / `https://acp.z-onesoftware.com/` | 一键控车（R 车型/其它） | 同上 |
| `https://appserver.nokeeu.com/api/` | Ingeek 数字钥匙生产 API | `BaseEnvironmentService` |
| `https://mweb.mos.csvw.com/` | H5 页面（钥匙分享/续费） | `KDConfig` / `PayCenterUtil` |
| `https://fawvw.askdwl.com/app` | KDWL 数字钥匙（一汽） | `KeyConstants` |
| `https://api-c-oneway-uat.mosc.faw-vw.com/vw-digitalkey/api/app` | 一汽数字钥匙 UAT | `KeyConstants` |

### 网关错误码（黑盒确认）

| 场景 | 响应 |
| --- | --- |
| 根路径 | `{"code":104000,"message":"COMMON_SYS_EXCEPTION"}` |
| `/api/` 缺 `x-app-id` | `{"code":20260001,"message":"HEADER_NOT_EXIST_APP_ID"}` |
| `/api/` 带 `x-app-id`（值无效） | `{"code":101102,"message":"COMMON_ARG_APP_ID_INVALID"}` |

`x-app-id` 的正确值在真实 dex 中（猜测为数字 ID）。

### Web 门户（补充探测）

| 域名 | 说明 |
| --- | --- |
| `connectivity.svw-volkswagen.com` | 智慧车联官方介绍页（营销页，无 Web 远程控车） |
| `pass.svw-volkswagen.com/login` | SVW 统一 SSO 登录（UC/商城共用），可能与 App 登录同源 |
| `uc.svw-volkswagen.com` | 二手车/用户中心，页面 JS 里出现 `myVehicles` / `defaultCar` 数据字段 |
| `connectivity.saicskoda.com.cn` | 斯柯达同族门户（仅介绍页） |

## 2. mTLS 客户端证书

- 文件：`res/raw/kd_client.p12`（已复制到 `tools/kd_client.p12`，2594 字节）。
- 用途：访问 `proxy-mbb-*` / `audi-proxy-bff-*` / `hu-api-*` 需要该客户端证书。
- 密码：未知（不在常见密码字典，需从 dex 或运行时提取）。

## 2.1 一键控车（TSP 场景）SDK 配置

```java
// com.saic.zone.zonemakerhttp.common.Const + HttpProxy
REMOTE_URL = "https://vw-onehitmobilesdk-af.mos.csvw.com/"   // 生产
APP_KEY    = "f23b6f2dc6cc47a5bfe3ae102f488826"              // 生产
APP_SECRET = "5da28ae18d1e43f8a34d8f90d3c01606"              // 生产
SIGN_KEY   = "973D5F1269759ECF2312D2F0E9C04671"
SECRET_KEY = "7D5F81A491CC90C2CB8148A1346557A9"
accountNo  = "acc2025062400270001"                            // ES33 生产
```

## 2.2 一键控车请求头与签名

```
version: <appVersion>   deviceId: <deviceId>   timestamp: <ms>   accountNo: acc2025062400270001
nonce: <uuid>   requestId: <ms>   signType: sha256Hex
x-device-from: IMAPP   deviceFrom: svwab   x-sdk-version: <sdkVer>
Authorization: Bearer <accessToken>
userId: <userId>   vin: <vin>   appKey: <APP_KEY>   clientType: APP
business: ZMAKER   loginVehicleType: SOA   loginManufacturer: RACAR   manufacturer: RACAR
clientName: SOA   x-body: <请求体原文>
sign: SHA256( [除 signType/sign 外，headers 按 key 字典序拼 k=v&k=v...] + SIGN_KEY ) 大写hex
```

token 流程：`POST /svwcar/ab/dev/auth/authapi/vehuser/exchangetoken/v2`（拿 accessToken/refreshToken）→
刷新 `refreshtoken/v1`。头里还有 `V_X_CHECK_TOKEN=2.0.0` / `V_X_NOT_CHECK_TOKEN=3.0.0` 版本标记。

## 3. 认证流程（社区确认 + 壳字符串线索）

```
登录 -> 原始长效 JWT
  -> PUT 刷新地址 -> 短时效 JWT
  -> 短时效 JWT + accessToken（与 JWT 绑定，需同步刷新）-> 业务接口
```

相关类（壳 dex 明文）：`com.svw.sc.mos.main.net.TokenInterceptor`、
`com.svw.sc.mos.main.net.RefreshTokenManager`、`/refreshToken/RefreshTokenManager`。

## 4. 业务模块路由（壳 dex 明文，ARouter）

车控相关 UI 路由（非 HTTP 路径，但指示功能模块）：

- `/afcar/remote/view`（远程影像）、`/afcar/charging/management/main`（充电管理）
- `/afcar/onehit/...`（一键场景）、`/afcar/smart/ac/...`（智能空调）
- `/afcar/car/finder/main`（找车）、`/afcar/digital/key/...`（数字钥匙）
- `/mycar/MyCarV2Activity`（我的车辆）、`/enrollment/CarVerifyMainActivity`（车辆绑定）
- `/mos/account/login`、`/mos/order/list`、`/mos/violation/payment`

## 5. 一键控车接口清单（已确认，`/svwcar/ab/...`）

### 车辆状态/功能

| 接口 | 说明 |
| --- | --- |
| `/svwcar/ab/vel/vehicle/sdkInit/v1` | SDK 初始化 |
| `/svwcar/ab/vel/vehicle/featureList/v3` | 车辆功能列表 |
| `/svwcar/ab/vel/vehicle/svw/getACStatus/v1` | **空调状态** |
| `/svwcar/ab/vel/vehicle/getValStatus/v1` | 车辆状态 |
| `/svwcar/ab/vel/vehicle/getOutsideMirrorStatus/v1` | 后视镜状态 |
| `/svwcar/ab/vel/vehicle/svw/getAddress/v1` | 车辆地址 |
| `/svwcar/ab/vel/vehicle/svw/getAmbientLamp/v2` | 氛围灯 |
| `/svwcar/ab/vel/vehicle/svw/getDriverPowerSeat/v1` 等 | 座椅状态 |
| `/svwcar/ab/vel/vehicle/appInit/v2` | App 初始化 |

### 场景（OneHit 一键）

| 接口 | 说明 |
| --- | --- |
| `/svwcar/ab/aoh/sm/user/scene/createScene/v1` / `modifyScene/v2` / `checkSceneNumber/v1` | 场景增改 |
| `/svwcar/ab/aoh/sm/user/scene/getExecuteNumber` | 执行次数 |
| `/svwcar/ab/aoh/scene/task/saveVentilationTask` / `getTaskInterval` | 通风任务 |
| `/svwcar/ab/aoh/sm/scene/share/changeAuthorize/v1` / `shareScene` | 场景分享 |

### 认证

| 接口 | 说明 |
| --- | --- |
| `/svwcar/ab/dev/auth/authapi/vehuser/exchangetoken/v2` | exToken（拿 accessToken） |
| `/racar/dev/auth/authapi/vehuser/refreshtoken/v1` | 刷新 token（BuildConfig 路径，生产可能不同） |

## 5. 待补全（脱壳后）

- [ ] 全部 Retrofit 接口路径（搜 `@GET`/`@POST`）
- [ ] `x-app-id` 正确值
- [ ] 白盒密钥获取接口（`WhiteBoxKeyServiceImpl`）
- [ ] JWT 刷新地址（PUT）
- [ ] mTLS 证书密码
