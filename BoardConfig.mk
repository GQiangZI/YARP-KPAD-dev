#
# Copyright (C) 2025 The TWRP Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# YARP base: TWRP-Test/platform_manifest_twrp_aosp, branch twrp-16.0
# (TWRP 3.7.1_16, GUI2/LVGL) + PR #42 (OTG hotplug fix, applied by the
# build workflow). Adapted from the twrp-14.1 minimal-manifest tree; the
# rothko patches that 14.1 needed are mostly already upstream here, see
# patches/PATCHES.md for the per-patch verdict.
#
DEVICE_PATH := device/xiaomi/turner

# Architecture
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_ABI2 :=
TARGET_CPU_VARIANT := generic
TARGET_CPU_VARIANT_RUNTIME := cortex-a55

TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv8-a
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_2ND_CPU_VARIANT := generic
TARGET_2ND_CPU_VARIANT_RUNTIME := cortex-a55

TARGET_IS_64_BIT := true
TARGET_USES_64_BIT_BINDER := true
TARGET_BOARD_SUFFIX := _64

# Board
TARGET_BOARD_INFO_FILE := $(DEVICE_PATH)/board-info.txt

# Power
ENABLE_CPUSETS := true
ENABLE_SCHEDBOOST := true

# Assertation
TARGET_OTA_ASSERT_DEVICE := turner

# Bootloader
TARGET_BOOTLOADER_BOARD_NAME := mt6991
TARGET_NO_BOOTLOADER := true
TARGET_USES_UEFI := true

# Build Hack
BUILD_BROKEN_DUP_RULES := true
BUILD_BROKEN_ELF_PREBUILT_PRODUCT_COPY_FILES := true

# Full TWRP-Test manifest (not the 14.1 minimal manifest); keep the escape hatch
ALLOW_MISSING_DEPENDENCIES := true

# Crypto
TW_INCLUDE_CRYPTO := true
TW_INCLUDE_CRYPTO_FBE := true
BOARD_USES_METADATA_PARTITION := true
TW_INCLUDE_FBE_METADATA_DECRYPT := true
TW_USE_FSCRYPT_POLICY := 2
# TWRP's relink list still names the V1 AIDL libs; vold and the stock mitee keymint/gatekeeper
# need these. Listing them also gets them built for .github/scripts/recovery_deps.py
TW_RECOVERY_ADDITIONAL_RELINK_LIBRARY_FILES += \
    $(TARGET_OUT_SHARED_LIBRARIES)/android.system.keystore2-V4-ndk.so \
    $(TARGET_OUT_SHARED_LIBRARIES)/android.hardware.security.keymint-V3-ndk.so \
    $(TARGET_OUT_SHARED_LIBRARIES)/android.hardware.security.rkp-V3-ndk.so \
    $(TARGET_OUT_SHARED_LIBRARIES)/android.hardware.gatekeeper-V1-ndk.so \
    $(TARGET_OUT_SHARED_LIBRARIES)/android.hardware.confirmationui-V1-ndk.so
PLATFORM_VERSION := 99.87.36
PLATFORM_VERSION_LAST_STABLE := $(PLATFORM_VERSION)
PLATFORM_SECURITY_PATCH := 2099-12-31
BOOT_SECURITY_PATCH := $(PLATFORM_SECURITY_PATCH)
VENDOR_SECURITY_PATCH := $(PLATFORM_SECURITY_PATCH)

