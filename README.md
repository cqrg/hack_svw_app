# 上汽大众超级App（ID.3）逆向 → HA 集成

与 [bmw/](../bmw/) 同模式的项目。目标：把 `com.svw.sc.mos`（上汽大众超级App，
ID.3 车控）的私有 API 逆向出来，供 Home Assistant 使用。

## 当前状态（诚实版）

| 模块 | 状态 |
| --- | --- |
| App 识别 | ✅ v5.0.5，包名 `com.svw.sc.mos` |
| 加固识别 | ✅ **SecNeo（梆梆）**，2022-03 至今所有可下载版本均加固 |
| 后端域名测绘 | ✅ `*.mos.csvw.com` 体系，`proxy-cccdk-vwaf-prod` 网关（需 `x-app-id`），其余需 mTLS |
| native 加密库 | ✅ JNI 接口/密钥结构/init 校验已逆向，unidbg 可调用（`tools/vw_crypto_oracle.py`） |
| 真实 dex（URL/请求体/白盒密钥） | ❌ 被 SecNeo 加密，**本机无模拟器（无 Hypervisor）** |
| 登录/车控 API | ❌ 待脱壳 |

**一句话：** 这是一个"万事俱备、只欠脱壳"的工程。所有能静态做的都做完了，
唯一缺口是真实 dex，而它只需要一台手机 + Frida（约 10 分钟），见
`tools/frida-dump/README.md`。

## 目录

```
svw/
├── REVERSE_NOTES.md            # 逆向全过程、坑、结论
├── API_REFERENCE.md            # 后端域名、网关、错误码
├── APP_PROTOCOL.md             # 加密库协议、密钥结构、认证流程
├── svw_client.py               # 客户端骨架（TODO 标注待补全处）
├── custom_components/
│   └── svw_tracker/            # HA 集成骨架
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

# 2. 在真机 dump dex（解锁全部 API）
cd tools/frida-dump && python dump_dex.py --spawn
```

## 已确认的关键事实

- 网关 `proxy-cccdk-vwaf-prod.mos.csvw.com/api/` 返回
  `HEADER_NOT_EXIST_APP_ID` / `COMMON_ARG_APP_ID_INVALID` → 需要 `x-app-id` 头。
- `libvwappwbox2025_crypto_tool.so` 的 JNI：`(data, keyHex, byte[])`，
  密钥带 4 字节头（魔数 `a7 26`），`key[0]^key[3]` 选变体，实际密钥
  `newkey[i]=key[i+4]^key[i%3]`，自定义白盒 cipher（非标准 AES）。
- 白盒密钥由服务端 `WhiteBoxKeyServiceImpl` 下发，必须在 dex 中提取。

## 后续（脱壳后）

1. jadx 反编译真实 dex，搜 `Retrofit` 接口/`OkHttp` interceptor 提取全部 API。
2. hook `WhiteBoxKeyServiceImpl` 拿密钥，用 oracle 验证。
3. 按社区流程复刻 JWT 登录/刷新（PUT 刷新 + accessToken）。
4. 补全 `svw_client.py` 与 `custom_components/svw_tracker/`。
