# v3.39 Vendor Boot 镜像刷入目标

实机分区日志显示 `/vendor_boot` 指向当前槽位的 64 MB 块设备，缺少
`Can_Flash_Img`。在已有 `twrp.flags` 中补充 `flashimg=1` 和显示名，
沿用 recovery.fstab 已有的 emmc、块设备路径及 slotselect。

```sh
python3 hybrid/stage55/build_vendor_boot_target.py \
  --base turner-vendor_boot-hybrid-v3.38-AUTH-LOOKUP-TEST.img \
  --output turner-vendor_boot-hybrid-v3.39-VENDOR-BOOT-TEST.img
```

构建器验证 v3.38 输入哈希、vendor_boot 布局、AVB 哈希和 DTB，逐条对比 ramdisk。
实机先在「安装」选择 vendor_boot 镜像，核对目标列表中显示 `Vendor Boot /vendor_boot`，
然后返回。刷入功能验收使用已知可启动的镜像和当前槽位。
