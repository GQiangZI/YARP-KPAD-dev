# Skyward-for-turner 重打包到 OS4 底座 — 可行性与方案

审计日期：2026-11-14。对象：酷安适配版 a7（OS3.0.306 底座）相对原厂的全部改动，
以及把同一套适配搬到 OS4 底座自制镜像的路径。

## 一、适配的完整配方（a7 vs 原厂 stock 逐文件 diff 已实证）

底座镜像（OS3.0.310 原厂，sha 0d92a8f1…）对照 a7：

- **DTB**：与原厂逐字节一致（sha 4f985cad…）。
- **F0（platform fragment）**：功能上零改动。278 处差异 = 274 个内核模块（306↔310
  内核重编漂移）+ prop 版本戳 + copylib.txt + 310 的 F0 多一个 res/ 目录。
  init 本体、init.rc 链、第一阶段全部原样。
- **F1（recovery fragment）**：先把原厂 recovery 的 userspace 几乎删空——
  res/（原厂 UI 图）、apex/config/linkerconfig、init、e2fsdroid、以及
  system/lib64 里除下列保留项外的全部库（libbase/libc++/libcrypto/libfs_mgr/
  liblp/libselinux/libsparse 等全删）。保留：boot/fastboot/health 三组 HAL 库、
  libbinder/libc/libhidlbase/libboot_control_client（均与原厂逐字节一致）、
  fastbootd + 其 rc 与 vintf 清单、recovery.fstab、fstab.emmc、sepolicy、
  property contexts、prop.default。
- **新增**：`system/bin/recovery` = Skyward 二进制（8.4 MB，Rust，源自上游
  v0.1.2）；`skyward/` 目录（device.toml + MiSansVF/KirkMono 字体 +
  libkmsglog.so）；`system/etc/init/skyward-mtp.rc`；`task_profiles.json`。
- **rc 改动**：仅在 init.recovery.mt8799.rc / mt6991.rc / hardware.rc 三个文件
  末尾追加同一段：on boot 拉起 adb、建 touch HAL 的 /data/vendor 目录、
  setprop vendor.teefs_state ready。原厂内容（含 mtk_plpath_utils 那行）未动。
- 镜像头/命令行为原厂值，按原厂方式组装 + AVB hash 页脚（Algorithm NONE）。

## 二、运行时机制（为什么能解密/能触控）

Skyward 本体不带解密与触控实现。开机后它按 device.toml 的 [[service]] 清单，
把**已安装系统** /vendor、/odm 里的原厂服务以逐个调校的库搜索路径拉起：
tee-supplicant（root，wait 后）→ keymint mitee（等 IKeyMintDevice 注册，
含 secureclock/sharedsecret 三接口全注册）→ gatekeeper mitee → 小米 touch
HAL（HTCP 模式，NT36536E 驱动模块自 vendor_dlkm 加载）。库路径的核心讲究：
触控 HAL 注册面对的是 ramdisk 里的 servicemanager，必须让 recovery 自带的
libbinder（RECO 标记）优先；TEE 链则用已安装系统的库（SYST）。a7 相对 b8 的
唯一修复：删掉 [[service]] 里的 vndservicemanager（在 turner 上 SIGABRT 循环，
且厂商服务实际注册在 /dev/binder 的 servicemanager 上）。

## 三、搬到 OS4 底座：能做，工作量与未知数

能复用的：整套配方（上）、a7 的 device.toml、二进制（复用现成 a7 二进制，
或从 ~/workspace/skyward-0.1.2 源码自编——需 Rust + NDK r29 + cargo-ndk）、
我们现成的 vendor_boot 组装器（assemble_v5iso.py 一系：F0/F1 手术、lz4
legacy、avbtool 页脚、校验套件）。

必须先审的 OS4 未知数（决定成败，按序）：

1. ~~OS4 的 vendor_boot 结构~~ **已审完（2026-11-14，官方 OTA OS4.0.3.0 抽取，
   vendor_boot sha 987a06d0…）：与 OS3 同构。** header v4、cmdline 相同、
   bootconfig=0、双 fragment；**DTB 与 OS3 逐字节一致**（533115 B，
   sha 4f985cad…）；F1 骨架同形（645 文件，sdk 仍报 35）；mt8799 rc 同形。
   **F1 的 libbinder.so 与 libc.so 与 OS3.0.306/310 逐字节一致**
   （libbinder sha c083e732…）——recovery 侧运行时世代未变。
2. OS4 已安装系统的服务布局：keymint 服务版本号与路径（mitee@3.0 是否还在）、
   gatekeeper、tee-supplicant、touch HAL 的 rc 与二进制路径是否与 toml 一致。
   **已审完（2026-11-14 10:47，详见 os4-service-audit-2026-11-14.md）：结论是
   toml 原样可用——keymint 仍是 @3.0，4 个服务二进制、5 份 VINTF 清单、3 份 rc、
   触控节点、vendor_dlkm 四模块、TA 目录全部在位且版本未变；SDK 仍 35。**
3. OS4 的 libbinder 世代标记：recovery 侧已证不变（见 1）；系统侧的 vendor
   服务二进制所用 libbinder 仍待 vendor 审完后比对。
