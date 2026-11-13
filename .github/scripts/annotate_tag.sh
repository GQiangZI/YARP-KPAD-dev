#!/bin/bash
# Turn release tag <version> into an annotated tag on the same commit, with the changelog as its
# message: GitHub's Tags page shows an annotated tag's message instead of the commit message.
# usage (from the repo root): annotate_tag.sh <version> <firmware> <owner/repo>
set -euo pipefail
ver=$1 fw=$2 repo=$3
ref=$(gh api "repos/$repo/git/ref/tags/$ver" --jq '.object.type + " " + .object.sha')
sha=${ref#* }
[ "${ref%% *}" = tag ] && sha=$(gh api "repos/$repo/git/tags/$sha" --jq .object.sha)
msg=$(mktemp)
"$(dirname "$0")/tag_message.sh" "$ver" "$fw" > "$msg"
obj=$(gh api "repos/$repo/git/tags" -f tag="$ver" -F message=@"$msg" -f object="$sha" -f type=commit --jq .sha)
gh api -X PATCH "repos/$repo/git/refs/tags/$ver" -f sha="$obj" -F force=true >/dev/null
echo "::notice title=Tag $ver::annotated tag on ${sha:0:7}"
