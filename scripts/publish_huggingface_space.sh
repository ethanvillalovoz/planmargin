#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(dirname "$script_dir")
hf_cli=${HF_CLI:-hf}
space_id=${PLANMARGIN_SPACE_ID:-ethanvillalovoz/planmargin}

if ! command -v "$hf_cli" >/dev/null 2>&1; then
  echo "Hugging Face CLI not found. Install hf or set HF_CLI to its path." >&2
  exit 1
fi

staging_dir=$(mktemp -d "${TMPDIR:-/tmp}/planmargin-space.XXXXXX")
trap 'rm -rf "$staging_dir"' EXIT HUP INT TERM

npm --prefix "$project_root/web/debugger" ci
npm --prefix "$project_root/web/debugger" run check

cp -R "$project_root/web/debugger/dist/planmargin-debugger/browser/." "$staging_dir/"
cp "$project_root/deploy/huggingface-space/README.md" "$staging_dir/README.md"

"$hf_cli" upload "$space_id" "$staging_dir" . \
  --type space \
  --commit-message "Deploy PlanMargin aggregate workbench"
