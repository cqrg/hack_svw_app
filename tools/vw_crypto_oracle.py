#!/usr/bin/env python3
"""vw_crypto_oracle.py - 通过 unidbg 调用真实 libvwappwbox{2024,2025}_crypto_tool.so

该 App 的加解密在 native 库中实现（自定义 wbox 白盒 AES 变体），且密钥由服务端
(WhiteBoxKeyService) 下发。在拿到真实密钥之前，可以用本脚本 + 真实 so 作为加解密
oracle 验证算法假设；拿到密钥后，若需要在纯 Python 里复现，需继续逆向该自定义
cipher（见 REVERSE_NOTES.md 第 5 节）。

依赖：
  - JDK 17（本机：D:\\aigc\\gmiot.net\\analysis\\android\\jdk17\\...）
  - unidbg classpath（cp.txt，来自 D:\\aigc\\gmiot.net\\analysis\\android\\cp.txt）
  - 已编译的 CallVwCryptoTool.class
"""
import base64
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JAVA = r"D:\aigc\gmiot.net\analysis\android\jdk17\jdk-17.0.20+8\bin\java.exe"
CP = (HERE / "unidbg-runner" / "cp.txt").read_text(encoding="utf-8", errors="ignore").strip()
OUT = HERE / "unidbg-runner" / "out"
SO25 = r"D:\aigc\gmiot.net-bmw\androws\decompiled\apktool\lib\arm64-v8a\libvwappwbox2025_crypto_tool.so"
SO24 = r"D:\aigc\gmiot.net-bmw\androws\decompiled\apktool\lib\arm64-v8a\libvwappwbox2024_crypto_tool.so"
APK = r"D:\aigc\gmiot.net-bmw\androws\androws_1786517045399.apk"


def call(so: str, method: str, data, key_hex: str, iv_hex: str) -> str:
    """data 为 str（String 方法）或 bytes（ByteArr 方法）。"""
    if isinstance(data, bytes):
        data_arg = data.hex()
    else:
        data_arg = data
    cmd = [JAVA, "-cp", f"{CP};{OUT}", "CallVwCryptoTool", so, APK, method,
           data_arg, key_hex, iv_hex]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    for line in r.stdout.splitlines():
        if line.startswith("RESULT="):
            return line[len("RESULT="):]
    raise RuntimeError(f"call failed\nstdout={r.stdout}\nstderr={r.stderr}")


def aes_encrypt_str(so: str, plaintext: str, key_hex: str, iv_hex: str) -> str:
    return call(so, "aesEncryptStringWithBase64", plaintext, key_hex, iv_hex)


def aes_decrypt_str(so: str, b64: str, key_hex: str, iv_hex: str) -> str:
    return call(so, "aesDecryptStringWithBase64", b64, key_hex, iv_hex)


def common_encrypt(so: str, data: bytes, key_hex: str, iv_hex: str) -> bytes:
    return bytes.fromhex(call(so, "commonEncryptByteArr", data, key_hex, iv_hex))


if __name__ == "__main__":
    # 自检：2025 so + 合法测试密钥（key 头 00 a7 26 00 + 16B 材料）
    key25 = "00a72600" + "0102030405060708090a0b0c0d0e0f10"
    iv = "000102030405060708090a0b0c0d0e0f"
    ct = aes_encrypt_str(SO25, "hello world", key25, iv)
    print("2025 enc:", ct)
    # 注：构造密钥（xor=0）仅加密方向可用，解密返回 null（真实密钥变体未知），
    # 因此这里不做解密断言。
    key24 = "00dcb200" + "0102030405060708090a0b0c0d0e0f10"
    ct24 = aes_encrypt_str(SO24, "hello world", key24, iv)
    print("2024 enc:", ct24)
    assert ct and ct24, "加密调用失败"
    print("self-test OK (encrypt oracle works for 2024/2025)")
