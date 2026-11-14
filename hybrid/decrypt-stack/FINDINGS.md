# turner（Redmi K Pad）凭据验证栈盘点 — HyperOS OS4 实测

盘点目的：为混合 recovery 的解密阶段提供事实依据——小米到底在 turner 上用了
哪套凭据方案，YARP 群里说的 thales/goodix 双 Weaver 风险在不在这台机器上。

证据来源（全部本地实物，非推测）：

- OS4 `vendor.img` / `odm.img`（官方 OTA OS4.0.3.0.XAOCNXM 抽取，
  sha256 `3dbcb0f8…` / `8b3fb766…`）——用审计同款 EROFS 读取器全量 walk：
  vendor 6,160 条、odm 1,014 条，与 `os4-service-audit-2026-11-14.md` 数字一致。
  全量清单存本目录 `os4_vendor_list.txt` / `os4_odm_list.txt`。
- OS4 F1 树 `~/workspace/skyward-turner/os4/os4_f1/`（fstab / prop 文件）。
- 凭据相关二进制 strings 扫描：tee-supplicant、keymint 服务、gatekeeper 服务、
  libteecli、libkeymint、libgatekeeper（抽取存本目录 `bin/`，大小与审计逐一对上）。
- OS3 对照：a7 的 `device.toml`（适配者从 OS3 原厂 rc 抄出的解密链定义，且该链
  已在 OS3 上实测解开 data）+ OS3 stock310 F0/F1 ramdisk 树。
- piano 树（`~/workspace/piano-tree`）——双 Weaver 世界的形态对照。

---

## 一、turner OS4 有没有 Weaver HAL？——没有，一处都没有

文件名级（vendor + odm 全量 7,174 条，`grep -i weaver`）：**0 命中**。

- 没有 `libmi_weaver.so`（piano 用它作世代标记的那个文件，turner odm 里不存在）；
- 没有 `android.hardware.weaver` 二进制、没有 weaver 的 rc、没有 weaver 的 TA；
- VINTF：vendor `/etc/vintf/manifest/` 全部条目 + odm 全部条目逐一过目，
  **没有 `android.hardware.weaver` 的 fqname**；总清单 `/etc/vintf/manifest.xml`
  grep weaver = 0；`compatibility_matrix.xml` 里 weaver/gatekeeper/keymint 均 0 命中。

OS3 对照：stock310 与 a7 的 F0/F1 树文件名 grep（weaver/thales/mi_weaver）
同样 0 命中；更决定性的是 a7 的 toml——适配者照 OS3 原厂 rc 写下的解密链
只有 tee-supplicant → keymint → gatekeeper 三件（见第三节），无任何 Weaver
成分，而 Skyward 在 OS3 上就是用这条链解开的 data。（注：本地无 OS3 的
vendor.img，OS3 侧结论以 toml + ramdisk 树为据。）

**piano 对照（为什么群里会有双方案之说）**：piano 是高通 SM8750，它的
`piano-setup.sh:76` 明确 `if [ -f "${MNT}/odm/lib64/libmi_weaver.so" ]`，
其 variant/hos3 里实打实装着 `odm/lib64/libmi_weaver.so` 和
`odm/bin/hw/android.hardware.weaver` 二进制——双安全栈/Weaver 选择是
**高通小米**的世界。turner 是 MTK + 小米自研 mitee，那个标记文件在本机
返回「不存在」，整套机制与本机无关。

## 二、thales / goodix 双方案痕迹？——零痕迹，唯一的 goodix 是音响功放

- 文件名：`thales` 在 vendor+odm = **0 命中**；`goodix` 仅 1 命中：
  `/lib64/libgoodixsmartpaparser.so`。strings 实锤其身份：Goodix **Smart PA
  喇叭功放**参数解析库（`tfa98xx_music.bin`、`audio_mode`、`output_device`），
  与凭据毫无关系（汇顶也做音频功放芯片，仅此而已）。
- strings 级：对 6 个凭据二进制/库（tee-supplicant、
  `android.hardware.security.keymint@3.0-service.mitee`、
  `android.hardware.gatekeeper-service.mitee`、libteecli.so、libkeymint.so、
  libgatekeeper.so）扫 `thales|goodix|weaver`：**全部 0 命中**。

