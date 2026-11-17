# Hybrid YARP/Skyward for turner（红米 K Pad）

把 YARP（TWRP 16 / GUI2）的界面与功能，拼到 Skyward 在本机验证过的硬件通路上：
OS4 原厂 vendor_boot 为底（F0/DTB 不动），F1 放 TWRP 用户态并做严格库隔离，
解密/触控所需的 HAL 全部从已装系统在运行时拉起（沿用 Skyward a7 镜像的 device.toml 编排）。

目标机：turner（MT6991 / ro.hardware = mt8799），面板 1880×3008，触控 Novatek NT36536E。
**当前系统基线：HyperOS OS4.0.3.0 正式版**（平板已于 2026-11-12 升 OS4 正式版，BL 漏洞解锁保留至今）。
注：`skyward-analysis/` 里的 a7/b8 参考镜像是 OS3.0.306 时代的产物，仅作编排参考；
其 device.toml 编排已审计确认在 OS4 上原样可用（见 os4-service-audit）。

## 当前状态（2026-11-17，v3.31）

| 项目 | 状态 |
|---|---|
| 显示（GUI2） | ✅ v2.2 打通：libtwrpminui.so 5 字节补丁强制 legacy modeset，绕过高通 SDE plane 门（stage5/DRM-RESEARCH.md） |
| 触控 | ✅ v3.12：THP 链卡在 /sys/class/touch/touch_dev/abnormal_event 属主（root:root 而 HAL 以 system 运行），stage_touch_owners 全量 chown 后打通 |
| HAL 注册/存活 | ✅ v3.9 注册墙破（servicemanager VINTF 检查 NOP 补丁 + 拆分 binder 对 SDK35 libbinder.so / SDK36 libbinder_ndk.so + liblogcapture Accessor 桩）；v3.10 改监管进程常驻，不再被 oneshot 退出连带 SIGKILL |
| OTG / U 盘 | ✅ 2026-11-16 实测挂载（/auto4-sdd-1）；改名 USB-OTG 尝试已回滚（v3.26 教训，见 CHANGELOG） |
| 振动 | ✅ v3.25：补载 OS4 vendor_dlkm 的 aw8693x_vibrator.ko 后 vibratorfeature HAL 出振 |
| keystore2 链路 | ✅ v3.27：装机 keystore2 与 mitee KeyMint 完成握手（current version 300）、注册 IKeystoreService、共享密钥协商成功，零崩溃 |
| 数据解密 | ❌ 进行中：已修两处——原厂 fstab /data 行缺 metadata_encryption=（v3.28 setup 补丁）、keystore2 VINTF 声明版本对齐（v3.30）。当前卡点经探针实证：vold 用 NDK `AServiceManager_checkService` 轮询 keystore2（300×100ms），而该 API 在本 recovery 中对全部服务返回 null（含可用的 vibratorfeature），waitForService 正常——修复方向为 checkService→waitForService 转发垫片 |
| WiFi | ⏳ 未做（计划顺序：解密 → OTG ✅ → WiFi） |

版本变更明细见 `CHANGELOG-draft.md`；解密栈审计见 `decrypt-stack/FINDINGS.md`。

## 构建史（要点）

| 版本 | 结果 |
|---|---|
| v1–v2.1 | ❌ 卡 logo（GUI2 DRM plane 门，见 stage5 研究） |
| v2.2 | 🎉 首次点亮 YARP 界面，显示完成 |
| v2.3–v2.9 | HAL 注册诸战：库序翻转、版本化桩证伪、modules.dep 绝对路径 bug 修复（触控驱动层 v2.4 通） |
| v3.0–v3.5 | ld.config 命名空间、twrpbinder 拆分对、清单毒化教训 |
| v3.6 | servicemanager 4 字节 NOP 补丁（F0 唯一改动点），health 注册通 |
| v3.9 / v3.10 | 注册墙破 / 监管进程保活，HAL 全部注册并存活 |
| v3.12 | 触控打通 |
| v3.13–v3.23 | keystore2 引入与诸版排障（ICU/APEX、段错误定位到 getAllHalInstanceNames 空解引用，v6 桩修复）；并行启动重构、启动链守卫（拦截 lk/preloader 刷入） |
| v3.24 | 并行事件驱动启动（就绪 5.99s）+ 振动 HAL 接入 |
| v3.25 | 振动 ✅；keystore2 声明实例桩（v7），改走真 AIDL 路径 |
| v3.27 | keystore2 链路全通（换回装机 keystore2） |
| v3.28 / v3.30 | fstab metadata_encryption 补丁 / keystore2 VINTF 声明 8.0 对齐 |
| v3.31 | **当前版**：诊断版，内置 keystore_cli_v2 + NDK 探针（kscli），定位 checkService 失效 |

镜像本体（64 MB）与 .so 二进制不入 git；构建/校验脚本、运行时脚本与全部分析文档在此。
stage10 起每代目录含该版构建脚本（buildN.py）与当时的运行时脚本快照。

## 关键结论

- **DRM plane 门**：GUI2 的 minui DRM 后端是高通 SDE 移植，只认带专有
  `capabilities` 属性的 plane，联发科 plane 永远 0/2 —— 这是 v1–v5 全部「卡 logo」的总根源。
- **注册三件套**：SM 的 VINTF 声明检查 NOP（F0 @0x9d04）+ 无重复的有效清单 +
  拆分 binder 对 + liblogcapture 的 Accessor/trace 桩，缺一不可。
- **监管进程模式**：init oneshot 退出会连带 SIGKILL 其拉起的子进程；
  HAL 必须由永不退出的监管脚本 spawn（Skyward 的监督进程同理）。
- **NDK 查找分化**：本 recovery 中 AServiceManager_checkService/getService 对全部服务
  返回 null，waitForService 正常；vold 的解密轮询恰好用 checkService。
