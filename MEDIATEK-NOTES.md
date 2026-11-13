# 联发科（天玑）适配问题记录

本文件记录为红米 K Pad（`turner`，天玑 9400+ / MT6991）从零适配 TWRP 时
实际遇到、并逐项验证过的问题。所用官方固件：OS3.0.310.0.WAOCNXM。
最后更新：2026-11-10。

## 1. 直出的 vendor_boot 进不了 recovery，必须以原厂镜像为模板重打包

twrp-14.1 底子和 YARP 底子直出的镜像共 5 个版本，刷入后全部黑屏或
logo 循环。参考的三个联发科项目（dash / MT6991Z、warhol / MT6993、
chagall / MT6899）无一例外都是「先编译、再把产物重打包进原厂
vendor_boot 模板」，没有直刷编译产物的。

可行路线：内核、DTB、镜像头、第一阶段 ramdisk 全部保留原厂，
只替换 recovery 部分。

## 2. ramdisk 压缩必须用 lz4，zstd 全部失败

原厂两个 ramdisk 片段都是 lz4 legacy 格式。内核配置里虽然有
`CONFIG_RD_ZSTD=y`，但所有 zstd 压缩的镜像都启动失败。
本仓库原有的 zstd 压缩补丁已经删除，统一用 lz4。

## 3. AVB 不是门槛，别在签名上浪费时间

无 AVB 页脚、仅哈希页脚（Algorithm NONE）、RSA4096 完整签名三种
都试过，失败方式完全一致；原厂镜像本身就是仅哈希页脚。
启动失败和 AVB 无关。

## 4. ro.hardware 是 mt8799，不是 mt6991

init 按 `${ro.hardware}` 导入 `/init.recovery.mt8799.rc`，
mt6991 只是平台的营销名。把启动脚本的改动（例如触摸开关）写进
`init.recovery.mt6991.rc` 永远不会被执行。这一点由原厂 recovery
的 ramoops 日志确认（init 实际处理的是 mt8799 的 rc）。

## 5. 触摸驱动编进内核，没有.ko 可加载

整个镜像里找不到触摸的.ko（同平台 OrangeFox rothko 也是 0 个）。
小米的触摸走用户态 THP 原始帧处理，recovery 里没有对应守护进程，
需要在 mt8799 rc 的 `on boot` 里写：

```
write /sys/class/touch/touch_dev/enable_touch_raw 0
```

切回内核输入事件模式。

## 6. 有一个 31 秒的看门狗

原厂日志确认 `mtk-wdt` 超时 31 秒（nowayout=0）：进入 recovery 后
31 秒内没有喂狗就会被硬复位。排查时要区分「真的崩了」和
「看门狗超时」，两者的日志尾巴长得不一样。

## 7. misc 分区的 BCB 不清，平板会每次开机直进原厂 recovery

刷机失败后，如果 misc 里 BCB 的 boot-recovery 指令没被清掉，
每次开机都会直进原厂 recovery，而且之后拉到的 ramoops 全是
原厂会话的记录，不是失败那一次的。清法（二选一）：

```sh
adb shell su -c "dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1"
fastboot erase misc
```

抓失败启动的日志之前必须先清 BCB，并让平板直接冷启动进系统。

## 8.重打包合并时必须做符号级配对审计

合并顺序是：平台片段在前、recovery 片段覆盖在后，**同名文件后者胜**。
模板里的原厂 init 被保留下来，但它依赖的同名库会被 TWRP 的
API 36 版本静默覆盖。只查 DT_NEEDED 闭合（文件在不在）的验证
全部 PASS，符号级却对不上，PID 1 在动态链接阶段就死掉，
表现就是黑屏 / logo 循环。

**案例一：killProcessGroupOnce**
原厂 init 引用的是 C 符号 `killProcessGroupOnce`；TWRP 的
`libprocessgroup.so` 只导出 C++ 改名版 `_Z20killProcessGroupOncejii`，
合并后的镜像里没有任何库提供 C 版。
修法：在 recovery 片段里删掉 TWRP 的 `libprocessgroup.so`，
让原厂版胜出。原厂版多依赖的 `libcgrouprc.so` 本就在镜像里
且为原厂版；TWRP 的 recovery 本体根本不链接这个库，删除安全。
（repack v3 已修复，验证 47 项全部 PASS。）

**案例二：android::base::Join 模板实例**
TWRP 的 `libhidl-gen-utils.so` 引用
`android::base::Join<std::vector<std::string>&, char const*>(...)`，
原厂 `libbase.so` 不导出这个模板实例，只有 twrp16 目录里的
API 36 版 libbase 导出。但 twrp16 只通过 recovery 服务定义里的
`setenv LD_LIBRARY_PATH` 对 recovery 进程生效；init 直接链接
`libhidl-gen-utils.so`，走默认路径解析不到这个符号。
原厂版 `libhidl-gen-utils.so` 不引用该符号且依赖闭合完整，
v4 计划同样删掉 recovery 片段里的覆盖版。
（其消费者为 init、hwservicemanager，均为原厂二进制；
librecovery_ui_ext 的符号满足情况待最后确认。）

**教训**：repack 路线必须用 `readelf --dyn-syms` 把 UND 引用和
DEF 导出逐条配对，不能只查 DT_NEEDED 闭合。

附带两条：
- `ueventd` 与 `init` 是字节完全一致的同一个文件，符号审计时
两个引用者都要算，不是多出一个无关消费者。
- 原厂两个 rc 第一行都有 `import /init.recovery.project.rc`，
但这个文件在原厂镜像里根本不存在，是原厂遗留的悬空 import，
无害，不要追。

## 9. 原厂固件自己的 DLKM 就是两个构建拼的

审计 `OS3.0.310.0` 的三个 dlkm 镜像（共 336 个.ko）：
`system_dlkm` 的 68 个模块 vermagic 与平板当前运行的内核完全一致
（`6.6.118-android15-8-gc44b714366cc-abogki519650608-4k`）；
`vendor_dlkm` 的 258 个模块却是另一个构建
（`gf1638d237c11`）。模块加载报 vermagic 对不上时，
先想想固件本身就是混装的。

## 10. 本平台在 recovery 下解密目前不可用

warhol（MT6993）同样记录了 recovery 解密不工作。repack 路线里
keystore / keymint 相关组件与原厂启动脚本对不齐，
刷入后不要指望能解密 /data，先保证能进界面再说。

## 当前状态（2026-11-10）

repack v3 已组装完成并通过全部静态验证（原厂模板 + 三处既有修复：
charger 二进制移除、mtk_plpath_utils 用回原厂、触摸行移入 mt8799 rc；
外加第 8 节案例一的 libprocessgroup 符号修复），待刷机验证。
v4 计划只多一项修改：删掉 recovery 片段的 `libhidl-gen-utils.so`
覆盖版（第 8 节案例二）。
