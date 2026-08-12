import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Emulator;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.DalvikModule;
import com.github.unidbg.linux.android.dvm.DvmClass;
import com.github.unidbg.linux.android.dvm.DvmObject;
import com.github.unidbg.linux.android.dvm.StringObject;
import com.github.unidbg.linux.android.dvm.array.ByteArray;
import com.github.unidbg.linux.android.dvm.BaseVM;
import com.github.unidbg.linux.android.dvm.AbstractJni;
import com.github.unidbg.linux.android.dvm.VM;
import com.github.unidbg.memory.Memory;
import com.github.unidbg.pointer.UnidbgPointer;

import java.io.File;
import java.util.Arrays;

/**
 * Call the real libvwappwbox{2024,2025}_crypto_tool.so JNI functions via unidbg.
 *
 * The lib performs an integrity check in vwappwboxXXXX_init (package name +
 * APK signature MD5) and exits on failure; we patch init to `ret` and preset
 * the "initialized" globals so the crypto calls succeed.
 *
 * Usage:
 *   java CallVwCryptoTool <so> <apk> <method> <data> [keyHex] [ivHex]
 *
 * method: aesEncryptStringWithBase64 | aesDecryptStringWithBase64
 *         aesEncryptByteArr | aesDecryptByteArr
 *         commonEncryptByteArr | commonDecryptByteArr
 *
 * Example:
 *   java CallVwCryptoTool libvwappwbox2025_crypto_tool.so app.apk \
 *        aesEncryptStringWithBase64 "hello world" \
 *        "00a72600..." "000102030405060708090a0b0c0d0e0f"
 */
public class CallVwCryptoTool {

    public static void main(String[] args) throws Exception {
        String soPath = args[0];
        String apkPath = args[1];
        String method = args[2];
        String data = args[3];
        String keyHex = args.length > 4 ? args[4] : null;
        String ivHex = args.length > 5 ? args[5] : null;

        AndroidEmulator emulator = AndroidEmulatorBuilder.for64Bit()
                .setProcessName("com.svw.sc.mos")
                .build();
        Memory memory = emulator.getMemory();
        memory.setLibraryResolver(new AndroidResolver(23));

        VM vm = emulator.createDalvikVM(new File(apkPath));
        vm.setVerbose(false);
        System.out.println("VM packageName=" + vm.getPackageName());
        vm.setJni(new AbstractJni() {});

        DalvikModule dm = vm.loadLibrary(new File(soPath), false);
        long base = dm.getModule().base;
        System.out.println("loaded " + new File(soPath).getName() + " base=" + Long.toHexString(base));

        // Patch init to `ret` (skip package/signature integrity check)
        UnidbgPointer initPtr = UnidbgPointer.pointer(emulator, base + 0x1164);
        initPtr.setByte(0, (byte) 0xC0);
        initPtr.setByte(1, (byte) 0x03);
        initPtr.setByte(2, (byte) 0x5F);
        initPtr.setByte(3, (byte) 0xD6); // ret
        // Preset "initialized" globals (see REVERSE_NOTES.md):
        UnidbgPointer.pointer(emulator, base + 0x81050).setInt(0, 1);
        UnidbgPointer.pointer(emulator, base + 0x81054).setInt(0, 1);
        System.out.println("patched init; flags [0x81050]=1 [0x81054]=1");

        DvmClass cls = vm.resolveClass(guessClassName(new File(soPath).getName()));
        System.out.println("class=" + cls.getClassName());

        boolean returnsByteArr = method.contains("ByteArr");
        Object res;
        if (returnsByteArr) {
            // byte[] data, String keyHex, byte[] iv
            byte[] iv = ivHex == null ? new byte[0] : hex(ivHex);
            res = cls.callStaticJniMethodObject(emulator, method,
                    hex(data), keyHex, iv);
            if (res instanceof ByteArray) {
                byte[] out = ((ByteArray) res).getValue();
                System.out.println("RESULT_HEX=" + toHex(out));
                System.out.println("RESULT_B64=" + java.util.Base64.getEncoder().encodeToString(out));
            } else {
                System.out.println("RESULT=" + res);
            }
        } else {
            // String data, String keyHex, byte[] iv
            byte[] iv = ivHex == null ? new byte[0] : hex(ivHex);
            res = cls.callStaticJniMethodObject(emulator, method, data, keyHex, iv);
            if (res instanceof StringObject) {
                System.out.println("RESULT=" + ((StringObject) res).getValue());
            } else {
                System.out.println("RESULT=" + res);
            }
        }
        emulator.close();
    }

    private static String guessClassName(String soName) {
        if (soName.startsWith("libvwappwbox2024")) return "com/vwappwbox2024/CryptoTool";
        if (soName.startsWith("libvwappwbox2025")) return "com/vwappwbox2025/CryptoTool";
        if (soName.startsWith("libaudiappwbox")) return "com/audiappwbox/CryptoTool";
        if (soName.startsWith("libskodaappwbox")) return "com/skodaappwbox/CryptoTool";
        return "com/vwappwbox/CryptoTool";
    }

    private static byte[] hex(String s) {
        s = s.replaceAll("\\s", "");
        byte[] out = new byte[s.length() / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(s.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }

    private static String toHex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) sb.append(String.format("%02x", x & 0xff));
        return sb.toString();
    }
}
