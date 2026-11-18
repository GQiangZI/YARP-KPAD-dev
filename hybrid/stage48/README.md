# turner v3.35：有界服务查询桥接测试

本阶段优先验证 **data 元数据解密**。2026-11-18 实机反馈确认：recovery 可操作，
补丁已加载，fstab 修正已生效；但 `checkService` 与异步 `waitForService` 均为空，
**data 仍未解密**。不可标注为解密成功版。协议差异与下一步独立进程探针见
[stage49](../stage49/README.md)。主机测试和镜像校验通过不代表实机解密通过。

基底固定为用户实测的 v3.30，SHA256：
`aa0606d8d09d40f9988c8cd92b5c561e47360e6369bbca0f620b8730b219ae2d`。
v3.32–v3.34 的实机日志在本次会话未能取得原件；此前讨论中的恢复进程重启、
链接失败的外部探针均不作为本阶段已验证的修复依据。

## 两个修正

1. **在 recovery 内桥接查询**：先保留真实 `AServiceManager_checkService`。
   仅对 keystore2、KeyMint、Gatekeeper、SecureClock、SharedSecret 的默认实例，
   若查询为空，启动一个独立线程调用同进程的 `waitForService`。线程先幂等启动
   Binder 线程池，保证服务稍后注册时的通知能被处理。UI 线程立即返回空，沿用
   vold 原有的有界轮询；每个服务最多一个等待线程。成功返回的 Binder 保留一个
   缓存引用，每个调用方再获得自己的一份引用。可选/未知服务维持原行为。
2. **在读取时补齐 fstab**：仅处理 `/etc/additional.fstab` 及其 `/system/etc`
   别名的只读打开。仅当 `/data` 行含确切的
   `keydirectory=/metadata/vold/metadata_encryption` 且没有显式元数据 cipher 时，
   在第五字段追加 `metadata_encryption=aes-256-xts`。通过 memfd 返回修正内容，
   保留原文件、已装 ROM 的其他参数及任何已指定的 cipher。
   覆盖 `fopen`、`open`、`open64`、`__open_2`、`openat` 和 `__openat_2`。

这是对已报告阻断点的定向验证。`checkService` 失效的最终根因仍需本进程日志
确认；ABI/事务版本差异是待验证解释。若正常 `checkService` 本就成功，桥接不介入。

未修改 `sys.boot_completed`、平台版本/安全补丁属性、密码或密钥文件；
未引入 `PLATFORM_VERSION=99`。发现 `KEY_REQUIRES_UPGRADE` 时，先比较已装 ROM
与 HAL 实际读取的 OS/补丁参数，再决定修正；不可把提高版本当作无副作用的诊断。

## 镜像差异及边界

- F0：仅在现有 `service recovery` 下增加本补丁的 `LD_PRELOAD` 行。
- F1：新增 `libturner_crypto.so` 和只读诊断脚本；既有归档条目逐字节保持。
- Recovery、两套 Binder 库、HAL 监管脚本、触控/振动驱动、DTB、fstab 原文件，
  均从 v3.30 保留。解压/再压使用 legacy LZ4。
- 从基底继承的 LK/preloader dummy-link 机制原样保留。**这不等同于完整刷包防护**：
  本阶段未验证通过裸块设备、其他别名、update_engine/payload 访问时的保护。
  修复 data 后仍需单独实现刷包预检/拒绝策略，不能据此宣布所有路径都已拦截。
- 不新增 vendor_boot 刷入菜单、不处理 WiFi/OTG 上游升级；它们不影响本次验证。
- 等待线程及成功 Binder 缓存存活至进程退出；若 keystore2 后来崩溃重启，
  本阶段尚未实现死 Binder 缓存更新。正常 IPC 仍会报告服务死亡。

## 复现

主机：Python 3.12；`pip install ziglang==0.17.1 lz4 pyelftools`。
仅编译一个 ARM64、无额外 `DT_NEEDED` 的小型库。`generic+lse` 使用 ARMv8.1
的原子指令；本产物仅面向 turner/MT6991。

```sh
python3 tests/stage48/test_crypto_bridge.py
mkdir -p build
python3 -m ziglang cc -target aarch64-linux-android -mcpu=generic+lse \
  -Os -ffreestanding -fno-stack-protector -nostdlib -shared -fPIC -s \
  -Wall -Wextra -Werror -Wl,-z,max-page-size=4096 \
  -Wl,-soname,libturner_crypto.so \
  hybrid/stage48/libturner_crypto.c -o build/libturner_crypto.so
python3 hybrid/stage48/build.py \
  --base /absolute/path/turner-vendor_boot-hybrid-v3.30.img \
  --bridge build/libturner_crypto.so \
  --output /absolute/path/turner-vendor_boot-hybrid-v3.35-CRYPTO-BRIDGE-TEST.img
```

构建器拒绝不同的基底、测试版库、缺失的导出符号、基底 libc/libdl 不满足的导入、
意外归档差异、超出 64 MiB 或 AVB 哈希不匹配的输入/输出。AVB 保留基底的
`algorithm=NONE`，重新计算 salted SHA256；这属于哈希校验，不是新增可信签名。
不需要前 47 个阶段的本机路径或二进制。输出旁附 `.verification.json`。

## 实机验证

仅刷当前使用的 vendor_boot，保留原 v3.30 作为回退文件：

```sh
fastboot flash vendor_boot turner-vendor_boot-hybrid-v3.35-CRYPTO-BRIDGE-TEST.img
fastboot reboot recovery
```

观察内置存储是否显示容量、文件名及现有文件；有锁屏凭据时正常输入一次。
随后收集：

```sh
adb shell /system/bin/turner-crypto-status.sh
adb pull /tmp/turner-v335-logs.tar
```

ADB 不便时可在 recovery 终端运行 `/system/bin/turner-crypto-status.sh`，
再用文件管理器把 `/tmp/turner-v335-logs.tar` 复制到已挂载的 U 盘。

验收顺序：库确实加载 → fstab 修正被读取 → `checkService` 实际调用与异步返回
非空 → keystore2/KeyMint 收到密钥操作 → 元数据映射及 `/data` 挂载 → DE 可读 →
凭据验证及 CE 文件可读。仅 service list 能看到服务不算 data 解密成功。

主机测试覆盖异步等待、并发、引用计数、真实 ELF interposition、只读 fstab 视图、
不修改源文件、已有 cipher、注释/制表符/末行、溢出回退、缺失文件及文件描述符泄漏。
它们不能代替设备上的 Android 链接器、MiTEE、dm-default-key 与 FBE 实测。

参考代码：
- [YARP vold Keystore.cpp](https://github.com/TWRP-Test/android_system_vold/blob/twrp-16.0/Keystore.cpp)
- [YARP vold MetadataCrypt.cpp](https://github.com/TWRP-Test/android_system_vold/blob/twrp-16.0/MetadataCrypt.cpp)
- [AOSP NDK service manager](https://android.googlesource.com/platform/frameworks/native/+/android-16.0.0_r1/libs/binder/ndk/service_manager.cpp)
- [taiko 2404d58 发布说明](https://github.com/kodeaqua/android_device_xiaomi_taiko-twrp/releases/tag/2404d58)