## 三、OS4 凭据链全清单（PIN 验证 + FBE 密钥派生）

全部位于 **vendor**，全部是小米自研 **mitee** CA 构建（VINTF 清单注释的
源码路径为 `vendor/xiaomi/proprietary/mitee_ca/…`）：

| 环节 | 文件（OS4 vendor.img 内路径） | 细节 |
|---|---|---|
| TEE 客户端守护 | `/bin/tee-supplicant`（68,576 B）+ `/etc/init/tee-supplicant.rc` | service `tee-supplicant`，class core，disabled，由 `on fs` 启用；同 rc 内 `enable vendor.keymint-mitee`、建 `/mnt/vendor/persist/data` 与 `/mnt/vendor/persist/fdsd`（0755 system system）、`setprop vendor.teefs_state ready`、**`setprop ro.hardware.gatekeeper mitee`**；chmod 0660 `/dev/tee0`、`/dev/teepriv0`、`/dev/rpmb0`、`/dev/mmcblk0rpmb`、`/dev/ufs-bsg0`；strings 确认 TA 搜索路径 `/vendor/mitee/ta` + `/odm/mitee/ta`，安全存储 `/mnt/vendor/persist` |
| KeyMint | `/bin/hw/android.hardware.security.keymint@3.0-service.mitee`（138,456 B） | service `vendor.keymint-mitee`，class early_hal，user system，disabled（由上面 rc 启用）。VINTF（三个清单文件）：`android.hardware.security.keymint` v3 → **IKeyMintDevice/default** + **IRemotelyProvisionedComponent/default**；`android.hardware.security.secureclock` → **ISecureClock/default**；`android.hardware.security.sharedsecret` → **ISharedSecret/default**。单进程注册三接口（审计已验符号） |
| Gatekeeper（PIN 验证本体） | `/bin/hw/android.hardware.gatekeeper-service.mitee`（52,672 B） | service `vendor.gatekeeper_mitee`，class hal。VINTF：`android.hardware.gatekeeper` AIDL → **IGatekeeper/default**。PIN 的 HMAC 验证与节流全在 mitee 内完成，**中间没有 Weaver** |
| TA 文件 | `/mitee/ta/`（vendor 9 个）+ odm `/mitee/ta/`（2 个） | vendor：`4d573443-6a56-4272-ac6f2425af9ef9bb`、`655a4b46-cd77-11ea-aafbf382a6988e7b`、`68bcd09d-4101-4c0a-9552ed0af9ae16b2`、`86f623f6-a299-4dfd-b560ffd3e5a62c29`、`8aaaf201-2460-0000-7143fe4f7c823c80`、`8aaaf201-2460-0000-aabbccdd00000006`、`9811c1f6-47e3-5cea-ae6ef62ba433c4fd`、`dba51a17-0563-11e7-93b16fa7b0071a51`、`e97c270e-a5c4-4c58-bcd3384a2fa2539e`；odm：`123af5d1-d6f5-cc54-f78fa19030b2e76a`、`a3ba6512-6e0e-4065-93165e4a7d04ca08`。TA 为签名 TEE 二进制，strings 只有通用 TEE agent 错误串，各 TA 身份静态不可判读（不影响结论：keymint/gatekeeper 服务只经 tee-supplicant 加载它们） |
| 支撑库 | `/lib64/libteecli.so`、`/lib64/libkeymint.so`、`/lib64/libgatekeeper.so`、`android.hardware.security.keymint-V3-ndk.so`、`android.hardware.gatekeeper-V1-ndk.so`、`libkeymint_support.so`、`lib_android_keymaster_keymint_utils.so`（及 32 位对应件） | — |
| 相邻 mitee 服务（不在 FBE/PIN 路径上，仅记录） | `/bin/hw/android.hardware.identity-service.mitee@5.0` | VINTF：`android.hardware.identity` v5 → IIdentityCredentialStore/default。电子身份凭证用，同为 mitee 后端，解密 data 用不到 |
| TEE 日志 | `/bin/miteelog` + rc | 支撑件，非凭据环节 |

