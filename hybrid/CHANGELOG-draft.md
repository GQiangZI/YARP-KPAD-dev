# turner 混合版更新日志素材（持续维护，最终定稿用）

维护规则：每出一版、每验证一个功能，就在这里更新。状态分三种：✅ 已验证 / 🧪 已加入待验证 / ❌ 不支持（附原因）。

## 功能总览

- ✅ 显示：YARP/TWRP GUI2 界面正常显示（v2.2 起，minui DRM legacy_modeset 补丁）
- ✅ 触摸：完整可用（v3.12 起，触控驱动 + 小米 touchfeature HAL + THP 守护链）
- ✅ USB OTG / U 盘：可读写，可导出日志（2026-11-16 验证）
- ✅ 安全服务链：KeyMint / Gatekeeper / tee-supplicant 正常注册并存活（v3.9 注册、v3.10 存活）
- ✅ 开机画面机型名显示 REDMI K Pad（v2.7 起）
- ✅ 内置终端：Advanced → Terminal，root 权限（载荷自带）
- 🧪 数据解密：keystore2 段错误已除（v3.25）；新卡点已定位——keystore2 查「VINTF 声明实例」在本环境恒空，被迫走老 HIDL 兼容死路 panic 循环；v3.26 用声明实例桩把它扳回 AIDL 正道，待实机验证（见版本记录）
- 🧪 adb root：v3.22 起烘焙 ro.debuggable=1，待刷机验证 `adb shell id`
- 🧪 镜像刷入新增分区：Vendor Boot（刷入+备份）、Init Boot（v3.23 起，待验证）；无 recovery 分区（本机无此分区，vendor_boot 为唯一 recovery 通道）
- 🧪 链分区防护：刷机包禁止写 lk / preloader / preloader_raw 等启动链分区（v3.23 起，by-name 路径重定向到临时假文件，保护 LK 漏洞解锁）
- ✅ 振动反馈：**v3.25 实机确认有振动**。路线：载荷 vibrate()（libtwrpminui.so）走 AIDL 振动 HAL `IVibrator/vibratorfeature`；v3.24 拉起 odm 的 vibratorfeature 服务 + 补 vintf 片段（注册成功），v3.25 补上缺失的 AW8693x 执行器驱动模块（打包自 OS4 vendor_dlkm，setup 点火前 insmod）后打通。（注：Skyward 程序有振动模块，但 turner 适配未配置 [haptics]，在 turner 上同样不振）
- ⏳ WiFi：未做（用户排期：解密 → OTG ✅ → WiFi）
- ⚠️ 与上游差异：当前载荷（官方 YARP 4.0.0 sm8750 镜像，2026-10-26 构建）**不含 PR #42**（GUI2 存储热插拔刷新，2026-11-06 才合并；二进制内 storage_task / RefreshPartitionListSnapshots 两个标记均缺失，2026-11-17 核实）。基础 OTG 挂载不受影响；要拿到它只能等官方新版载荷发布后重新拼接。
- ⏳ 开机速度优化：**已提级进 v3.24**（2026-11-17 用户：等待 10 秒甚至更久，"作为一个优秀的作品，不应该这么失败"）。方案：setup 改事件驱动并行——所有 supervisor（TEE 对、触控、振动）背靠背同时启动，单一轮询环统一验活、就绪即退（替代串行 grace 叠加）；keystore2 由 keymint 注册轮询触发。目标总时长 5–6 秒，以 dmesg 时间戳（setup 起止）实测为准；preloader/lk + F0 stock 模块加载那段约 3–4 秒动不了，已如实告知。