# Vendor Boot
TARGET_KERNEL_ARCH := arm64
BOARD_RAMDISK_USE_LZ4 := true
TARGET_KERNEL_HEADER_ARCH := arm64
TARGET_NO_KERNEL := true
BOARD_KERNEL_SEPARATED_DTBO := true
TARGET_PREBUILT_DTB := $(DEVICE_PATH)/prebuilt/dtb
BOARD_USES_GENERIC_KERNEL_IMAGE := true
BOARD_MOVE_RECOVERY_RESOURCES_TO_VENDOR_BOOT := true
BOARD_INCLUDE_RECOVERY_RAMDISK_IN_VENDOR_BOOT := true
# The common Skyward PLATFORM ramdisk already supplies first-stage modules.
# The NT36536E input driver lives in the installed vendor_dlkm, not in that
# 274-module set. YARP twrp_flags.go only enables its vendor module loader
# when this filename list is nonempty; TW_LOAD_VENDOR_BOOT_MODULES alone
# does not enable it. Keep dependency resolution in upstream libmodprobe.
TW_LOAD_VENDOR_MODULES := "nt36536e_touch_turner.ko"
TW_LOAD_VENDOR_BOOT_MODULES := true
# 原厂 turner vendor_boot.img 实测 header（见 analysis/vendor_boot_header.json）：
#   kernel_addr=0x80000000  ramdisk_addr=0xA6F00000
#   tags_addr=dtb_addr=0x87C80000
# mkbootimg 以 base + *_OFFSET 写入这四个地址；旧 base 0x3FFF8000 使四个地址
# 整体偏低 0x40000000。0x7FFF8000 配合现有 offsets 恰好还原原厂值。
BOARD_KERNEL_BASE := 0x7FFF8000
BOARD_PAGE_SIZE := 4096
BOARD_KERNEL_OFFSET := 0x00008000
BOARD_RAMDISK_OFFSET := 0x26F08000
BOARD_TAGS_OFFSET := 0x07C88000
BOARD_BOOT_HEADER_VERSION := 4
BOARD_DTB_SIZE := 533115
BOARD_DTB_OFFSET := 0x07C88000
BOARD_HEADER_SIZE := 2128
# 原厂 cmdline 含 erofs.reserved_pages=64（super 内全是 erofs 逻辑分区），
# 丢掉会影响 first_stage_mount / recovery 挂载。保留原厂值后再追加 permissive。
BOARD_VENDOR_CMDLINE := "bootopt=64S3,32N2,64N2 erofs.reserved_pages=64 androidboot.selinux=permissive"
BOARD_MKBOOTIMG_ARGS += --dtb $(TARGET_PREBUILT_DTB)
BOARD_MKBOOTIMG_ARGS += --vendor_cmdline $(BOARD_VENDOR_CMDLINE)
BOARD_MKBOOTIMG_ARGS += --pagesize $(BOARD_PAGE_SIZE) --board ""
BOARD_MKBOOTIMG_ARGS += --kernel_offset $(BOARD_KERNEL_OFFSET)
BOARD_MKBOOTIMG_ARGS += --ramdisk_offset $(BOARD_RAMDISK_OFFSET)
BOARD_MKBOOTIMG_ARGS += --tags_offset $(BOARD_TAGS_OFFSET)
BOARD_MKBOOTIMG_ARGS += --header_version $(BOARD_BOOT_HEADER_VERSION)
BOARD_MKBOOTIMG_ARGS += --dtb_offset $(BOARD_DTB_OFFSET)

# Partitions
BOARD_FLASH_BLOCK_SIZE := 262144
BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE := 67108864
BOARD_SUPER_PARTITION_SIZE := 9663676416
BOARD_SUPER_PARTITION_GROUPS := main
BOARD_MAIN_PARTITION_LIST := system system_ext product vendor vendor_dlkm odm
# BOARD_SUPER_PARTITION_SIZE - 10MiB
BOARD_MAIN_SIZE := 9653190656
BOARD_PARTITION_LIST := $(call to-upper, $(BOARD_MAIN_PARTITION_LIST))
$(foreach p, $(BOARD_PARTITION_LIST), $(eval BOARD_$(p)IMAGE_FILE_SYSTEM_TYPE := erofs))
$(foreach p, $(BOARD_PARTITION_LIST), $(eval TARGET_COPY_OUT_$(p) := $(call to-lower, $(p))))
BOARD_USERDATAIMAGE_FILE_SYSTEM_TYPE := f2fs
TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USERIMAGES_USE_F2FS := true
BOARD_USES_VENDOR_DLKMIMAGE := true

# Hardware
BOARD_USES_MTK_HARDWARE := true

# Platform
TARGET_BOARD_PLATFORM := mt6991

# Properties
TARGET_SYSTEM_PROP += $(DEVICE_PATH)/system.prop

# Device Fstab (YARP tree layout: top level, like device/xiaomi/sm8850)
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/recovery.fstab

# Resolution
TARGET_SCREEN_HEIGHT := 3008
TARGET_SCREEN_WIDTH := 1880

# Screen Density
# TARGET_SCREEN_DENSITY := 446

# Recovery
TARGET_NO_RECOVERY := true
BOARD_HAS_LARGE_FILESYSTEM := true
BOARD_HAS_NO_SELECT_BUTTON := true
BOARD_SUPPRESS_SECURE_ERASE := true
TARGET_RECOVERY_PIXEL_FORMAT := RGBX_8888

# Verified Boot (warhol-style AVB block, copied from noahbliss/twrp-warhol)
BOARD_AVB_ENABLE := true
BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS += --flags 3
BOARD_AVB_RECOVERY_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_RECOVERY_ALGORITHM := SHA256_RSA4096
BOARD_AVB_RECOVERY_ROLLBACK_INDEX := 1
BOARD_AVB_RECOVERY_ROLLBACK_INDEX_LOCATION := 1
# vendor_boot footer: this tree's build/make/core/Makefile signs vendor_boot
# with $(INTERNAL_AVB_VENDOR_BOOT_SIGNING_ARGS), which is undefined anywhere
# in the tree (so v4 got a hash-only footer, Algorithm NONE). The
# BOARD_AVB_VENDOR_BOOT_* vars alone do not feed that rule, so define the
# signing args here to make the vendor_boot footer actually RSA4096-signed.
BOARD_AVB_VENDOR_BOOT_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_VENDOR_BOOT_ALGORITHM := SHA256_RSA4096
BOARD_AVB_VENDOR_BOOT_ROLLBACK_INDEX := 1
BOARD_AVB_VENDOR_BOOT_ROLLBACK_INDEX_LOCATION := 1
INTERNAL_AVB_VENDOR_BOOT_SIGNING_ARGS := --algorithm SHA256_RSA4096 --key external/avb/test/data/testkey_rsa4096.pem --rollback_index 1