**明确不存在的组件**（全量清单 + `/bin/hw/` 全目录核对）：

- **secure_element / eSE HAL：不存在。** `/bin/hw/` 里没有任何 secure_element
  服务；文件名含 secure 的只有 secureclock 相关两条。tee-supplicant rc 里
  `group system secure_element nfc` 只是 unix 组名（给 /dev 访问权），不是服务。
- **ssgtzd：不存在。**
- **batterysecret：存在但与凭据无关。** `/bin/batterysecret` +
  `/etc/init/hw/init.batterysecret.rc` 实锤是 **USB-PD 充电器鉴权**守护进程
  （rc 里全是 `/sys/class/usbpd/…`、`pd_authentication`、`bms/authentic` 节点，
  在 boot_completed / charger 时启动）。piano 的安全栈 variant 里混有同名文件，
  但 turner 上它只管充电鉴权，**不要把它拉进解密链**。

## 四、userdata 加密声明（逐字引用）

OS4 F1 `system/etc/recovery.fstab` 第 65 行，与 OS4 vendor `/etc/fstab.mt8799`
的 userdata 行**逐字相同**：

```
/dev/block/by-name/userdata /data f2fs noatime,nosuid,nodev,discard,noflush_merge,fsync_mode=nobarrier,reserve_root=134217,resgid=1065,gc_merge,atgc,age_extent_cache,inlinecrypt wait,check,formattable,quota,latemount,resize,reservedsize=128m,checkpoint=fs,fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized,keydirectory=/metadata/vold/metadata_encryption,fsverity
```

要点：FBE v2（`fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized`，
inlinecrypt 内联加密）；元数据加密密钥目录
`keydirectory=/metadata/vold/metadata_encryption`；userdata 行上**没有**
`metadata_encryption=` 标志、**没有** `wrappedkey`；`/metadata` 分区行本身
无加密标志（明文存放密钥 blob）。OS4 F1 的 `fstab.emmc` 变体只有细微差别
（少 gc_merge/atgc/age_extent_cache，fileencryption 尾为 `:v2` 无
`+inlinecrypt_optimized`）。

**OS3 对照**：stock310 F1 `recovery.fstab` 第 65 行与 OS4 **逐字节相同**——
加密声明 OS3→OS4 未变。

## 五、方案选择类属性

- vendor `build.prop`：`ro.vendor.mtk_mitee_support=1`、
  `ro.vendor.mtk_tee_gp_support=1`、`ro.crypto.volume.filenames_mode=aes-256-cts`。
- odm `/etc/build.prop`：无任何凭据相关属性。
- OS4 F0/F1 的 prop.default / default.prop：无 gatekeeper/weaver 选择项。
- 唯一的「方案选择」动作在运行时：tee-supplicant.rc 的 `on fs` 里
  `setprop ro.hardware.gatekeeper mitee`——选的值恒为 mitee。
  **不存在 `ro.twrp.weaver` 的对应物，不存在任何按已装 ROM 切换凭据方案的
  属性或配置。**

## 六、结论

**(a) turner 的 PIN 链是纯 gatekeeper + keymint，不是 Weaver 式。**
整机不存在 Weaver HAL，PIN 验证路径上没有它站的位置：锁屏凭据经
`IGatekeeper/default`（mitee）在 TEE 内做 HMAC 验证与节流，FBE 密钥操作经
`IKeyMintDevice/default` v3（mitee，含 ISecureClock / ISharedSecret 同进程
注册），两者都由 tee-supplicant 喂 TA。这是 AIDL 版的经典
Gatekeeper+KeyMint 组合，与高通小米那套（Weaver 槽位 + onekeymint/StrongBox）
是两个世界。

**(b) thales/goodix 双方案风险在 turner 上不存在。**
双 Weaver 是高通小米按 odm 配置运行时二选一的机制（piano 的
libmi_weaver 标记、sm8850 树的 weaver-vendor.sh 都是这个语境）；17U 当年
失败是「写解密时不知道有两套」。turner（MTK + mitee）在 OS3、OS4 两代
证据里都只有一条链：没有可选项，也就没有选错的可能。本机不需要、也不
应该引入任何方案探测/切换逻辑。