4. ~~OS4 vendor_dlkm 触控模块名~~ **已确认**：nt36536e_touch_turner.ko 在
   （另有 xiaomi_touch_turner.ko、touch_boost.ko），与 toml 的 load 名一致。

输入材料（缺一不可）：
- OS4 vendor_boot.img：追梦包内那份（用户手机 /sdcard/zhui/zhuimeng/ 里），
  或官方 OS4 OTA 抽取。
- OS4 的 vendor/odm 镜像（审服务布局用）：追梦包 super 或官方 OTA 均可抽。

## 四、验证门（出镜像前）

1. F0 与 OS4 原厂逐字节一致（只许 F1 变化）。
2. F1 的保留库逐个对 OS4 原厂校验来源。
3. toml 里每个 [[service]] 路径在 OS4 vendor/odm 中真实存在。
4. 组装后 header/DTB/表偏移与 OS4 原厂一致，64 MiB，AVB 页脚复算通过。
5. 首刷纪律：白天、追梦 OS4 vendor_boot 在手边可救砖、先清 BCB。

## 五、与 YARP/TWRP 线的关系

- 打包层：YARP 项目的组装器、校验、设备知识直接复用——这就是「基于 YARP 搞」。
- 本体层：把 Skyward 的「借系统服务」解密机制移植进 TWRP 不现实：TWRP 的加密
  栈按自带 HAL 模型写，且我们已实证把 TWRP userspace 并进原厂 ramdisk 会与
  原厂 init 冲突（符号配对、SetupCgroups 崩、挂 logo）。Skyward 绕开的正是这点。

## 六、用户 2026-11-14 04:31 提供的参考仓库（已核）

- echoskies-works/skyward-extra：Skyward 的桌面化分支（默认界面是桌面，
  能看书/听歌/玩游戏，基于 v0.2.0），设备名单与上游相同，**无 turner**，
  与 turner 适配无关；仅证明 Skyward 代码可分支魔改 UI。
- kirklin 本人仓库：skyward 本体 + unpayload（他自己的 payload 抽取工具，
  Rust；我们已有自研抽取脚本且已实证，可互为校验）。
- TWRP-Test（YARP 本体）：UI/GUI2 源码在 android_bootable_recovery，
  构建清单 platform_manifest_twrp_aosp twrp-16.0——我们的 turner 树正是
  基于它构建，v1–v5 产物（f1_v4 树）已含该 UI（twres），拼接时直接复用。
- YuKongA/twrp_device_xiaomi_sm8850（YARP 树）：其 nezha Weaver 选择机制
  （weaver-vendor.sh 在运行时读已装 ROM 的 odm 配置来决定起哪个安全单元
  实现）是 YARP 树内「运行时借用/选择已装系统组件」的现成先例，支持本案
  的服务编排设计。

## 七、piano（Xiaomi Pad 8 Pro）YARP 树参考（2026-11-14，用户提供，已拉到 ~/workspace/piano-tree）

- 机型事实：11.2" 3200×2136（3:2）**横向原生**面板，SM8750；官方规格已核。
- BoardConfig 实证：TW_THEME := landscape_hdpi；触控变换
  RECOVERY_TOUCHSCREEN_SWAP_XY := true、RECOVERY_TOUCHSCREEN_FLIP_Y := true；
  TW_LOAD_VENDOR_MODULES := "xiaomi_touch.ko nt36532_touch.ko adsp_loader_dlkm.ko"
  ——触控模块从**已装系统的 vendor_dlkm** 加载（NT36532 是 turner NT36536E 的同族）。
- piano-setup.sh（recovery/root/system/bin/）：开机只读挂载已装 ROM 的
  vendor/odm/system → 以 odm 是否含 libmi_weaver.so 区分 HyperOS 3/4 安全栈
  → 把对应世代的 Weaver/ssgtzd/batterysecret 及库从 /variant 覆盖到公共文件
  → 在 KeyMint 启动前 resetprop 写入从已装 ROM 读到的真实 OS 版本与补丁级别
  （构建期兜底值故意取旧，宁可解密失败也不升级 ROM 的密钥）→ 带重试地拉起服务。
  其 README 称 HyperOS 4 下触控、PIN 解密已实测。
- 对 turner 的适用性：面板 1880×3008 **竖向原生**，主题不能照抄 landscape_hdpi，
  首版沿用竖向主题，SWAP/FLIP 留作首刷后按现象调的旋钮；可直接借的是
  TW_LOAD_VENDOR_MODULES 机制（对应 nt36536e_touch_turner.ko）与 setup 脚本的
  「读已装 ROM 参数再起安全栈」模式——与 Skyward 的服务编排互补：
  编排参数以 a7 的 toml 为准（turner 真机已验证），流程骨架参考 piano-setup.sh。

## 八、用户定的取材规矩（2026-11-14）

拼接时凡 a7/b8 镜像中已有的文件，优先用从镜像提取的原件（已在 KPad 真机
验证过的字节）：device.toml、rc 追加段、skyward-mtp.rc、字体、libkmsglog.so、
task_profiles.json 等适配者文件一律取提取件；原厂骨架仍以 OS4 原厂为底
（关键库已证与镜像内副本逐字节相同，无冲突时两规矩自动一致）。