# Init
TARGET_INIT_VENDOR_LIB := //$(DEVICE_PATH):libinit_turner
TARGET_RECOVERY_DEVICE_MODULES := libinit_turner

# TWRP Configurations
TW_FRAMERATE := 165
TW_STATUS_ICONS_ALIGN := center
TW_THEME := portrait_hdpi
TW_BRIGHTNESS_PATH := "/sys/class/leds/lcd-backlight/brightness"
TW_DEFAULT_BRIGHTNESS := 200
TW_MAX_BRIGHTNESS := 2047
RECOVERY_SDCARD_ON_DATA := true
TW_EXCLUDE_DEFAULT_USB_INIT := true
TW_PREPARE_DATA_MEDIA_EARLY := true
TW_USE_NEW_MINADBD := true
TW_EXCLUDE_APEX := true
TW_DEFAULT_LANGUAGE := zh_CN
TW_HAS_NO_DISPLAY_CUTOUT := false
# TW_STATUS_BAR_HEIGHT := 90
# TW_Y_OFFSET := 90
# TW_H_OFFSET := -90
TW_NO_LEGACY_PROPS := true
TW_NO_BIND_SYSTEM := true
TW_BACKUP_EXCLUSIONS := /data/fonts
TW_INPUT_BLACKLIST := "hbtp_vm"
TW_DEVICE_VERSION := Redmi_K_Pad | QiangZi
TARGET_USE_CUSTOM_LUN_FILE_PATH := /config/usb_gadget/g1/functions/mass_storage.usb0/lun.%d/file
TW_USE_SERIALNO_PROPERTY_FOR_DEVICE_ID := true

# Fastbootd
TW_INCLUDE_FASTBOOTD := true
# 16.0 WipeEncryption drops the metadata-encryption userdata mapping with
# `dmctl delete userdata` (replaces the old FDE ioctl stub); needs dmctl
TW_USE_DMCTL := true

# Debug
TARGET_USES_LOGD := true
TWRP_INCLUDE_LOGCAT := true
TWRP_EVENT_LOGGING := true
# debug aids (same as the sm8850 YARP tree); useful if the new build also
# shows a black screen — adb + logcat + strace stay available in recovery
# debuggerd dropped: its relinked deps (libdebuggerd_handler.so / libdebuggerd_client.so)
# are not in TW_RECOVERY_ADDITIONAL_RELINK_LIBRARY_FILES, and recovery has no tombstoned
TARGET_RECOVERY_DEVICE_MODULES += strace
RECOVERY_BINARY_SOURCE_FILES += $(TARGET_OUT_EXECUTABLES)/strace

# Tools
TW_INCLUDE_RESETPROP := true
# off: TWRP repacks into /boot, but on turner recovery lives in vendor_boot (Install Recovery Ramdisk would break boot)
TW_INCLUDE_REPACKTOOLS := false
TW_INCLUDE_LIBRESETPROP := true
TW_INCLUDE_LPDUMP := true
TW_INCLUDE_LPTOOLS := true

# Filesystem Feature
TW_INCLUDE_NTFS_3G := true
TARGET_USES_MKE2FS := true
TW_INCLUDE_FUSE_NTFS := true
TW_INCLUDE_FUSE_EXFAT := true

# Haptic
# Stock vendor_boot has no haptic.ko (verified against its 274 modules);
# loading a missing module is a no-op, so drop the dead reference.
TW_SUPPORT_INPUT_AIDL_HAPTICS := true
TW_SUPPORT_INPUT_AIDL_HAPTICS_FQNAME := "IVibrator/vibratorfeature"
TW_SUPPORT_INPUT_AIDL_HAPTICS_FIX_OFF := true

# Indicator
TW_CUSTOM_CPU_TEMP_PATH := "/sys/class/thermal/thermal_zone53/temp"
TW_BATTERY_SYSFS_WAIT_SECONDS := 6
# read capacity straight from sysfs: recovery has no registered health HAL, so the default path shows a fake 100%
TW_USE_LEGACY_BATTERY_SERVICES := true
# pin the sysfs node so the legacy branch never falls back to TWRP's built-in default
TW_CUSTOM_BATTERY_PATH := "/sys/class/power_supply/battery/capacity"
