# Hybrid v1 首刷失败 — 本地核查笔记（research run, 2026-11-14 17:33 CST）

## 失败事实（对话内）
- v1 镜像 `turner-vendor_boot-hybrid-v1.img`（67,108,864 B，sha256 `eb55c81b…48f9`），
  2026-11-14 17:29 CST 用户刷入，报告“不行，进不去”；17:31:48 CST “一直卡住不动”。
- 症状与 2026-11-11 的 v5iso 首刷完全一致：卡在 lk 花屏 logo、无 UI、无 ADB、无自动重启。
- 同一天早上 a7（Skyward）在同一台平板、同一 OS4 上成功进 recovery、触控完美。

## 本轮本地核查（全部实测于 ~/workspace/yarp-hybrid 与 ~/workspace/skyward-turner）

### 1. v1 缺少 early-adb —— 已实锤，v2 必补（照抄 a7 原文）
- a7 的三份 `init.recovery.*.rc`（hardware / mt6991 / mt8799）每份末尾都有同一段：
  ```
  # skyward: bring adb up even if the recovery service dies
  on boot
      setprop sys.usb.config adb
  ```
  外加 mkdir /data/vendor/* 六行 + `setprop vendor.teefs_state ready`。
- hybrid v1 的三份对应 rc 里**没有** `setprop sys.usb.config adb` 这一行；
  mkdir 那几行被搬进了 `hybrid-services.rc`，teefs_state 被搬进 turner-setup.sh。
- 后果：recovery 服务起不来时 v1 全程无 ADB，挂死等于零证据——与 v5iso 同款。
- v2 修复：把上面 a7 原文整段照抄进三份 rc（用户规则：有 a7 原件的优先用原件）。

### 2. plpath exec 已洗清 —— v2 保留，别动
- a7 的 mt8799/mt6991 rc 里保留 `on boot / exec u:r:update_engine:s0 root root -- /system/bin/mtk_plpath_utils`，
  且 a7 成功启动；v1 同样保留。plpath 不是挂点。
- v6-plpathtest（删这行）的思路至此作废，不必再试。

### 3. F0 删 system/bin/recovery 已洗清 —— v2 不必恢复（省 1.73 MB）
- OS4 原厂 F1 里**根本没有** `system/bin/recovery`；该二进制在原厂布局里只存在于 F0。
- hybrid F1 在同一路径放了 TWRP 的 recovery（3,270,200 B）；`service recovery`
  的定义只存在于 F0 的 `system/etc/init/hw/init.rc`（第 95 行），由同一份 init 解析。
- vendor_boot v4 的 fragments 由 bootloader 按序拼接成一份 ramdisk，
  后出的 cpio 覆盖先出的同名文件（stage1 的 merge gate 用的就是这个模型），
  所以 /system/bin/recovery 实际解析到 F1 的 TWRP 二进制，F0 那份删不删都不影响 exec。
- 结论：恢复它要花 1.73 MB 预算且修不了任何东西；v2 保持删除。

### 4. turner-setup.sh 不会卡住 boot —— 已洗清
- 有界等待：服务启动重试 30×1 s、设备节点等待 10×1 s、sleep 4 s + 5 s；
  以 oneshot 服务运行，不阻塞 init 的 trigger 处理。
- hybrid-services.rc 的三个 `on boot` 块只有 start/mkdir/chown，无阻塞 exec。

### 5. 首要嫌疑仍成立（与主会话 post-mortem 一致）
- v1 复用了 v5iso 的合并版 F1：TWRP 的 system/lib64 全套覆盖共享路径，
  init/hwservicemanager 等进程都吃到 TWRP 构建的库；libvintf 3 个未解析 Join
  与 v5iso 基线逐字相同。
- a7 的 F1 是原厂骨架 + 只换 system/bin/recovery（8.4 MB Skyward 二进制），
  其余库全部原厂——这是 a7 能进、v1/v5iso 不能进之间最大的结构差。
- v2 的真隔离方向（OS4 原厂 F1 骨架原样 + 只换 recovery 二进制 + 差异库全进
  twrp16 私有目录 + early-adb + kmsg 埋点）正确。

## v2 检查清单（供组装时逐项打勾）
- [ ] 三份 init.recovery.*.rc 追加 a7 early-adb 原文段（含 mkdir + teefs_state，或确认 hybrid-services.rc/turner-setup.sh 已覆盖后者）
- [ ] 保留 plpath exec；保留 F0 的两刀（res/ + recovery 本体）
- [ ] F1 从 OS4 原厂骨架起步，只换 system/bin/recovery 为 TWRP；所有与原厂不同的 TWRP 库进 twrp16 私有路径，system/lib64 保持原厂
- [ ] turner-setup.sh / hybrid-services.rc 保持有界等待；加 kmsg 埋点（init trigger 边界）
- [ ] 组装后重跑 5 道门 + 对比 a7 的 F1 文件清单做差分复核
- [ ] 首刷前确认：用户平板已恢复进系统（长按电源强制重启；进不去则 fastboot 刷回 /sdcard/zhui/zhuimeng/ 的追梦 OS4 vendor_boot），misc BCB 已清

## 备注
- v1 的远程下载链接（有效期至 2026-11-16 17:21 CST）随 v1 失败而作废，无需再传。
- 截至 17:33 CST，本地尚无 stage4 目录；MEMORY.md 已记 v2“building”。
