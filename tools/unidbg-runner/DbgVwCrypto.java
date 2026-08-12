import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Emulator;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.DalvikModule;
import com.github.unidbg.linux.android.dvm.DvmClass;
import com.github.unidbg.linux.android.dvm.DvmObject;
import com.github.unidbg.linux.android.dvm.StringObject;
import com.github.unidbg.linux.android.dvm.AbstractJni;
import com.github.unidbg.linux.android.dvm.VM;
import com.github.unidbg.memory.Memory;
import com.github.unidbg.hook.ReplaceCallback;
import com.github.unidbg.hook.whale.IWhale;
import com.github.unidbg.hook.whale.Whale;
import com.github.unidbg.arm.HookStatus;
import com.github.unidbg.hook.HookContext;
import com.github.unidbg.pointer.UnidbgPointer;
import com.sun.jna.Pointer;

import java.io.File;

/**
 * Debug runner: hooks malloc/free/AES and calls aesEncryptStringWithBase64.
 * Usage: java DbgVwCrypto <so> <apk> <method> <data> <keyHex> <ivHex>
 */
public class DbgVwCrypto {

    static long base;

    public static void main(String[] args) throws Exception {
        String soPath = args[0];
        String apkPath = args[1];
        String method = args[2];
        String data = args[3];
        String keyHex = args[4];
        String ivHex = args[5];

        AndroidEmulator emulator = AndroidEmulatorBuilder.for64Bit()
                .setProcessName("com.svw.sc.mos")
                .build();
        Memory memory = emulator.getMemory();
        memory.setLibraryResolver(new AndroidResolver(23));
        VM vm = emulator.createDalvikVM(new File(apkPath));
        vm.setVerbose(false);
        vm.setJni(new AbstractJni() {});

        DalvikModule dm = vm.loadLibrary(new File(soPath), false);
        base = dm.getModule().base;
        System.out.println("base=" + Long.toHexString(base));
        // Patch vwappwbox2025_init (0x1164) to `ret` so the package/signature
        // integrity check is skipped (unidbg cannot fake PackageManager/signature).
        UnidbgPointer initPtr = UnidbgPointer.pointer(emulator, base + 0x1164);
        initPtr.setByte(0, (byte) 0xC0);
        initPtr.setByte(1, (byte) 0x03);
        initPtr.setByte(2, (byte) 0x5F);
        initPtr.setByte(3, (byte) 0xD6); // ret
        System.out.println("patched init @ " + Long.toHexString(base + 0x1164));
        // Set the "initialized" globals that init would set on success:
        //   [base+0x81050] = 1  (init in progress / ready)
        //   [base+0x81054] = 1  (verification passed)
        UnidbgPointer g50 = UnidbgPointer.pointer(emulator, base + 0x81050);
        g50.setInt(0, 1);
        UnidbgPointer g54 = UnidbgPointer.pointer(emulator, base + 0x81054);
        g54.setInt(0, 1);
        System.out.println("set init flags [0x81050]=1 [0x81054]=1");
        IWhale whale = Whale.getInstance(emulator);

        hook(whale, 0x18cc, "AES_cbc_encrypt", "pppippp");
        hook(whale, 0x24e0, "AES_cbc_decrypt", "pppippp");
        hook(whale, 0xb898, "b64_decode", "ppip");
        hook(whale, 0xbf84, "aesDecryptStringWithBase64", "pppp");

        DvmClass cls = vm.resolveClass("com/vwappwbox2025/CryptoTool");
        DvmObject<?> res = cls.callStaticJniMethodObject(
                emulator, method,
                data, keyHex, hex(ivHex));
        if (res instanceof StringObject) {
            System.out.println("RESULT=" + ((StringObject) res).getValue());
        } else {
            System.out.println("RESULT=" + res);
        }
        emulator.close();
    }

    static void hook(IWhale whale, long off, String label, String fmt) {
        whale.inlineHookFunction(base + off, new ReplaceCallback() {
            @Override
            public HookStatus onCall(Emulator<?> emu, HookContext ctx, long originFunction) {
                StringBuilder sb = new StringBuilder();
                sb.append("[").append(label).append("] ");
                int n = fmt.length();
                for (int i = 0; i < n; i++) {
                    char c = fmt.charAt(i);
                    if (c == 'p') {
                        sb.append("x").append(i).append("=").append(Long.toHexString(ctx.getLongArg(i))).append(" ");
                    } else if (c == 'i') {
                        sb.append("x").append(i).append("=").append(ctx.getIntArg(i)).append(" ");
                    }
                }
                sb.append("lr=").append(ctx.getLRPointer() == null ? "0" : Long.toHexString(ctx.getLRPointer().peer));
                System.out.println(sb);
                return HookStatus.RET(emu, originFunction);
            }
        });
    }

    static byte[] hex(String s) {
        s = s.replaceAll("\\s", "");
        byte[] out = new byte[s.length() / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(s.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }
}
