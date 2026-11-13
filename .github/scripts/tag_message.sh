#!/bin/bash
# Annotated tag message (what GitHub's Tags page shows): plain text from both changelogs.
# usage (from the repo root): [CL=CHANGELOG-orangefox] tag_message.sh <version> <firmware>
set -euo pipefail
ver=$1 fw=$2 cl=${CL:-CHANGELOG}
name=TWRP; [ "$cl" = CHANGELOG-orangefox ] && name=OrangeFox
plain() { awk -v v="$ver" '/^## /{p = ($2 == v); next} p' "$1" | sed -e 's/^### //' -e 's/\*\*//g' -e '/./,$!d' | cat -s; }
id=$(plain "$cl.md")
en=$(plain "$cl.en.md")
if [ -z "$id" ] || [ -z "$en" ]; then
  echo "::error title=CHANGELOG::no '## $ver' section in both $cl.md and $cl.en.md" >&2
  exit 1
fi
printf '%s turner %s · firmware %s\n\n%s\n\nEnglish\n\n%s\n' "$name" "$ver" "$fw" "$id" "$en"
