#!/bin/bash
# Release notes for one version, from $CL.md (Indonesian) + $CL.en.md (English).
# usage (from the repo root): [CL=CHANGELOG-orangefox] release_notes.sh <version> <firmware> <image sha256> <owner/repo>
set -euo pipefail
ver=$1 fw=$2 sha=$3 repo=$4 cl=${CL:-CHANGELOG}
case $cl in
  CHANGELOG-orangefox) name=OrangeFox bat=1-PASANG-ORANGEFOX.bat doc=docs/orangefox/pasang ;;
  *) name=TWRP bat=1-PASANG-TWRP.bat doc=docs/pasang ;;
esac
sec() { awk -v v="$ver" '/^## /{p = ($2 == v)} p' "$1"; }
id=$(sec "$cl.md")
en=$(sec "$cl.en.md")
if [ -z "$id" ] || [ -z "$en" ]; then
  echo "::error title=CHANGELOG::no '## $ver' section in both $cl.md and $cl.en.md" >&2
  exit 1
fi
cat <<EOF
**$ver** · firmware \`$fw\` · Xiaomi 14T Pro (turner)

$id

**Pasang:** ekstrak zip ke folder \`platform-tools\`, jalankan \`$bat\`, atau flash zip-nya langsung di recovery. Lihat [panduan](https://github.com/$repo/blob/HEAD/$doc.md).

<details><summary>English</summary>

$en

**Install:** extract the zip into \`platform-tools\` and run \`$bat\`, or flash the zip straight in recovery. See the [guide](https://github.com/$repo/blob/HEAD/$doc.en.md).

</details>

---
$name image sha256 \`$sha\` · Cek keaslian / authenticity: https://github.com/$repo/attestations

⚠️ Pra-rilis — backup data dulu. / Pre-release — back up your data first.
EOF
