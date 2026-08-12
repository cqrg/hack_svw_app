# 上汽大众超级App（ID.3 车控）逆向笔记

> 目标：从 `com.svw.sc.mos` 提取车控 API 供 Home Assistant 使用（与 gmiot / BMW 同一模式）。
> 结论先行：**App 使用 SecNeo（梆梆）加固，所有可下载版本均加固，本机无模拟器/真机，
> 真实 dex（URL / 请求体 / 白盒密钥）暂时无法静态提取。** 但已完成后端域名测绘、
> native 加密库逆向（可调用）、网关/证书分析，并把解锁路径整理为 `tools/frida-dump/`。

## 1. 样本与识别

| 项目 | 值 |
| --- | --- |
| APK | `androws_1786517045399.apk`（483MB，小米商店 v5.0.5，2026-07） |
| 包名 | `com.svw.sc.mos` |
| 架构 | 混合：Java 业务（classes.dex 212MB）+ Unity il2cpp 3D 车模 |
| 加固 | **SecNeo（梆梆安全）**：manifest `android:name="com.secneo.apkwrapper.AW"`，壳 so `libDexHelper.so` |
| 编译 SDK | 36（Android 16） |

### 下载渠道

- 522gg：v2.28.0（2025-09，193M）——直链 `apk.down8818.com`，但也是 SecNeo 加固。
- 9k9k：`sqdz_130844.apk`（2022-03，256M）——**同样是 SecNeo 加固**（dex 头字段乱值）。
- doyo：v2.30.1（2024-01）——需 POST `/down`，未拿到直链。
- pgyer：2022-11 测试包——`/app/install/<key>` 提示"该应用无法下载"。
- 结论：**2022-03 至今的版本全部 SecNeo 加固**，静态反编译均不可行。

## 2. 加固结构与脱壳评估

### classes.dex 壳结构（v5.0.5）

```
file_size=212928476
data_off=117, data_size=11872   <- 有效 dex 仅 ~12KB（入口/壳类）
尾部 ~212,916,487 字节          <- 加密载荷（真实 dex 的密文）
```

- dex 头字段（string_ids_size 等）全是乱值 → 头部也被加密。
- 壳 dex 仅 1166 个可读字符串，类名/ARouter 路由明文，**URL 全部加密**。

### libDexHelper.so

- 1.2MB，无导出符号（除 `JNI_OnLoad`），字符串加密，反编译成本极高。
- 2022 版与 2025 版 md5 不同（SecNeo 版本不同），但都同样混淆。

### 脱壳路径评估

| 路径 | 可行性 | 备注 |
| --- | --- | --- |
| 旧版未加固 APK | ❌ | 2022-03 起全部加固 |
| 本机模拟器 + Frida dump | ❌ | **本机无 Hypervisor（`HypervisorPresent=False`）**，x86_64 镜像需 WHPX/AEHD（需管理员+重启），ARM 镜像被拒 |
| 真机 + Frida | ✅ 推荐 | 见 `tools/frida-dump/`，几分钟可完成 |
| 静态逆向 libDexHelper 解密 | ⚠️ 成本极高 | 混淆+字符串加密，无公开工具匹配该版本 |

## 3. 后端域名测绘（已完成）

### 已知域名

- 9k9k 页面泄露：`mos-public-prod.mos.csvw.com`（OSS 静态资源，`/prod/richText/...` 隐私政策）。
- certspotter 证书透明日志：`*.mos.csvw.com` 共 29 个子域，关键：
  - `proxy-mbb-live.mos.csvw.com`、`proxy-mbb-audi.mos.csvw.com`、`proxy-mbb-skd.mos.csvw.com`（MBB 网关）
  - `audi-proxy-bff-prod.mos.csvw.com`（Audi BFF）
  - `mos-core-live-signature.mos.csvw.com`（签名服务，当前 DNS 不解析）
  - `proxy-cccdk-vwaf-prod.mos.csvw.com`（**VWAF 网关，唯一无 mTLS 要求的入口**）
  - `hu-api-*`（车机 HU API）

### 网关行为

| 域名 | 行为 |
| --- | --- |
| `proxy-mbb-live` / `audi-proxy-bff-prod` / `hu-api-platform` | 400 **"No required SSL certificate was sent"**（要求 mTLS） |
| `proxy-cccdk-vwaf-prod` | 无需 mTLS；`/api/` 返回 `{"code":20260001,"message":"HEADER_NOT_EXIST_APP_ID"}`；带 `x-app-id` 头后返回 `{"code":101102,"message":"COMMON_ARG_APP_ID_INVALID"}` |

- `x-app-id` 是网关识别的头名，但正确取值未知（在真实 dex 中），猜测为数字 ID。
- mTLS 客户端证书：`res/raw/kd_client.p12`（已复制到 `tools/kd_client.p12`），密码未知（需 dex）。