**(c) OS4 与 OS3 的凭据链组成：零差异。**
同一组三服务、同路径、同版本（keymint 仍 @3.0）、同 VINTF fqname、
TA 布局同为 vendor 9 + odm 2、fstab 加密声明逐字节相同、rc 结构不变
（审计：OS4 的 tee-supplicant.rc 只多了 ufs-bsg0 等 chmod 行）。
与 YuKongA 的判断互证：加密方案出厂定死、OTA 改不了。因此 a7 在 OS4 上
PIN 解不开**不是方案变了**——链没动，变量只剩参数对齐（stage2 已定位的
首要嫌疑：载荷呈现的 OS 版本/补丁级别是 OS3.0.310 / 2026-08-01，系统实际
是 OS4 / 2026-10-01）或凭据世代（系统内改一次锁屏密码重生凭据）。

**(d) 混合版 turner-setup.sh 解密阶段的硬性要求清单**（全部有据）：

1. **先挂载**已装系统的 vendor + odm（TA 两个目录分居两处），且 persist
   必须挂在 `/mnt/vendor/persist`（部分加密系统只认此路径，a7 toml 亦用此路径）。
2. **建目录** `/mnt/vendor/persist/data` 与 `/mnt/vendor/persist/fdsd`
   （0755 system:system）——recovery 里 init 的 `on fs` 不会替你做，
   keymint 的 fdsd 密钥存储就在里面（toml [[owners]] create 项）。
3. **设备节点权限**：`/dev/tee0`、`/dev/teepriv0`、`/dev/rpmb0`
   （及 mmcblk0rpmb 名）0660 system:system（原厂 rc / toml owners 一致）。
4. **参数对齐先于 keymint 启动**：从已装 ROM 现读真实 OS 版本与安全补丁
   级别并 resetprop（piano 法）。链组成 OS3→OS4 没变，这是剩余变量里
   唯一还没对齐的一项。
5. **启动顺序与等待**（照 toml 实测值）：tee-supplicant 先行——且必须
   **以 root 运行**（`/odm/mitee/ta` 属主 root，system 身份会
   "loading ta from /odm/mitee/ta failed"）；等 TEE 就绪后起
   keymint@3.0-service.mitee（toml wait 4000 ms 级别）；再起
   gatekeeper-service.mitee（wait 5000 ms 级别）；向 TWRP 解密 UI 交棒前，
   确认 `android.hardware.security.keymint.IKeyMintDevice/default` 与
   `android.hardware.gatekeeper.IGatekeeper/default` 均已在 servicemanager
   注册可见。
6. **三份 VINTF 清单必须齐**：IKeyMintDevice / ISecureClock / ISharedSecret
   三个 fqname 的清单都要能被 vintf 校验看到——缺任何一份，keymint 注册
   第二个接口时会被判致命错误直接 abort（toml 注释里的实测教训）。
7. **不起 vndservicemanager**：a7 实测它在本机 SIGABRT 循环，且服务实际
   注册在 /dev/binder 的 servicemanager 上（b8 的教训，见舞台 2 设计）。
8. **单链硬编码**：不写 weaver 探测、不留方案切换分支；mitee 链是本机
   唯一链。载荷自带的 mitee 栈（stage2 已验与 OS4 逐字节相同）只作后备，
   主用已装系统的（用户规则 + toml 先例）。
9. **时序统一**：解密完成前不要 umount 凭据链依赖的任何挂载（群内教训：
   解密流程提前 umount 曾连带弄挂触摸）；服务编排与触摸 HAL 共用一套
   启动时序管理。
10. **兜底认知**：若参数对齐后 PIN 仍失败，下一杠杆在系统侧（在 OS4 里
    改一次锁屏密码让凭据按当前世代重生），不在 recovery 侧换方案——
    不要为此去移植任何 Weaver/onekeymint 组件，那些与本机无关。

---

附：本目录证据文件——`os4_vendor_list.txt`、`os4_odm_list.txt`（全量清单）、
`bin/`（凭据二进制抽取）、`dump_files.py`（EROFS 定点读取脚本）、
`os4_vendor_buildprop.txt`（vendor build.prop 全文）。
