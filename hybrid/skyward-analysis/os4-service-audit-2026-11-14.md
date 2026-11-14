# OS4 服务布局审计 — turner / Redmi K Pad（2026-11-14）

审计对象：官方 OTA OS4.0.3.0.XAOCNXM 抽取的 vendor.img（2,343,292,928 B，sha256
`3dbcb0f807d0c7f3b59430e6b83c66804cfacae9a9c2c882db7cb039ea32a411`）与 odm.img
（929,005,568 B，sha256 `8b3fb766e76fc41b6ff5dec3c8676036032c90efd7e06470793ddfb8b6afc6c9`），
对照 a7（Skyward-for-turner，OS3.0.306 底座）的 device.toml
（`~/workspace/skyward-turner/x_a7_f1/skyward/device.toml`）。

审计方法：本地 EROFS 读取器 `~/workspace/skyward-turner/os4/erofs_read.py`
（本次审计中修了 4 个 bug，见末尾）+ `dump.erofs` 交叉核对（文件数、大小、
inode 信息）。vendor 全量 walk：6,160 条；odm 全量 walk：1,014 条。

## 结论：a7 的 toml 在 OS4 上原样可用，服务布局零改动

- 4 个 [[service]] 二进制全部在 toml 写死的路径上，版本未变。
- 5 个 VINTF 清单（keymint 3 接口分两个文件 + gatekeeper + touch）全部存在，
  fqname 与 toml 的 `ready_service` / `registers` 逐一对应。
- 3 份 rc 与 toml 的描述一致（OS4 只多了几行 chmod，无结构变化）。
- 触控：rc 覆盖 toml [[owners]] 清单的全部节点；vendor_dlkm 四个触控模块齐全；
  TA 目录 vendor（9 个 .ta）+ odm（2 个 .ta）都在。
- SDK 仍是 35，recovery 侧 libbinder 与 OS3/a7 逐字节一致。
- 唯一待真机验证的：libbinder RECO/SYST 世代标记在二进制里找不到字面量，
  静态方法无法定论；以及解密链的运行时行为——只能由 a7 实测 + 首个 OS4
  混合镜像首刷验证。

## 一、TEE 解密链（vendor）

| toml 路径 | OS4 实测 | 备注 |
|---|---|---|
| `/vendor/bin/tee-supplicant` | 在，68,576 B，sha `f4c6911c04b14d56…` | 无 raw fallback，提取干净 |
| `/vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee` | 在，138,456 B，sha `7fdd096eabdbbda7…` | **仍是 @3.0，与 OS3 同版本**；NEEDED 含 keymint-V3-ndk、secureclock-V1-ndk、sharedsecret-V1-ndk、rkp-V3-ndk、libteecli、libkeymint |
| `/vendor/bin/hw/android.hardware.gatekeeper-service.mitee` | 在，52,672 B，sha `68e24c8beb7a513a…` | 尾部 pcluster 原样存储（见“提取可信度”） |
| `/etc/init/tee-supplicant.rc` | 在，1,076 B | `mkdir /mnt/vendor/persist/data + fdsd`、`setprop vendor.teefs_state ready`、`enable vendor.keymint-mitee` 与 toml 描述一致；OS4 多了 ufs-bsg0 等 chmod 行，无害 |
| `/etc/init/android.hardware.security.keymint.mitee@3.0-service.rc` | 在，157 B | service 名 `vendor.keymint-mitee`，class early_hal，user system，group system drmrpc |
| `/etc/init/android.hardware.gatekeeper-service.mitee.rc` | 在，136 B | service 名 `vendor.gatekeeper_mitee`，class hal，user system |
| `/etc/vintf/manifest/android.hardware.security.keymint-service.mitee.xml` | 在 | IKeyMintDevice/default + IRemotelyProvisionedComponent/default，version 3 |
| `/etc/vintf/manifest/android.hardware.security.secureclock-service.mitee.xml` | 在 | ISecureClock/default |
| `/etc/vintf/manifest/android.hardware.security.sharedsecret-service.mitee.xml` | 在 | ISharedSecret/default |
| `/etc/vintf/manifest/android.hardware.gatekeeper-service.mitee.xml` | 在 | IGatekeeper/default |
| `/vendor/mitee/ta/` | 在，9 个 .ta | toml 说 TA 在 /odm/mitee/ta 与 /vendor/mitee/ta；两处都在 |
| `/vendor/lib64/libteecli.so` 等 keymint 依赖库 | 全在 | 24 个 NEEDED 库中 22 个在 /vendor/lib64；缺的 2 个见下 |

