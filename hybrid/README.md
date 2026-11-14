# Hybrid YARP/Skyward for turner（红米 K Pad）

把 YARP（TWRP 16 / GUI2）的界面与功能，拼到 Skyward 在本机验证过的硬件通路上：
OS4 原厂 vendor_boot 为底（F0/DTB 不动），F1 放 TWRP 用户态并做严格库隔离，
解密/触控所需的 HAL 全部从已装系统在运行时拉起（沿用 Skyward a7 镜像的 device.toml 编排）。

目标机：turner（MT6991 / ro.hardware = mt8799），面板 1880×3008，触控 Novatek NT36536E。
当前系统基线：HyperOS OS4.0.3.0。

## 当前状态（2026-11-15）

| 项目 | 状态 |
|---|---|
| 显示（GUI2） | ✅ v2.2 打通：libtwrpminui.so 5 字节补丁强制 legacy modeset，绕过高通 SDE plane 门（见 stage5/DRM-RESEARCH.md） |
| 触控 | ❌ 进行中：v2.3 死于 modules.dep 绝对路径双拼 bug；v2.4 已改 basename 闭包加载，等实机日志定论（stage9/NOTE.md） |
| HAL 注册 | ❌ 进行中：keymint/gatekeeper 在 v2.3 死于向 servicemanager 注册 AIDL 时的 libbase CHECK abort；v2.4 用单符号桩（见下）+ a7 库序验证中 |
| 数据解密 | ⏳ 未测：从未输入过真实 PIN（此前日志里的 Decrypt 失败是 TWRP 的默认密码自动尝试 + 元数据解密失败）。turner 凭据链 = Gatekeeper + KeyMint@mitee，无 Weaver、无 eSE（decrypt-stack/FINDINGS.md） |
| OTG / WiFi | ⏳ 按计划后置 |

## 构建史

| 版本 | 结果 | SHA256（前 8 位） |
|---|---|---|
| v1（stage3b） | ❌ 卡 logo：未真正落实严格隔离，合并 F1 的老病带入 | eb55c81b |
| v2（stage4） | ⚠️ 尺寸超限未出图；查明 OS4 原厂无 hwservicemanager | — |
| v2.1（stage4b） | ❌ 卡 logo，但 adb 可达，拿到 recovery.log 定位到 DRM plane 门 | f33623cb |
| v2.2（stage6） | 🎉 首次点亮 YARP 界面（显示完成） | 7adf15f1 |
| v2.3（stage7） | 显示正常；触控/HAL 仍崩，日志定位到 modules.dep 路径 bug + 注册 abort | 331ce6f3 |
| v2.4（stage8） | **当前版**：闭包加载修复 + HAL 并行启动 + binder 桩；2026-11-14 19:41 刷入，触控仍不行，日志待读 | 554cac23 |

镜像本体（64 MB）与 .so 二进制不入 git；构建/校验脚本与全部分析文档在此。

## 关键结论

- **DRM plane 门**：GUI2 的 minui DRM 后端是高通 SDE 移植，只认带专有
  `capabilities` 属性的 plane，联发科 plane 永远 0/2 —— 这是 v1–v5 全部「卡 logo」的总根源。
- **符号普查**：装机系统（SDK 37 代）与 ramdisk（SDK 35 代）两代 binder 库之间，
  rkp 链实际只缺一个符号 `AIBinder_Class_setTransactionCodeToFunctionNameMap`；
  v2.4 以一个 4 KB 手工 ELF 桩（仅导出该符号、实现为 no-op ret）补齐，
  使 HAL 可以回到 a7 的 ramdisk 优先库序。（桩的构建脚本待补回本目录。）
- **modules.dep 闭包**：vendor_dlkm 的 modules.dep 用绝对路径写依赖，
  加载器必须按 basename 解析并先挂规范路径 /vendor_dlkm；toybox modprobe 同样中招。
- **Skyward a7/b8 差异**：仅 device.toml 与 recovery 本体两处；b8 多起的
  vndservicemanager 在 turner 上会 SIGABRT 循环，a7 是调试后的定版（skyward-analysis/）。
- **OS4 服务布局审计**：a7 的 toml 在 OS4 上原样可用；OS3→OS4 凭据链组成零差异。

## 目录

- `stage1/` 载荷回收与 OS4 切分报告
- `stage2/` 混合编排设计
- `stage3/`、`stage4/` v1/v2 构建校验记录（含尺寸超限与 F0 裁剪分析 `f0trim/`）
- `stage5/` DRM 根源研究（stage6 的 5 字节补丁依据）
- `stage6/` v2.2 构建/校验/补丁审计脚本
- `stage7/` v2.3 构建/校验脚本 + v2.2 取证（DIAG-V22-FORENSICS）
- `stage8/` v2.4 构建/校验脚本 + turner-setup.sh + hybrid-services.rc（当前版）
- `stage9/` v2.4 刷后诊断准备（两条分支的判读表）
- `decrypt-stack/` turner 凭据链全量盘点
- `skyward-analysis/` Skyward 适配全解 + OS4 服务布局审计
