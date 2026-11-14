#!/usr/bin/env python3
"""G3 (stage 6): closure audits against the PURE OS4-stock baseline.
Hybrid world = stage4/f0_new (byte-identical F0, shared with v2.1) +
stage6/f1_v22. Expected: result identical to audit4b (v2.1).

Worlds (overlay, later fragment wins):
  hybrid   = stage4/f0_new + stage4/f1_v21
  os4stock = stage1/os4_f0 + stage1/os4_f1

Starts: system/bin/init and system/bin/servicemanager.
NOTE on hwservicemanager: the OS4 stock ramdisk contains NO
system/bin/hwservicemanager at all (nor vndservicemanager) — HAL
registration in this layout is done by the stock servicemanager binary
(F0). hwservicemanager existed only in v5iso's merged tree (TWRP build,
137,384 B), and it was that TWRP binary + TWRP libvintf pairing that
carried the 3 unresolved android::base::Join instantiations. This audit
therefore (a) proves hwservicemanager/vndservicemanager are absent from
both v2 and pure stock, and (b) audits servicemanager's closure, which
must be winner-identical and unresolved-identical between the worlds.
"""
import importlib.util, os, sys

H = os.path.expanduser
S1 = H("~/workspace/yarp-hybrid/stage1")
S4 = H("~/workspace/yarp-hybrid/stage4")
S6 = H("~/workspace/yarp-hybrid/stage6")

spec = importlib.util.spec_from_file_location(
    "symaudit", os.path.join(S1, "_src", "audit-v5", "symbol-audit-v5.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
World = mod.World

worlds = {
    "hybrid": World("hybrid", "overlay", [os.path.join(S4, "f0_new"),
                                          os.path.join(S6, "f1_v22")]),
    "os4stock": World("os4stock", "overlay", [os.path.join(S1, "os4_f0"),
                                              os.path.join(S1, "os4_f1")]),
}

ok = True
ROOTS = {"hybrid": [os.path.join(S4, "f0_new"), os.path.join(S6, "f1_v22")],
         "os4stock": [os.path.join(S1, "os4_f0"), os.path.join(S1, "os4_f1")]}
for probe in ("system/bin/hwservicemanager", "system/bin/vndservicemanager"):
    for name, roots in ROOTS.items():
        present = any(os.path.lexists(os.path.join(r, probe)) for r in roots)
        print(f"absence check: {probe} in {name}: {'PRESENT' if present else 'absent'}")
        if present:
            ok = False


def unresolved(res):
    return {(rel, sym) for (rel, sym), r in res.items()
            if r["status"] in ("unresolved", "version-mismatch")}


for start in ("system/bin/init", "system/bin/servicemanager"):
    mod.START_REL = start
    print("=" * 78)
    print(f"closure from {start}")
    data = {}
    for name, w in worlds.items():
        order, missing, res = mod.audit(w, name)
        data[name] = (order, missing, res)
        print(f"  {name}: closure files={len(order)} missing_needed={missing} "
              f"unresolved={len(unresolved(res))}")
    ho, _, hres = data["hybrid"]
    so, _, sres = data["os4stock"]
    hw, sw = worlds["hybrid"], worlds["os4stock"]
    only_h = sorted(set(ho) - set(so))
    only_s = sorted(set(so) - set(ho))
    print(f"  closure file set: only-in-hybrid={only_h} only-in-stock={only_s}")
    diffs = []
    for rel in dict.fromkeys(ho + so):
        a, b = hw.sha(rel), sw.sha(rel)
        if a != b:
            diffs.append((rel, (a or "-")[:12], (b or "-")[:12]))
    print(f"  winner content diffs hybrid-vs-stock: {len(diffs)}")
    for d in diffs:
        print(f"    {d[0]}: hybrid={d[1]} stock={d[2]}")
    new_unres = unresolved(hres) - unresolved(sres)
    gone_unres = unresolved(sres) - unresolved(hres)
    print(f"  NEW unresolved in hybrid vs stock: {sorted(new_unres)}")
    print(f"  resolved-away vs stock: {sorted(gone_unres)}")
    for name, res in (("hybrid", hres), ("os4stock", sres)):
        lv = sorted(sym for (rel, sym), r in res.items()
                    if rel == "system/lib64/libvintf.so"
                    and r["status"] in ("unresolved", "version-mismatch"))
        if lv:
            print(f"  {name}: libvintf.so unresolved in this closure: {lv}")
    if only_h or only_s or diffs or new_unres or gone_unres:
        ok = False
print("=" * 78)
print("G3 RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
