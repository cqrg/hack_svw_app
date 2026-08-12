#!/usr/bin/env python3
"""dump_dex.py - Frida 附加到 com.svw.sc.mos 并 dump 内存中的 dex。

用法：
    python dump_dex.py            # 附加到正在运行的 App
    python dump_dex.py --spawn    # 冷启动 App 再附加

输出：当前目录 dex_dump/classesN.dex

原理：SecNeo 运行时用 InMemoryDexClassLoader / DexFile 加载解密后的 dex，
内存中的 dex 以 "dex\n0x03x\0" magic 开头，扫描进程内存即可 dump。
"""
import argparse
import os
import sys

import frida

PKG = "com.svw.sc.mos"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dex_dump")

SCRIPT = r"""
function dump_dex(offset, size) {
    if (size < 0x70) return;
    var magic = Memory.readByteArray(ptr(offset), 8);
    var bytes = new Uint8Array(magic);
    if (bytes[0] !== 0x64 || bytes[1] !== 0x65 || bytes[2] !== 0x78) return; // 'dex'
    var fileSize = Memory.readU32(ptr(offset).add(0x20));
    if (fileSize > size || fileSize < 0x70 || fileSize > 0x80000000) return;
    var data = Memory.readByteArray(ptr(offset), fileSize);
    var name = "/data/local/tmp/dex_dump_" + offset.toString(16) + ".dex";
    var f = new File(name, "wb");
    f.write(data);
    f.close();
    send({type: "dex", offset: offset.toString(16), size: fileSize, name: name});
}

function scan() {
    var ranges = Process.enumerateRanges("r--");
    for (var i = 0; i < ranges.length; i++) {
        var r = ranges[i];
        try {
            // 粗略扫描每个可读区域找 dex magic（只扫前 64MB 以提速）
            if (r.size > 0x4000000) continue;
            var p = ptr(r.base);
            var end = p.add(r.size);
            var step = ptr(0x1000);
            while (p.compare(end) < 0) {
                var b = Memory.readU8(p);
                if (b === 0x64) { // 'd'
                    dump_dex(p, 0x100000);
                    p = p.add(step);
                } else {
                    p = p.add(1);
                }
            }
        } catch (e) {}
    }
}

rpc.exports = { scan: scan };
"""


def on_message(message, data):
    if message["type"] == "send":
        payload = message["payload"]
        if payload.get("type") == "dex":
            print(f"[+] dex @ {payload['offset']} size={payload['size']} -> {payload['name']}")
    elif message["type"] == "error":
        print(f"[!] error: {message.get('stack', message)}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spawn", action="store_true", help="冷启动 App")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    try:
        device = frida.get_usb_device(timeout=5)
    except frida.InvalidArgumentError:
        print("[!] 未找到 USB 设备，请确认 adb 已连接且手机开启 USB 调试", file=sys.stderr)
        sys.exit(1)

    if args.spawn:
        pid = device.spawn([PKG])
        session = device.attach(pid)
        script = session.create_script(SCRIPT)
        script.on("message", on_message)
        script.load()
        device.resume(pid)
    else:
        session = device.attach(PKG)
        script = session.create_script(SCRIPT)
        script.on("message", on_message)
        script.load()

    print(f"[*] 已附加 {PKG}，开始扫描内存 dex ...")
    script.exports_sync.scan()
    print("[*] 扫描完成。文件在 /data/local/tmp/，拉取到电脑：")
    print(f"    adb pull /data/local/tmp/ {OUT}/")
    session.detach()


if __name__ == "__main__":
    main()