## 4. Native 加密库逆向（已完成，可调用）

### 4.1 库清单（未被壳加密）

| so | 大小 | 说明 |
| --- | --- | --- |
| `libvwappwbox2024_crypto_tool.so` / `libvwappwbox2025_crypto_tool.so` | 464KB | VW 品牌加解密工具（2024/2025 两个版本，2024 版 2022 与 2025 APK 中 md5 一致） |
| `libaudiappwbox_crypto_tool.so` / `libskodaappwbox_crypto_tool.so` | 58KB | 奥迪/斯柯达同族工具，白盒 AES（`WB_LAES`） |
| `libcccplus_rpa_svw.so` | 1.3MB | 遥控泊车（RPA），与车控 API 关系不大 |

### 4.2 JNI 导出（关键）

`libvwappwbox2025_crypto_tool.so` 导出（2024 同名替换 2024）：

```
Java_com_vwappwbox2025_CryptoTool_aesEncryptStringWithBase64
Java_com_vwappwbox2025_CryptoTool_aesDecryptStringWithBase64
Java_com_vwappwbox2025_CryptoTool_aesEncryptByteArr
Java_com_vwappwbox2025_CryptoTool_aesDecryptByteArr
Java_com_vwappwbox2025_CryptoTool_commonEncryptByteArr
Java_com_vwappwbox2025_CryptoTool_commonDecryptByteArr
vwappwbox2025_init / AES_cbc_encrypt / AES_cbc_decrypt / AES_ecb_encrypt / AES_ecb_decrypt / skb_encrypt / skb_decrypt
```

### 4.3 Java 方法签名（已从反汇编确定）

所有 6 个 JNI 方法都是 **3 个参数**：

```java
// String 版本（base64 出入参）
String aesEncryptStringWithBase64(String data, String keyHex, byte[] iv);
String aesDecryptStringWithBase64(String data, String keyHex, byte[] iv);
// byte[] 版本
byte[] aesEncryptByteArr(byte[] data, String keyHex, byte[] iv);
byte[] aesDecryptByteArr(byte[] data, String keyHex, byte[] iv);
byte[] commonEncryptByteArr(byte[] data, String keyHex, byte[] iv);
byte[] commonDecryptByteArr(byte[] data, String keyHex, byte[] iv);
```

区别只在全局模式 `[0x81058]`：

| 方法 | mode | 调用的内部函数 |
| --- | --- | --- |
| `aes*` | 0 | `AES_cbc_encrypt/decrypt` |
| `common*` | 8 | `skb_encrypt/decrypt` |
| （其他） | 其它 | `AES_ecb_*` |

### 4.4 init 完整性校验（已绕过）

`vwappwbox2025_init`（0x1164）通过 JNI 反射：

1. `ActivityThread.currentActivityThread().getSystemContext().getPackageName()` → 校验 == `com.svw.sc.mos`
2. `getPackageManager().getPackageInfo(pkg, GET_SIGNATURES)` → 签名字节 → MD5 → 校验 == `F1A1B7802057B665C22C982235E32BE1`
3. 失败 → `exit(1)` / 错误码

unidbg 中无法伪造签名 → 把 init 首条指令 patch 成 `ret`，并把全局标志
`[base+0x81050]=1`、`[base+0x81054]=1` 预置，即可跳过校验。已实现在
`tools/unidbg-runner/CallVwCryptoTool.java`。

### 4.5 密钥结构（关键）

传入的 `keyHex` 不是裸 AES 密钥，而是 **带 4 字节头的结构化密钥**：

```
key[0]   key[1]      key[2]      key[3]    key[4..]
可变     魔数        魔数        可变       密钥材料
2025版:  0xa7        0x26
2024版:  0xdc        0xb2
```

- `key[0] ^ key[3] <= 0x19(25)`，该 XOR 值经跳转表选择**加密变体**（26 种，多数是
  反逆向诱饵）。已知变体参数：`[0x94]=w4(块类型)`、`[0x98]=密钥位长(0x40/0x80/0xc0/0x100)`、
  `[0x9c]=填充`、`[0xa0]`。
- 实际密钥派生：`newkey[i] = key[i+4] ^ key[i % 3]`，长度 = keylen - 4。
- 校验：`key[1]==0xa7 && key[2]==0x26`（2025），否则错误 104。
- 2024 版实测可用头 `00 dc b2 00`；2025 版实测可用头 `00 a7 26 00`（xor=0，w4=0）。

### 4.6 自定义 cipher（未完全复现）