keymint 二进制含 `BnSecureClock` / `BnSharedSecret` / `IKeyMintDevice` /
`IRemotelyProvisionedComponent` 符号——单进程注册三接口的说法在 OS4 依然成立，
toml 的 `registers = [secureclock, sharedsecret]` 在 OS4 有各自独立的清单文件对应。

**不在 vendor/odm 的 2 个 NEEDED 库**：`libbinder_ndk.so`、`liblog.so`——
这两个是 system 分区 / APEX 的平台库，toml 的 libraries 清单本来就列了
`/mnt/system/system/lib64` 与 APEX 路径（`/apex/com.android.runtime/lib64` 等），
覆盖无缺口，不是问题。

**一个差异**：OS4 原厂 tee-supplicant.rc 是 `user system`；toml 坚持 root 运行，
理由是 /odm/mitee/ta 属主 root、system 读不了（a7 在 OS3 上实测出的）。
OS4 的 /odm/mitee/ta 同样存在且同布局，root 设定继续有效，不用改。

## 二、触控 HAL（odm）

| toml 路径 | OS4 实测 | 备注 |
|---|---|---|
| `/odm/bin/hw/vendor.xiaomi.hw.touchfeature-service` | 在，308,072 B，sha `3e4b038e04985afc…` | NEEDED 含 libui、libxml2、libbinder_ndk、libmisight、touchfeature-V1-ndk 等 |
| `/odm/etc/init/vendor.xiaomi.hw.touchfeature-service.rc` | 在，8,080 B | 覆盖 toml [[owners]] 全部节点：/dev/xiaomi-touch（0666）、knock/thp（0664）、enable_touch_raw、resolution_factor、touch_sensor、touch_sensor_ctrl、touch_thp_cmd、touch_thp_cmd_data、touch_thp_cmd_ready、update_rawdata、gesture_single_tap_state、fod_press_status 均在列 |
| `/odm/etc/vintf/manifest/vendor.xiaomi.hw.touchfeature-service.xml` | 在 | ITouchFeature/default |
| `/odm/lib64/libtouchreport{,_alg,_hal,_sensor}.so` + libtensorflowlite_touch_c.so | 全在 | toml 注释的 /odm/lib64 依赖齐全 |
| `/odm/mitee/ta/` | 在，2 个 .ta | 与 vendor 的 9 个互补 |

## 三、vendor_dlkm 触控模块

`nt36536e_touch_turner.ko`、`xiaomi_touch_turner.ko`、`touch_boost.ko`、
`mtk_ioctl_touch_boost.ko` 四个全在 `/lib/modules/`——与 toml `[modules] load`
及 os4-repack-plan.md §三 item 4 的已确认项一致。

## 四、版本与世代

- vendor build.prop：`OS4.0.3.0.XAOCN`，Android 15，SDK 35，security patch
  2026-10-01，build 日期 2026-11-06；device turner，model 25079RPDCC。
  与 OS3 同为 SDK 35——系统侧世代未升级，这是 toml 能平移的根本原因。
- recovery 侧 libbinder：OS4 F1 的 `system/lib64/libbinder.so` 与 a7 F1 的
  逐字节一致（sha `c083e732cdb1914f…`，800,944 B）——os4-repack-plan.md §三
  item 1 的结论复核无误。
