#!/usr/bin/env python3
"""Copy missing git-tracked files from pinned upstream tree. No build or flashing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

EXPECTED_DTB_SHA256 = "4f985cad82176ea746ffef6aa960269ef0aec410f294bc157bd766ad74f49bc0"
PRESERVE = {"README.md", "README.en.md"}
SKIP_PREFIXES = (".github/workflows/",)

def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args]).decode().strip()

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def matches(left, right):
    if left.is_symlink() or right.is_symlink():
        return left.is_symlink() and right.is_symlink() and os.readlink(left) == os.readlink(right)
    return left.is_file() and right.is_file() and sha256(left) == sha256(right)

def import_files(source, target, expected_commit, report_path):
    source, target = source.resolve(), target.resolve()
    actual = git(source, "rev-parse", "HEAD")
    if actual != expected_commit:
        raise ValueError(f"unpinned source commit: {actual}; expected {expected_commit}")
    names = subprocess.check_output(["git", "-C", str(source), "ls-files", "-z"]).decode().split("\0")
    names = [name for name in names if name]
    source_modules = sum(name.startswith("recovery/root/lib/modules/") and name.endswith(".ko") for name in names)
    if source_modules < 250:
        raise ValueError(f"upstream modules unexpectedly incomplete: {source_modules}")
    if sha256(source / "prebuilt/dtb") != EXPECTED_DTB_SHA256:
        raise ValueError("upstream DTB is not the DTB extracted from working Skyward images")
    copied, preserved, excluded = [], [], []
    for name in names:
        if name.startswith(SKIP_PREFIXES):
            excluded.append(name)
            continue
        src, dst = source / name, target / name
        if dst.exists() or dst.is_symlink():
            if matches(src, dst):
                continue
            if name in PRESERVE:
                preserved.append(name)
                continue
            raise ValueError(f"refusing to overwrite modified destination: {name}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            os.symlink(os.readlink(src), dst)
        else:
            shutil.copy2(src, dst)
        if not matches(src, dst):
            raise ValueError(f"copy verification failed: {name}")
        copied.append(name)
    missing = [name for name in names if name not in excluded and not (
        (target / name).exists() or (target / name).is_symlink())]
    if missing:
        raise ValueError(f"missing upstream files after copy: {missing[:10]}")
    target_modules = sum((target / name).is_file() for name in names if
        name.startswith("recovery/root/lib/modules/") and name.endswith(".ko"))
    if source_modules != target_modules:
        raise ValueError(f"modules missing: {target_modules} of {source_modules}")
    if sha256(target / "prebuilt/dtb") != EXPECTED_DTB_SHA256:
        raise ValueError("destination DTB does not match working Skyward")
    result = {
        "device": "Redmi K Pad / turner / MT6991",
        "source_repository": "GQiangZI/twrp_device_xiaomi_turner",
        "source_commit": actual,
        "source_tracked_files": len(names),
        "new_files_copied": len(copied),
        "preserved_edited_files": preserved,
        "excluded_legacy_workflows": excluded,
        "verified_kernel_modules": target_modules,
        "dtb_sha256": EXPECTED_DTB_SHA256,
        "status": "SOURCE_IMPORT_ONLY_NOT_BUILT_NOT_FLASH_TESTED"
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("target", type=Path)
    p.add_argument("--commit", required=True)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(import_files(a.source, a.target, a.commit, a.report), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