## 待核查（2026-11-17 用户转论坛帖追加）
- U 盘文件名编码：论坛有人报 YARP 文件管理器里西里尔字母文件名显示为「?????」（字体覆盖问题）。**已核查（v3.24 实机）：中文文件名显示正常**（照片实锤「启动快」）。
- OTG 挂载条目：**已定案（v3.24 实机+日志）**：twrp.flags 的 /usb-otg 条目建出来了（分区表里有，Is_Storage），但 U 盘被 recovery.fstab 里原厂的 `voldmanaged=` 行（5 条 usb + 1 条 mmc）抢先认领到 /auto4-sdd-1，/usb-otg 成了空文件夹——与论坛吐槽同病。**v3.26 已改**：删光全部 voldmanaged 行（taiko 同款清理），让 /usb-otg 独占认领，待实机验证。
- Install Image 缺 Vendor Boot（v3.24 实机发现）：**先前「原厂条目盖住追加条目」的定案是错的，特此更正**——fstab 里只有一条 vendor_boot 且带 flashimg=1，日志里它的 Flags 却没有 Can_Flash_Img。真因推定：TWRP 处理完 recovery.fstab 后又合并已安装系统的 /vendor/etc/fstab.mt8799，里面自带一条无标志的 vendor_boot，把我们的标志冲掉了（Init Boot 不在那份 fstab 里，所以没被冲）。**v3.26 试探解法**：加一条 `/vendor_boot_img` 别名条目（同一 by-name 设备，display=Vendor Boot + backup + flashimg）——系统 fstab 里没有这个挂载点，冲不掉，待实机验证。

## 版本变更