- 系统侧 libbinder：`/vendor/lib64/libbinder.so` 是另一份构建
  （sha `3916fb004493dae1…`，784,344 B），与 recovery 侧不同——符合预期，
  a7 的 toml 正是靠 libraries 顺序（触控 HAL 用 recovery 的 libbinder 优先，
  TEE 链用已装系统的库）处理这一差别的，OS4 上配方不变。

## 五、未解决项（静态审计到此为止）

1. **libbinder RECO/SYST 标记**：在 vendor、OS4 F1、a7 F1 三份 libbinder 里，
   按两种字节序搜 `RECO` / `SYST` 字面量均为 0 命中——标记不是以 4 字节常量
   明文存放的（可能是立即数拆分或编译期生成），静态方法无法定论。
   决定性证据只能来自真机：a7 在 OS4 上的表现 + 首个 OS4 混合镜像的启动日志。
2. **解密链运行时行为**：keymint/gatekeeper/tee-supplicant 在 OS4 上的
   实际注册与 PIN 解 data，只能真机验证，审计无法替代。
3. **a7 实测结果**：截至本审计完成（2026-11-14 10:47 CST），用户尚未回复今早的
   a7 测试结果。

## 六、提取可信度与工具修复

本次审计修了 `erofs_read.py` 的 4 个 bug（均在工作区本地工具，不影响用户设备）：

1. extent 物理偏移解析：`dump.erofs -e` 的物理字段含 `长度 : 起止` 两段，
   旧代码按 `..` 切分取到长度值导致 int 转换失败。
2. extent 序号 ≥10 被丢弃：旧代码用 `startswith(('0:',…,'9:'))` 匹配行首，
   `10:` 不满足 `1:`，导致大文件（如 keymint 15 个 extent）只读到前 10 个、
   静默截断（keymint 曾被误读成 83,878 B，实为 138,456 B）。
3. 内联目录的分块布局：FLAT_INLINE 目录数据是“首块在 iu 指向的块、
   余量内联在 inode 之后”，旧代码按 data_off 连续读导致 /bin 等大目录
   解析出垃圾、walk 递归爆炸。修后 vendor walk 完整通过（6,160 条）。
4. LZ4 前导零填充：个别 pcluster 的压缩流不在块首（前导 1321 字节零填充，
   LZ4_0PADDING 特性），旧代码只去尾零导致解压失败。修后 build.prop
   完整恢复（30,960 B，零 raw fallback）。

所有审计用文件均以 `dump.erofs --path` 的 Size 逐个核对（vendor 6,160 条、
odm 1,014 条全量 walk 零报错），关键二进制均通过 ELF 头校验
（e_shoff/e_phoff 在文件内、NEEDED 清单完整）。

仍带 raw-fallback 标记的文件（EROFS 原样存储的尾部 pcluster，内容经抽查
符合 ELF 结构——重定位表形态、尾部零填充均正常，属正常现象而非损坏）：
keymint（2 段）、gatekeeper（1 段）、touchfeature-service（3 段）、
vendor libbinder（9 段）。待用户发来平板实机的小审计 tar（os4-audit.tar）
后，可逐字节交叉核对这几处。

## 下一步（按 os4-repack-plan.md §四验证门）

1. 等用户 a7 实测结果（进界面？触控？PIN 解 data？挂点？）。
2. 门 3 已可打勾：toml 每个 [[service]] 路径在 OS4 vendor/odm 中真实存在。
3. 混合镜像组装仍待：OS4 vendor_boot 底座（官方 OTA 已抽，`os4/vendor_boot.img`）、
   YARP TWRP userspace + 严格库隔离、按 a7 toml 编排已装系统服务。
   首刷纪律不变：白天、追梦 OS4 vendor_boot 在手边、先清 BCB。
