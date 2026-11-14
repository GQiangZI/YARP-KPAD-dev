# DRM plane-selection failure — research report (stage 5)

Device: turner (Redmi K Pad, MT6991 / mtk_drm, kernel 6.6.118). Build: TWRP 3.7.1_16
GUI2 (TWRP-Test twrp-16.0). Failure: GUI init dies, recovery process exits, init
restarts it forever. Researched 2026-11-14 against fetched twrp-16.0 sources and
the device's own recovery.log/dmesg.

## Verdict

The GUI2 minui DRM backend (`twrpminui/`) is a **Qualcomm SDE/CLO port**. Its
atomic pipeline setup decides "is this a primary plane" by parsing a
**Qualcomm-SDE-only plane property named `capabilities`** (a text blob containing
`primary_smart_plane_id=`). MediaTek's DRM driver has never exposed such a
property, so on MT6991 **every** plane is rejected, the required count of 2 is
never met, and `Initdisplay()` returns −1. It is not a splash-handover, plane
in-use, or CRTC-state problem: the check never looks at plane state or fb_id,
and it never reads the standard DRM `type` property either. Everything before
that gate (connector/CRTC discovery, mode selection, dumb-buffer allocation)
works fine on MTK — the log proves it ("Framebuffer of size 22620160 allocated"
×2, then death).

## Q1 — Source of the log line and the exact condition

**Location:** `twrpminui/graphics_drm.cpp`, `MinuiBackendDrm::Initdisplay()`
(the `#else // TWRP: active implementation` copy), line 791, in
TWRP-Test/android_bootable_recovery @ `twrp-16.0`. It is compiled into
**`libtwrpminui.so`** — verified: the string lives in the payload's
`system/lib64/libtwrpminui.so`, which in the shipped v2.1 image sits at
`system/lib64/twrp16/libtwrpminui.so` (268,768 B, sha256 `06158204…`, identical
in both places). `libgui2.so` only prints the final
`gui2: minui display initialization failed`.

**The gate** (Initdisplay, lines 749–795, abridged to the operative logic):

```cpp
// number_of_lms comes from the connector property "mode_properties":
for (i in conn_res.props)
  if (!strcmp(name, "mode_properties"))
    number_of_lms = get_topology_lm_number(fd, prop_value);   // SDE topology blob
if (number_of_lms == 0 || number_of_lms > NUM_PLANES /*4*/) return -1;  // "invalid mixer count"

for (i = count_planes-1; i >= 0 && selected < number_of_lms; --i) {   // reverse order
  plane = drmModeGetPlane(fd, planes[i]);
  if (!(plane->possible_crtcs & (1U << crtc_index))) continue;
  bool primary = false;
  if (load_properties(plane->plane_id, DRM_MODE_OBJECT_PLANE, &candidate))
    for (j in candidate.props)
      if (!strcmp(props_info[j]->name, "capabilities"))          // <-- the gate
        primary = is_primary_plane(fd, prop_values[j]);
  if (primary) plane_res[selected++] = candidate; else free/skip;
}
if (selected != number_of_lms) {
  fprintf(stderr, "TWRP DRM: display %d found %u/%u primary planes for CRTC index %d\n",
          index, selected, number_of_lms, crtc_index);
  return -1;
}
```

`is_primary_plane()` (lines 161–185) fetches the `capabilities` **blob** and
scans it as text:

```cpp
static bool is_primary_plane(int fd, uint32_t blob_id) {
  bool primary = false;
  uint32_t master_plane_id_val = 0;
  blob = drmModeGetPropertyBlob(fd, blob_id);
  if (!blob) return false;
  ... scan lines for "primary_smart_plane_id=" -> master_plane_id_val = atoi(...)
  primary = master_plane_id_val ? false : true;   // 0 (or line absent) => "primary"
  return primary;
}
```

So a plane counts **iff**:
1. `possible_crtcs` includes the connector's CRTC index (MTK planes pass this), AND
2. the plane has a property literally named **`capabilities`** whose blob either
   lacks `primary_smart_plane_id=` or sets it to `0`. **No `capabilities`
   property ⇒ never counted.** Blob fetch failure ⇒ not counted.

And the required count: `get_topology_lm_number()` parses the connector's
`mode_properties` blob through a string table of **SDE topology names**
(`sde_dualpipe`→2, `sde_quadpipemerge`→4, …). With no such property (all
non-SDE drivers) `number_of_lms` keeps its member default
**`DEFAULT_NUM_LMS = 2`** (graphics_drm.h:35, :254). That is the "/2" in the
log — **it is the required LM count, not the number of planes the kernel
exposes** (MTK exposes many OVL-layer planes; all are rejected by gate 2).

