#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
F=$ROOT/thirdparty/fex
P=$ROOT/scripts/patches
RAW=$ROOT/host_tests/fixtures/fex-vm-aggregate.original.patch
PURE=$P/fex-windows-vm-contract.patch
WORK=$(mktemp -d "${TMPDIR:-/tmp}/fex-vm-aggregate-proof.XXXXXX")
trap 'rm -rf -- "$WORK"' EXIT

sha256_expect() {
  local file=$1 expected=$2 actual
  actual=$(sha256sum "$file" | awk '{print $1}')
  test "$actual" = "$expected" || { echo "hash mismatch: $file: $actual != $expected" >&2; exit 1; }
}
manifest() {
  local d=$1 out=$2
  (cd "$d" && find . -type f ! -name '*.orig' ! -name '*.rej' -print0 | sort -z | xargs -0 sha256sum) > "$out"
}
regular() {
  local d=$1 p=$2 fuzz=${3:-}
  local opt=(); test -z "$fuzz" || opt+=(--fuzz="$fuzz")
  if ! patch -d "$d" -p1 -R --dry-run -s "${opt[@]}" < "$p" >/dev/null 2>&1; then
    patch -d "$d" -p1 --dry-run --batch -s "${opt[@]}" < "$p" >/dev/null
    patch -d "$d" -p1 --batch -s --no-backup-if-mismatch "${opt[@]}" < "$p"
  fi
}
select_patch() {
  local input=$1 output=$2; shift 2
  python3 - "$input" "$output" "$@" <<'PY'
import re, sys
from pathlib import Path
src, dst, *wanted = sys.argv[1:]
text = Path(src).read_text()
# Preserve complete per-file chunks for patches with or without diff --git lines.
if re.search(r'^diff --git ', text, re.M):
    chunks = re.split(r'(?=^diff --git )', text, flags=re.M)
else:
    chunks = re.split(r'(?=^--- (?:a|base)/)', text, flags=re.M)
out=[]
for chunk in chunks:
    match=re.search(r'^--- (?:a|base)/([^\n]+)$', chunk, re.M)
    if match and match.group(1) in wanted:
        out.append(chunk)
seen={re.search(r'^--- (?:a|base)/([^\n]+)$', c, re.M).group(1) for c in out}
if seen != set(wanted):
    raise SystemExit(f'section mismatch for {src}: got {sorted(seen)}, wanted {sorted(wanted)}')
Path(dst).write_text(''.join(out))
PY
}
phase() {
  # Exercise the production script itself, not a duplicated patch-order model.
  local d=$1 diag=$2
  FEX_SRC="$d" SCRIPT_DIR="$ROOT/scripts" FEX_EXACTSTORE_DIAGNOSTICS="$diag" \
    FEX_STEAM_DIAG_PATCHES=0 bash "$WORK/production-phase.sh"
}
aggregate_reference() {
  local d=$1 diag=$2 q=$WORK/sections
  mkdir -p "$q"
  # Five disjoint legacy prerequisites. Raw aggregate already embeds both
  # Module.cpp unaligned overlays.
  for PATCH in \
    fex-missing-includes.patch \
    fex-winapi-locale-stubs.patch \
    fex-wow64-lookup-cache-commit.patch \
    fex-wow64-dynamic-l1-recommit.patch \
    fex-arm64ec-lookup-cache-commit.patch; do
    regular "$d" "$P/$PATCH"
  done
  regular "$d" "$RAW" 0
  patch -d "$d" -p1 -R --dry-run -s < "$P/fex-arm64ec-unaligned-diagnostics.patch" >/dev/null
  patch -d "$d" -p1 -R --dry-run -s < "$P/fex-windows-unaligned-stderr.patch" >/dev/null

  regular "$d" "$P/fex-wow64-exact-store.patch"
  test "$diag" = 0 || regular "$d" "$P/fex-wow64-exact-store-diagnostics.patch"

  # Restore precisely the predecessor sections absent from the raw aggregate.
  select_patch "$P/fex-wow64-synthetic-return.patch" "$q/synthetic-common.patch" \
    Source/Windows/Common/CallRetStack.h
  regular "$d" "$q/synthetic-common.patch"
  select_patch "$P/fex-windows-native-callret-fault.patch" "$q/native-common.patch" \
    Source/Windows/Common/CallRetStack.h
  regular "$d" "$q/native-common.patch"
  regular "$d" "$P/fex-windows-crt-file-open.patch"
  select_patch "$P/fex-windows-jit-symbols.patch" "$q/jit-symbols-nonmodule.patch" \
    FEXCore/Source/Common/JitSymbols.cpp
  regular "$d" "$q/jit-symbols-nonmodule.patch"
  regular "$d" "$P/fex-windows-jit-cost.patch"
  select_patch "$P/fex-windows-file-loading.patch" "$q/file-loading-nonmodule.patch" \
    FEXCore/Source/Utils/FileLoading.cpp \
    Source/Common/Config.cpp \
    FEXCore/Source/Interface/Config/Config.cpp
  regular "$d" "$q/file-loading-nonmodule.patch"

  regular "$d" "$P/fex-wow64-strict-mul24.patch"
  regular "$d" "$P/fex-pop-memory-precise-stack.patch" 0
  regular "$d" "$P/fex-memory-offset-fault-boundary.patch" 0
}

sha256_expect "$RAW" 86009659a7f61071aa0ab83b92e0701479b28b0ab7e18e5a5eb788fd17f28111
sha256_expect "$PURE" 601504cebc03e7faec3b4f9333bb7b6dfcbc42b905b899596567f2e6670682aa
test "$(git -C "$F" rev-parse HEAD)" = 86ff33bbe299cd8959a6610198c169b67ec419db
python3 - "$ROOT/scripts/build_fex.sh" "$WORK/production-phase.sh" <<'PYCODE'
from pathlib import Path
import sys
source=Path(sys.argv[1]).read_text()
start=source.index('patched_source=0\n')
end=source.index('prepare_mul24_cache() {', start)
Path(sys.argv[2]).write_text('set -euo pipefail\nlog() { :; }\nerr() { echo "$*" >&2; exit 1; }\n'+source[start:end])
PYCODE

for diag in 0 1; do
  prod=$WORK/prod-$diag; ref=$WORK/ref-$diag
  mkdir "$prod" "$ref"
  git -C "$F" archive HEAD | tar -C "$prod" -xf -
  git -C "$F" archive HEAD | tar -C "$ref" -xf -

  phase "$prod" "$diag"
  manifest "$prod" "$WORK/prod-$diag.first.sha256"
  phase "$prod" "$diag"
  manifest "$prod" "$WORK/prod-$diag.second.sha256"
  cmp "$WORK/prod-$diag.first.sha256" "$WORK/prod-$diag.second.sha256"
  test -z "$(find "$prod" -name '*.rej' -print -quit)"
  patch -d "$prod" -p1 -R --dry-run -s --fuzz=0 < "$PURE" >/dev/null

  aggregate_reference "$ref" "$diag"
  manifest "$ref" "$WORK/ref-$diag.sha256"
  test -z "$(find "$ref" -name '*.rej' -print -quit)"
  cmp "$WORK/prod-$diag.second.sha256" "$WORK/ref-$diag.sha256"
  echo "PASS diag=$diag manifest=$(sha256sum "$WORK/ref-$diag.sha256" | awk '{print $1}')"
done
