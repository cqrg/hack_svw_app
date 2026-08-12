# Frida 脱壳工具包（在真机上 dump 真实 dex）

## 为什么需要这个

`com.svw.sc.mos`（上汽大众超级App）使用 **SecNeo（梆梆）加固**，classes.dex 本体被加密，
只在运行时由 `libDexHelper.so` 解密并加载到内存。静态解包拿不到真实 dex，因此 API 的
URL / 请求体 / 白盒密钥来源全部拿不到。本机无模拟器（无 WHPX/AEHD 硬件加速），
最快的解锁路径是：**在一台已 root 或可调试的 Android 手机上用 Frida dump 内存中的 dex**。

## 前置条件

1. 一台 Android 手机（Android 7+），已开启「开发者选项 → USB 调试」。
2. 电脑安装 adb（本机可从腾讯镜像下载 platform-tools）：
   ```powershell
   curl.exe -L -o platform-tools.zip https://mirrors.cloud.tencent.com/AndroidSDK/platform-tools-latest-windows.zip
   ```
3. 手机 CPU 架构：`adb shell getprop ro.product.cpu.abi`（arm64-v8a 居多）。
4. Python 3 + frida：
   ```powershell
   pip install frida frida-tools
   ```

## 步骤

### 1. 推送 frida-server 到手机

从 GitHub releases 下载与电脑 frida 版本一致的 `frida-server-<ver>-android-arm64.xz`，
解压后：

```powershell
adb push frida-server /data/local/tmp/
adb shell "chmod 755 /data/local/tmp/frida-server"
adb shell "su -c '/data/local/tmp/frida-server &'"   # 已 root
# 或未 root 但可调试：adb shell "/data/local/tmp/frida-server &"
```

### 2. 打开 App 到已登录/车控页，然后 dump

```powershell
adb shell "am start -n com.svw.sc.mos/.views.SplashActivity"
python dump_dex.py
```

`dump_dex.py` 会附加到进程、枚举所有已加载的 dex 内存段并落盘到 `dex_dump/`。

### 3. 把 dump 出的 dex 反编译

```powershell
jadx -d dex_src --no-res dex_dump/
```

## dump 之后做什么（对应本工程文档）

1. **提取 API 清单**：在反编译源码里搜 `@GET` / `@POST` / `Retrofit` 接口、`OkHttp`
   interceptor（`TokenInterceptor` / `AroutePathInterceptor`）、`*.csvw.com`。
2. **提取白盒密钥**：hook `com.svw.sc.mos.whiteboxkey.WhiteBoxKeyServiceImpl`，
   看服务端下发的 key（配合 `vw_crypto_oracle.py` 验证）。
3. **抓登录/刷新令牌**：参考社区流程（长时效 JWT → PUT 刷新 → 短时效 JWT + accessToken）。
4. **mTLS 证书**：`tools/kd_client.p12` 是网关客户端证书，密码需从 dex 或运行时提取。

## 常见问题

- frida-server 与电脑 frida 版本不一致 → 下载对应版本。
- App 有反调试（SecNeo/ingenic 检测）→ 用 `-f com.svw.sc.mos --no-pause` 启动并加
  `-o log.txt` 观察；必要时先 hook `dlopen` 禁用 `libDexHelper.so` 的检测。