Caller chain: `MinuiBackendDrm::Init()` sets client caps
`DRM_CLIENT_CAP_UNIVERSAL_PLANES` + `ATOMIC`, allocates both GRSurfaceDrm
dumb buffers, then `ret = legacy_modeset ? 0 : Initdisplay(DRM_MAIN);` —
on −1 it prints `Failed to init display` and returns nullptr.

## Q2 — Why MT6991 mtk_drm produces 0

- **`capabilities`/`primary_smart_plane_id` is a Qualcomm SDE invention.**
  The whole twrpminui backend is copied from CAF/CLO minui: the file embeds
  the SDE kernel's `enum sde_rm_topology_name` comment block verbatim, parses
  `SDE_SPR_INIT_CFG_V1/V2` and `SDE_DEMURA_INIT_CFG_*` CRTC properties, and
  reads `vendor.display.enable_spr`. None of these exist off Snapdragon.
- **MediaTek planes carry only standard properties.** Mainline v6.6
  `drivers/gpu/drm/mediatek/mtk_drm_plane.c` (fetched): `mtk_plane_init()`
  calls `drm_universal_plane_init()` with a caller-passed type (one
  `DRM_PLANE_TYPE_PRIMARY` per CRTC, the rest OVERLAY) and adds only standard
  properties (rotation; zpos/alpha come from DRM core). Grep of the file for
  `capabilities`: **zero hits** — the property is never created. The device's
  vendor 6.6.118 kernel is a fork of the same driver lineage (device dmesg:
  `Loading module /lib/modules/mediatek-drm.ko`, `[DISP]mtk_drm_probe`), and
  nothing in MTK's driver history adds an SDE-style text-blob property.
- Therefore gate 2 fails for 100% of planes ⇒ `selected = 0 ≠ 2` ⇒ −1.
  The bootloader-splash / "primary plane busy" / "CRTC inactive" family of
  explanations does **not** apply to this code path: fb_id, plane state and
  CRTC active state are never consulted by the selection loop.
- Why everything else works on the same kernel: the classic minui in the
  *same repo* (`minui/graphics_drm.cpp`) uses legacy `drmModeSetCrtc()` with
  the CRTC's framebuffer — no plane logic at all. Skyward and stock recovery
  likewise drive the panel through standard KMS interfaces. Piano (Pad 8 Pro,
  SM8750) works with the *same* GUI2 binary stack because SDE really does
  publish `mode_properties` + `capabilities`.

## Q3 — Fixes, ranked

### Fix 1 (recommended, repack-level): force `legacy_modeset` in libtwrpminui.so

`MinuiBackendDrm::Init()` (~line 1212):

```cpp
legacy_modeset = version->name && !strcmp(version->name, "virtio_gpu");
```

Legacy mode is a complete, self-contained path that **skips Initdisplay
entirely** (`ret = legacy_modeset ? 0 : Initdisplay(...)`) and never touches
`plane_res`:
- `Blank()` → `SetLegacyCrtc()` = plain `drmModeSetCrtc(fd, crtc, fb, 0,0, &conn, 1, &mode)`;
- `Present()` → `drmModePageFlip()` with a built-in fallback to blocking
  `SetLegacyCrtc()` on failure.
This is exactly how the classic minui drives MTK. **Patch surface:** one
branch in `system/lib64/twrp16/libtwrpminui.so` — locate the `strcmp` against
the `"virtio_gpu"` rodata string (present in the shipped .so) inside
`MinuiBackendDrm::Init()` and make the assignment unconditional-true.
Caveats: fast-mode/SPR stays inert (their blobs are only created inside
Initdisplay — consistent); `twrp.drm.direct_scanout` defaults true, fine.
Risk is presentational (page-flip vsync behaviour), not structural.

### Fix 2 (clean, needs a build): teach Initdisplay the standard `type` property

In the selection loop, when a plane has no `capabilities` property, fall back
to the standard DRM `type` property == `DRM_PLANE_TYPE_PRIMARY`; **and**
relax the hard equality — accept `selected >= 1` and clamp
`number_of_lms = selected` — because MTK provides exactly **one**
primary-typed plane per CRTC while the code demands `== 2` (an SDE dual-pipe
assumption). With the clamp, SetupPipeline programs a single full-screen
plane, the standard configuration. Only `libtwrpminui` needs rebuilding, but
that still requires a synced twrp-16.0 tree + Soong — hours, not minutes.
This is also the upstreamable form of the fix.

