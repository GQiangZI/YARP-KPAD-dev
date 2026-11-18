# v3.35 实机反馈：ServiceManager 协议对照探针

本阶段交付 `turner-binder-probe.sh`，在当前 recovery 内启动三个独立的短进程。
无需重新刷镜像。探针只查询服务，不调用 KeyMint 密钥操作、不注册服务、不重启
recovery/HAL，不改属性、分区、密码或密钥。v2 由 shell 监管子进程，
每组约 8 秒后终止并保留已有输出。启动时会显示 `Turner Binder probe v2`。

## 实机证据

用户回传的 `turner-v335-logs.tar` 中：

- `turner-crypto.log` 确认补丁已在 recovery 加载、fstab 读取时修正已执行；
  `checkService` 为空后进入异步等待，但 `waitForService` 也返回 `0x0`。
- 状态文件确认实际加载的是 `twrp16/libbinder.so` 与 `twrp16/libbinder_ndk.so`。
  `/metadata`、persist 已挂载，元数据密钥目录存在，`/data` 没有挂载。
- `keystore.crash_count=0`；dmesg 中 keystore2 后续持续报告 `await_boot_completed`。
  这不能证明凭据/密钥 IPC 已成功，也不能据此把该线程当作解密根因。
- `service list` 工具不存在；本探针直接解析库函数并记录加载地址/路径。
- 迟取的 dmesg 从 uptime 2291.806 秒开始，缺少首轮解密；其中 logd 约每 5 秒
  因任务调度 profile 错误 abort、被 init 再拉起。下一轮诊断保留独立文件日志。
- `turner-setup.sh` 未找到 resetprop，对只读属性的 setprop 被拒绝，却仍打印
  `props aligned`。报告中的 release=17、sdk=35 不一致需要后续核验，不能把那条
  文本当作属性对齐成功的证据。本阶段不修改版本，先修服务查询。

**v3.35 启动/触控可用，但 data 解密失败；check→wait 不是已证实可行的修复。**

## 已核实的协议差异

对 v3.30/v3.35 保留的实际 ELF 反汇编：

| 库 | 方法 | Binder 事务号 |
|---|---|---:|
| 原厂 `system/lib64/libbinder.so` | `BpServiceManager::checkService` | 2 |
| payload `system/lib64/twrp16/libbinder.so` | `BpServiceManager::checkService` | 3 |
| 同一 payload 库 | `BpServiceManager::getService2` | 2 |
| 同一 payload 库 | `BpServiceManager::checkService2` | 4 |

servicemanager 的 rc 不设置 payload 库路径，使用原厂 libbinder；recovery 则明确
使用 twrp16 的库。AOSP Android 16 在接口中插入 getService2/checkService2，
新查询还要求 Service union/metadata 格式的回复。Android 15 的事务 2 返回裸
IBinder。因此“服务已注册，但新客户端两种 API 都空”有明确的协议不匹配解释；
仍需下列实机探针确认旧事务能否取得同一服务。

AOSP `CppBackendShim::waitForService` 也先调用 getService2；失败可立即返回空，
不会必然等到服务注册。这纠正此前把 waitForService 视为在本进程必然正常的假设。

## 探针的两条查询路径

每组记录真实 check/wait 函数的地址和来源；比较 keystore2、KeyMint、Gatekeeper
及 vibratorfeature 的返回结果。对照 recovery 的库对、HAL split 对和 stock 对。

旧协议路径使用当前库的 `ProcessState::self/getStrongProxyForHandle(0)` 取 context
manager，通过本库导出的 `AIBinder_fromPlatformBinder` 转为本库的 NDK Binder。
随后全部使用公开 NDK Parcel API：声明 android.os.IServiceManager 客户端 class、
写入接口 token 和服务名、发送事务 2、读取 Status 和 StrongBinder。未重新实现
Parcel 或混用另一个库的 AIBinder 对象。C++ sp 返回值通过 AArch64 x8 适配器接收，
不依赖对象字段偏移、vtable 槽、裸内存补丁或非公开函数地址。

适配器的实际 ARM64 指令有 Unicorn 寄存器测试；这不等于 Android Binder 实机通过。
只有在 recovery 库组里“modern=null，legacy rc=0 且 binder 非空”才确认此路径适合
下一版修复。返回非空还不是 data 解密成功，后续仍需验证实际密钥操作和挂载。

## 编译与运行

```sh
python3 -m pip install ziglang==0.17.1 pyelftools unicorn==2.1.4
mkdir -p build/stage49
python3 -m ziglang cc -target aarch64-linux-android -Os -ffreestanding \
  -fno-stack-protector -nostdlib -shared -fPIC -s -Wall -Wextra -Werror \
  -Wl,-z,max-page-size=4096 -Wl,-soname,libbinderprobe.so \
  hybrid/stage49/binder_probe.c -o build/stage49/libbinderprobe.so
python3 -m ziglang cc -target aarch64-linux-android -Os -ffreestanding \
  -fno-stack-protector -nostdlib -shared -fPIC -s -Wall -Wextra -Werror \
  -Wl,-z,max-page-size=4096 -DTURNER_BINDER_ABI_TEST \
  hybrid/stage49/binder_probe.c -o build/stage49/libbinderprobe-abi-test.so
python3 tests/stage49/test_arm64_sret.py \
  build/stage49/libbinderprobe.so build/stage49/libbinderprobe-abi-test.so
python3 hybrid/stage49/package_probe.py --library build/stage49/libbinderprobe.so \
  --output /absolute/output/turner-binder-probe.sh
```

把生成的脚本复制到平板 `/tmp/turner-binder-probe.sh`，在 rec 终端执行：

```sh
sh /tmp/turner-binder-probe.sh
```

保存并回传 `/tmp/turner-binder-probe-logs.tar`；重启前复制到 U 盘。

官方源码对照：
- [Android 15 IServiceManager.aidl](https://android.googlesource.com/platform/frameworks/native/+/android-15.0.0_r1/libs/binder/aidl/android/os/IServiceManager.aidl)
- [Android 16 IServiceManager.aidl](https://android.googlesource.com/platform/frameworks/native/+/android-16.0.0_r1/libs/binder/aidl/android/os/IServiceManager.aidl)
- [Android 16 IServiceManager.cpp](https://android.googlesource.com/platform/frameworks/native/+/android-16.0.0_r1/libs/binder/IServiceManager.cpp)