- v1（2026-11-14）：首版拼接，卡开机画面（F0 无罪，后定位为 GUI2 DRM 门槛）
- v2.2：二进制补丁 libtwrpminui.so 强制 legacy_modeset —— 首次点亮 TWRP 界面（里程碑：显示）
- v2.4：触控模块加载器重写（依赖路径修复），触控驱动层打通（面板注册 1880×3008）
- v2.7：开机画面机型名改为 REDMI K Pad
- v3.5：xiaomi_touch 驱动模块打包进 recovery（不再依赖系统分区提取）
- v3.6：servicemanager VINTF 校验补丁（1 处 NOP），health 服务首次注册成功
- v3.9：HAL 注册全通（拆分 binder 对 + Accessor/trace 桩 + SM 补丁 + 干净 VINTF 清单）
- v3.10：HAL 改常驻服务，存活问题解决；setup 串行等待并行化（提速第一步）
- v3.12：触摸节点权限补齐 —— **触摸可用**（里程碑）
- 2026-11-16：U 盘/OTG 验证可用（里程碑）
- v3.13：KeyMint/Gatekeeper 改监督进程常驻；定位解密缺失层为 keystore2
- v3.14–v3.15：加入 keystore2；挂载 i18n APEX 补齐 ICU 依赖
- v3.16：liblogcapture v5 补 BBinder 桩，keystore2 首次连通 KeyMint（版本 300）
- v3.17：挂载 tracefs（排除 atrace 因素）
- v3.18：keystore2 换官方 YARP 构建自带二进制+完整库闭包（仍崩溃，排除二进制因素）
- v3.19：keystore2 改 init 服务（仍崩溃，排除启动方式与 memlock 因素）
- v3.20：加入崩溃回溯库 libfaultlog v1（信号结构与 bionic 不匹配，未生效）
- v3.21：libfaultlog v2（signal() 注册 + 装上自证标记）
- v3.22：ro.debuggable=1（adb root 尝试，用户批准）
- v3.23：镜像刷入新增 Vendor Boot / Init Boot；链分区刷包防护（lk/preloader 拦截）
- v3.24（stage40，sha `641c2ada…`，2026-11-17 07:13 CST 打好，64 MiB）：v3.23 全量 + 并行/事件驱动 setup（各 supervisor 背靠背启动、单一轮询环验活、keystore2 由 keymint 注册轮询触发，目标 5–6 秒）+ 振动 HAL supervisor 与 vintf 片段（8.0）+ persist 守卫（新增 haptics 目录；TEE 启动前复检挂载，防 TWRP 早期扫描卸载的竞态重挂）+ twrp.flags 定死 /usb-otg（显示 USB-OTG）。v3.23 待验项（adb root、FAULTLOG 回溯）由本版一并收。未进本版：版本号 99 大法（等 keystore2 活过来后才用）、WiFi、PR #42。**刷机验证（2026-11-17，平板 ✓）**：触摸 ✅；并行点火生效（readiness 0 ticks、内核 5.99 秒全员就绪）**但 setup 收尾拖到 9.57 秒**——keystore2 双重点火（等待器+内联各一次）+ sleep 3 验活吃了约 3.5 秒，体感比 v3.12 更慢（半死的 keystore2 让解密尝试干等，不如没有时失败得干脆）；**FAULTLOG 定案：keystore2 崩在 libhidlbase 的 getAllHalInstanceNames（找 hwservicemanager 枚举 HIDL，本机根本没有）**；振动 HAL 注册成功（SM 在清单中找到 vibratorfeature）但无振动——执行器节点 /sys/class/leds/vibrator 不存在（AW8693x 驱动模块没人加载）；adb root 未被拒绝（debuggable 生效，adbd 接受重启，是 USB 重枚举老毛病，kill-server+重插恢复）；U 盘仍是 /auto4-sdd-1（twrp.flags 改名未生效）；**中文文件名显示正常**；Install Image 列表有 Init Boot。
- v3.25（stage41，sha `951f61d0…`，2026-11-17）：liblogcapture v6 加 getAllHalInstanceNames 桩（返回空列表——本机无 HIDL HAL，是真话）；keystore2 点火去重 + 验活 sleep 3→1（砍收尾拖尾）；打包 OS4 vendor_dlkm 的 aw8693x_vibrator.ko，setup 在点火振动前 insmod + 振动节点权限放宽到 activate/duration/state。校验：F0 与 v3.24 零差异；F1 差异恰为 {turner-setup.sh, turner-vibrator-sup.sh, liblogcapture.so} + 新增 aw8693x_vibrator.ko；AVB 通过。**刷机验证（2026-11-17，平板 ✓）**：**振动 ✅**（用户实测）；**keystore2 段错误消失**（FAULTLOG 零 fatal，v6 桩生效，共享密钥协商成功）**但仍未存活**：错误链定案——它向 servicemanager 查「VINTF 声明实例」恒为空（清单里明明有 IKeyMintDevice/default，SM 自己日志实锤），于是判定「没有正牌 KeyMint」，转走老 HIDL keymaster 兼容服务（android.security.compat，本机不存在）→ NAME_NOT_FOUND → panic，监督进程每 ~8 秒拉起重来（34 次）；metadata 仍解不开，解密页仍是密码页。
- v3.26（stage42，sha `68aa294a…`，2026-11-17）：liblogcapture v7 加声明实例桩——`AServiceManager_forEachDeclaredInstance`/`isDeclared`/`getDeclaredInstances` 对 keymint/secureclock/sharedsecret/RPC 四个 mitee 接口按事实回答 `default`（其余接口转发真实现），把 keystore2 扳回 AIDL 正道；recovery.fstab 删光全部 `voldmanaged=` 行让 /usb-otg 独占认领 U 盘；新增 `/vendor_boot_img` 别名条目试探恢复 Install Image 里的 Vendor Boot。校验：F0 与 v3.25 零差异；F1 差异恰为 {liblogcapture.so, recovery.fstab}；AVB 通过。**刷机验证（2026-11-17，平板 ✓）**：声明桩生效——keystore2 改走正道（错误链变 `globals.rs:245 Trying to connect to genuine KeyMint service`），**但 getService 查 IKeyMintDevice/default 恒 NAME_NOT_FOUND**：keymint 进程本体活着（开机 pid 561 未换、单次点火），振动正常（同一套查服务机制能找到 vibratorfeature）→ 注册表没坏，卡点收窄到「载荷版 keystore2 查 mitee 服务」这一条路；**OTG 回退 ❌**：删 voldmanaged 后 U 盘干脆不挂载（twrp.flags 条目在本载荷上认领不了盘）；**别名 ❌** 未出现在镜像刷入列表。
- v3.27（stage43，sha `c985dba0…`，2026-11-17）：**keystore2 换回已安装系统的原版**（v3.14/v3.16 配方：/mnt/system/system/bin/keystore2 + twrpbinder→系统库→APEX→twrp16）——它是唯一真连上过 mitee KeyMint 的 keystore2（v3.16「current version (Some(300))」），它的两个历史死因（BBinder 符号、getAllHalInstanceNames 段错误）都已被 liblogcapture v5/v6 桩覆盖，v7 桩保留；recovery.fstab **原样恢复 v3.25**（撤销 v3.26 的 OTG/别名两个失败实验，U 盘回到可用的 /auto 挂载）。校验：F0 与 v3.26 零差异；F1 差异恰为 {turner-ks2-sup.sh, recovery.fstab}，且 fstab 与 v3.25 逐字节相同；AVB 通过。**刷机验证（2026-11-17，平板 ✓）：keystore2 链路全通**——开机 7.6 秒连上 KeyMint（current version (Some(300))）、注册 IKeystoreService、共享密钥协商成功、单次点火零崩溃；U 盘恢复挂载（/auto4-sdd-1）；**但 metadata 解密仍失败、仍是密码页**，且解密尝试全程 KeyMint 零流量。
- **解密真根因（2026-11-17 午间定位）**：读 TWRP-Test/android_system_vold 源码（MetadataCrypt.cpp）确认——原厂 vendor fstab 的 /data 行**没有 `metadata_encryption=` 声明**，vold 的 v2 解析路径拿空字符串当加密算法名，查表失败后**在调 keystore2 之前就直接退出**。这解释了 v3.13 以来每一版的「零流量」：keystore2 链路其实早已修好，vold 根本没走到它。metadata 钥匙文件本身完整（Terminal 实查：version=1、encrypted_key、keymaster_key_blob、secdiscardable 全在）。**手动验证**：在 v3.27 活会话里用 sed 给 /etc/additional.fstab 的 /data 行尾加 `,metadata_encryption=aes-256-xts` 成功落盘（TWRP 每次解密都重读这份拷贝）；但 GUI 提交密码不重跑 metadata（开机一次性），`ctl.restart recovery` 又只换来黑屏（已重启恢复）——最终验证留给 v3.28 的开机自动补丁。
- v3.28（stage44，sha `adc1ed2d…`，2026-11-17）：turner-setup.sh 新增 `patch_additional_fstab`——开机时（挂载后 + step:done 前各一次）给 /etc/additional.fstab 的 /data 行补 `metadata_encryption=aes-256-xts`，日志打 `additional fstab: metadata_encryption=aes-256-xts added to /data`。其余与 v3.27 完全一致。校验：F0 零差异；F1 差异恰为 {turner-setup.sh}；AVB 通过。**刷机验证（2026-11-17，平板 ✓）**：补丁按时落地（日志两行齐全），解密尝试用上了新 fstab，**但仍失败、仍无 KeyMint 流量**——解析关过了，倒在下一关。
- **第二关定位（2026-11-17 午间，活体探针实证）**：从官方 YARP 镜像提取其自带 `keystore_cli_v2`（与 vold 同辈的客户端，报错直接上屏）在 v3.28 活会话里跑 `list`，秒回 **`Unable to connect to Keystore.`**——它的源码路径是 `AServiceManager_checkService(IKeystoreService/default)` 返回空。keystore2 明明注册成功（SM 日志全程只有一句「Could not find android.system.keystore2.IKeystoreService/default in the VINTF manifest」）——**F1 缺 keystore2 的 VINTF 声明片段**，未声明的服务对客户查询不可见；而已声明的 keymint、vibratorfeature 都能正常查到，与此完全吻合。
- v3.29（stage45，sha `972a77b5…`，2026-11-17）：F1 新增 `system/etc/vintf/manifest/android.system.keystore2-service.xml`，逐字节取自官方镜像。**刷机验证（2026-11-17，平板 ✓）：失败且自伤**——dmesg 实锤：`Unrecognized manifest.version 9.0 (libvintf@8.0)` → 整个 recovery manifest 变 NULL。**教训：官方片段是 9.0，我们的 libvintf 只认 8.0；搬文件必须对齐版本号**（taiko 的版本毒药在我们这儿以另一种形式重演）。
- v3.30（stage46，sha `aa0606d8…`，2026-11-17）：同一片段，仅把 `version="9.0" type="framework"` 改为 `version="8.0" type="device"`，与 F1 其余七个片段完全同格式，声明内容不变。其余与 v3.29 完全一致。校验：F0 零差异；F1 仅该文件变化；AVB 通过。待验证：manifest 正常解析→IKeystoreService 可见→metadata 解开→图案页。
- **探针结论（2026-11-17 13:19，NDK 探针 libprobe.so 活体实测）**：在 payload 库环境的进程里，`AServiceManager_isDeclared` 对 keystore2/keymint/vibrator 三个服务全返回 1（声明可见），但 `AServiceManager_checkService` **对三个服务全返回 null**——包括明明能用的 vibratorfeature 和 keystore2 自己能连上的 keymint。即：**payload 世代的 NDK 查找路径在本机整体失效，与 keystore2 无关**；此前 keystore_cli_v2 的 "Unable to connect" 不能证明 vold 那一跳坏了。已装系统的 keystore2（SDK37 客户端库）查找 keymint 正常。差异焦点收窄为：客户端库世代 × 原厂（SDK35 世代）servicemanager 的互操作。
