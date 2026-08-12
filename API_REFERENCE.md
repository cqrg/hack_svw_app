# 上汽大众超级App - API 参考

> 状态：**部分确认**。真实接口路径与请求格式在 SecNeo 加固的 dex 中，待 Frida 脱壳后补全。
> 本文记录已确认的后端域名、网关行为与头字段。

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

### 网关错误码（黑盒确认）

| 场景 | 响应 |
| --- | --- |
| 根路径 | `{"code":104000,"message":"COMMON_SYS_EXCEPTION"}` |
| `/api/` 缺 `x-app-id` | `{"code":20260001,"message":"HEADER_NOT_EXIST_APP_ID"}` |
| `/api/` 带 `x-app-id`（值无效） | `{"code":101102,"message":"COMMON_ARG_APP_ID_INVALID"}` |

`x-app-id` 的正确值在真实 dex 中（猜测为数字 ID）。

## 2. mTLS 客户端证书

- 文件：`res/raw/kd_client.p12`（已复制到 `tools/kd_client.p12`，2594 字节）。
- 用途：访问 `proxy-mbb-*` / `audi-proxy-bff-*` / `hu-api-*` 需要该客户端证书。
- 密码：未知（不在常见密码字典，需从 dex 或运行时提取）。

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

## 5. 待补全（脱壳后）

- [ ] 全部 Retrofit 接口路径（搜 `@GET`/`@POST`）
- [ ] `x-app-id` 正确值
- [ ] 白盒密钥获取接口（`WhiteBoxKeyServiceImpl`）
- [ ] JWT 刷新地址（PUT）
- [ ] mTLS 证书密码