- so 中**不包含标准 AES S-box**，是自定义 wbox 白盒变体（与奥迪/斯柯达 `WB_LAES` 同族）。
- 用构造密钥验证：2025 so 加密 `"hello world"`（key=`00a72600...`）→ `dIXHE/ZkSTo0+opymY+QPw==`，
  与标准 AES-128-CBC 各假设均不一致 → 确认非标准实现。
- 解密方向对构造密钥返回错误 2（该变体仅加密侧可用），说明真实密钥的头会选中一个
  加解密对称的变体。
- **结论**：纯 Python 复现需完整逆向自定义 cipher 轮函数（工作量大）；在拿到真实密钥前，
  用 `tools/vw_crypto_oracle.py`（unidbg + 真实 so）作为加解密 oracle 更实际。

### 4.7 白盒密钥来源（待 dex）

- shell 字符串：`/whiteBox/WhiteBoxKeyServiceImpl`、`com/svw/sc/mos/whiteboxkey/WhiteBoxKeyServiceImpl`
- 密钥由**服务端下发**（不是写死在 so），所以必须拿到真实 dex 才能复刻获取流程。

## 5. 认证/登录线索（社区情报）

精易论坛（上汽大众自动签到）描述：

1. 抓包得到**原始长效 JWT**；
2. 用原始 JWT 访问刷新地址（**必须是 PUT**）得到**新的短时效 JWT**；
3. 短时效 JWT + **accessToken**（accessToken 也要用旧 accessToken 刷新，二者绑定）访问业务接口；
4. 频繁用旧 accessToken 配新 JWT 会被风控。

对应 shell 字符串里的 `RefreshTokenManager` / `TokenInterceptor` / `/refreshToken/RefreshTokenManager`。
一汽大众同族 App（com.dssomobile.oneApp）的 HA 方案使用
`oneapp-api.faw-vw.com/mycar/car-networking/...`（bbs.hassbian 帖），上汽大众后端不同
（`*.mos.csvw.com`），但 MBB 框架结构可能相似。

## 6. 已完成的工具

| 工具 | 说明 |
| --- | --- |
| `tools/unidbg-runner/CallVwCryptoTool.java` | unidbg 调用真实 so（自动识别 2024/2025、绕过 init、支持 6 个 JNI 方法） |
| `tools/unidbg-runner/DbgVwCrypto.java` | 带 hook 的调试版（AES 出入参、base64 解码、JNI 调用） |
| `tools/vw_crypto_oracle.py` | Python 封装，调用真实 so 做加解密 oracle |
| `tools/frida-dump/` | 真机 Frida 脱壳工具包 + 说明 |
| `tools/kd_client.p12` | mTLS 网关客户端证书（密码未知） |

### 运行方式

```powershell
# 编译
javac -encoding UTF-8 -cp (Get-Content -Raw tools/unidbg-runner/cp.txt) `
      -d tools/unidbg-runner/out tools/unidbg-runner/CallVwCryptoTool.java
# 加密（2025）
java -cp "tools/unidbg-runner/cp.txt内容;tools/unidbg-runner/out" CallVwCryptoTool `
     <so2025> <apk> aesEncryptStringWithBase64 "hello world" "00a726000102030405060708090a0b0c0d0e0f10" "000102030405060708090a0b0c0d0e0f"
# 自检
python tools/vw_crypto_oracle.py
```

## 7. 下一步（解锁 dex 后）

1. 用 `tools/frida-dump/` 在真机 dump 真实 dex → jadx 反编译。
2. 搜 `Retrofit` 接口注解 / `OkHttp` interceptor，提取全部 URL 与请求头。
3. hook `WhiteBoxKeyServiceImpl` 拿服务端下发的白盒密钥，用 `vw_crypto_oracle.py` 验证。
4. 抓登录/刷新流程（PUT 刷新 JWT + accessToken），复刻到 `svw_client.py`。
5. 用 `tools/kd_client.p12` + 密码打通 mTLS 网关（若车控走 mTLS 网关）。
6. 补齐 `custom_components/svw_tracker/` 的 device_tracker 实现。

## 8. 关键坑

- PowerShell 写中文文件用 `[System.IO.File]::WriteAllText(path, content, (New-Object System.Text.UTF8Encoding $false))`。
- 大 APK 下载用 `curl.exe -L -C -` 断点续传；`Invoke-WebRequest` 大文件很慢。
- unidbg 调用前必须 `vm.setJni(new AbstractJni(){})`，否则报 `Please vm.setJni(jni)`。
- 全局变量地址是 `base + ELF VA`（如 `0x81050`），不是 `base + 0x10050`。
- 变体跳转表偏移是**带符号 16 位 × 4**：`target = 0x19e4 + (int16)table[xor] * 4`。
- `AES_cbc_decrypt` 在 0x24e0（0x1ef4 是 ecb_decrypt），hook 别弄错。
