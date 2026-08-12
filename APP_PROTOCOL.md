# 上汽大众超级App - 协议与签名算法

> 状态：native 加密库接口已确认可调用；自定义 cipher 未完全复现；白盒密钥由服务端下发（待脱壳）。

## 1. 加密库协议

### 1.1 库与 JNI 入口

包对应关系：

| so | Java 类 |
| --- | --- |
| `libvwappwbox2024_crypto_tool.so` | `com.vwappwbox2024.CryptoTool` |
| `libvwappwbox2025_crypto_tool.so` | `com.vwappwbox2025.CryptoTool` |
| `libaudiappwbox_crypto_tool.so` | `com.audiappwbox.CryptoTool` |
| `libskodaappwbox_crypto_tool.so` | `com.skodaappwbox.CryptoTool` |

### 1.2 JNI 签名

```java
// data: 明文（String）或密文（byte[]）；keyHex: 结构化密钥 hex 串；iv: 16 字节 IV
String aesEncryptStringWithBase64(String data, String keyHex, byte[] iv);
String aesDecryptStringWithBase64(String data, String keyHex, byte[] iv);
byte[] aesEncryptByteArr(byte[] data, String keyHex, byte[] iv);
byte[] aesDecryptByteArr(byte[] data, String keyHex, byte[] iv);
byte[] commonEncryptByteArr(byte[] data, String keyHex, byte[] iv);
byte[] commonDecryptByteArr(byte[] data, String keyHex, byte[] iv);
```

模式选择（全局 `[base+0x81058]`，由 JNI 包装函数设置）：

| 方法族 | mode | 内部函数 |
| --- | --- | --- |
| `aes*` | 0 | `vwappwboxYYYY_AES_cbc_encrypt/decrypt` |
| `common*` | 8 | `vwappwboxYYYY_skb_encrypt/decrypt` |
| 其它 | 其它 | `vwappwboxYYYY_AES_ecb_*` |

### 1.3 密钥结构（结构化密钥）

```
key[0]  key[1]   key[2]   key[3]   key[4..keylen-1]
可变    魔数     魔数     可变     密钥材料（长度 keylen-4）
```

- 魔数：2025 版 `0xa7 0x26`；2024 版 `0xdc 0xb2`（实测）。
- `variant = key[0] ^ key[3]`，要求 `<= 0x19`，经 26 项跳转表选变体。
- 实际密钥：`newkey[i] = key[i+4] ^ key[i % 3]`（i = 0..keylen-5）。
- 变体参数（在函数内 `[sp+0x94/0x98/0x9c/0xa0]`）：
  - `[0x94]` = 块类型 w4（0 表示 CBC 兼容；9/7/6/5/4/3/2/1/0 各对应一种配置）
  - `[0x98]` = 密钥位长（0x40=64, 0x80=128, 0xc0=192, 0x100=256）
  - `[0x9c]` = 填充标志，`[0xa0]` = 附加标志

> 实测：2025 so + key=`00a72600 0102030405060708090a0b0c0d0e0f10`（xor=0, w4=0）
> 加密 `"hello world"` → `dIXHE/ZkSTo0+opymY+QPw==`。该输出与标准 AES-128-CBC
> 各密钥假设均不一致 → 确认自定义 cipher。

### 1.4 完整性校验

`init` 校验包名 `com.svw.sc.mos` + APK 签名 MD5 `F1A1B7802057B665C22C982235E32BE1`，
失败 `exit(1)`。unidbg 调用时把 `init` patch 成 `ret` 并预置
`[base+0x81050]=1`、`[base+0x81054]=1`。

## 2. 认证协议（社区 + 壳字符串）

```
1. 登录 -> 原始长效 JWT
2. PUT <refresh端点>（带原始 JWT）-> 短时效 JWT
3. 业务请求头：短时效 JWT + accessToken（与 JWT 绑定，同步刷新）
```

对应实现类：`TokenInterceptor`、`RefreshTokenManager`。

## 3. 网关协议

- 网关：`proxy-cccdk-vwaf-prod.mos.csvw.com`（无 mTLS）
- 头：`x-app-id: <待提取>`
- 其它网关需要 mTLS：证书 `tools/kd_client.p12`

## 4. 复现状态

| 环节 | 状态 |
| --- | --- |
| so 调用（unidbg） | ✅ 已实现 `tools/vw_crypto_oracle.py` |
| 加密方向 | ✅ 可调用（变体 xor ∈ {0,2,4} 通过校验） |
| 解密方向 | ⚠️ 构造密钥的解密返回错误 2（真实密钥变体未知） |
| 纯 Python 复现 | ⚠️ 自定义 cipher 需完整逆向轮函数 |
| 密钥获取 | ❌ 服务端下发，待 dex |
| 登录/刷新 | ❌ 待 dex |