### Fix 3: full YARP rebuild with Fix 2's patch in the device tree

Same source change carried through the normal build (e.g. in the tree's
`patches/` mechanism). Slowest, best provenance.

### Dead ends (verified — do not spend time)

- **fbdev fallback exists in code but not on this device.** libgui2 imports
  the **no-arg** `gr_init()` (`_Z7gr_initv`), which uses
  `default_backends = { DRM, FBDEV }` (twrpminui/graphics.cpp:61–64) and
  *does* try FBDEV after DRM fails. `MinuiBackendFbdev::Init()` opens
  `/dev/graphics/fb0` (20 × 100 ms retries) — but the captured device dmesg
  contains **zero fb0/fbdev registration lines**; this vendor kernel's
  mediatek-drm registers no fbdev emulation, and the fbdev open-failure path
  is silent in source (plain `return nullptr`), exactly matching the
  recovery.log, which repeats the DRM failure with no fbdev output at all.
  No runtime switch can create fb0; it is compiled into mediatek-drm.ko.
- **No property or BoardConfig knob affects plane selection.** Properties
  actually read by the backend: `vendor.display.enable_spr`,
  `vendor.display.enable_spr_bypass`, `twrp.drm.fast_mode`,
  `twrp.drm.direct_scanout`, `twrp.drm.stats`, `ro.minui.pixel_format`,
  `ro.minui.overscan_percent`, `ro.minui.default_rotation`,
  `persist.twrp.rotation`. Only display-related build-time ifdefs:
  `TW_DRM_TWO_STAGE_MODESET` (fast-mode only) and the `RECOVERY_*` pixel
  formats. Nothing else exists to turn.
- **No runtime action can help.** DRM properties are created by the kernel
  driver at plane-init time; no module load, sysfs write or splash-release
  can synthesize a `capabilities` property on mtk planes.
- **Swapping in the classic `libminui`** is not viable: libgui2 links
  libtwrpminui's GUI2-specific exports (damage tracking etc.); not ABI-compatible.

## Q4 — Piano vs turner tree comparison

Grepped both local trees' BoardConfig.mk / rc / props for DRM/fb/minui/plane
settings:

- **Piano** (working GUI2, SM8750): no DRM, fbdev, plane or minui flags at
  all. Display-relevant entries are only theme/brightness
  (`TW_THEME := landscape_hdpi`, `TW_BRIGHTNESS_PATH := /sys/class/backlight/…`).
- **Turner**: likewise none (`TW_THEME := portrait_hdpi`, `TW_FRAMERATE := 165`,
  brightness via `/sys/class/leds/lcd-backlight/brightness`).

The working/broken difference is **not configuration — it is silicon**:
piano's SDE kernel driver publishes the vendor properties this backend
requires; turner's mtk_drm does not and cannot.

## Evidence index

- TWRP-Test/android_bootable_recovery @ twrp-16.0 (raw fetches):
  `twrpminui/graphics_drm.cpp` (Initdisplay :713–807 active copy,
  is_primary_plane :161–185, Init :1170–1300, Blank/Present/SetLegacyCrtc),
  `twrpminui/graphics_drm.h` (:35 DEFAULT_NUM_LMS, :254 default member),
  `twrpminui/graphics.cpp` (:61–64 default_backends, :436–500 gr_init),
  `twrpminui/graphics_fbdev.cpp` (:105–115 silent fb0 open failure),
  `minui/graphics_drm.cpp` (classic legacy-SetCrtc backend, same repo).
- Payload binaries: `stage1/twrp_payload/system/lib64/libtwrpminui.so`
  (contains the log string, MinuiBackendDrm/Fbdev symbols, "virtio_gpu"),
  `libgui2.so` (prints the failure line; imports `_Z7gr_initv`).
  Shipped image path: `stage4/f1_new/system/lib64/twrp16/libtwrpminui.so`,
  sha256 `0615820440c694fe840eb9ad58dcd7dcd22818dde5f0efa78434e414c1d7d269`.
- torvalds/linux v6.6 `drivers/gpu/drm/mediatek/mtk_drm_plane.c`
  (drm_universal_plane_init :310; no `capabilities` property).
- Device logs: `~/workspace/user/files/recovery_24_b4b3.log` (failure cycle,
  pid 389→420→…, no fbdev lines), `~/workspace/user/files/dmesg-v2_22_tw2g.txt`
  (mediatek-drm.ko load + probe; no fb0 registration).
