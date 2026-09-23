#!/usr/bin/env bash
# Repack an APK after apktool decode + edits, then align and sign it.
#
# Usage:
#   repack.sh <decoded_dir> <out.apk> [--keystore FILE] [--alias NAME]
#
# Signing:
#   If --keystore is omitted, a throwaway debug keystore is generated. The
#   resulting APK is installable for testing but is NOT publishable — treat
#   debug-signed output as local-only.
#
# Requires: apktool.jar, and either Android build-tools (zipalign/apksigner)
# on PATH or the ANDROID_HOME SDK layout.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$HERE/common.sh"

DECODED_DIR="${1:-}"
OUT_APK="${2:-}"
[ -n "$DECODED_DIR" ] || die "usage: repack.sh <decoded_dir> <out.apk> [--keystore F --alias N]"
[ -n "$OUT_APK" ] || die "usage: repack.sh <decoded_dir> <out.apk> [--keystore F --alias N]"
shift 2 || true

KEYSTORE=""
ALIAS="loaderdebug"
PASS="android"
STRIP_ATTRS=""

while [ $# -gt 0 ]; do
  case "$1" in
    --keystore)   KEYSTORE="$2"; shift 2 ;;
    --alias)      ALIAS="$2";    shift 2 ;;
    --pass)       PASS="$2";     shift 2 ;;
    --strip-attrs) STRIP_ATTRS="$2"; shift 2 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[ -d "$DECODED_DIR" ] || die "decoded dir not found: $DECODED_DIR"

MANIFEST="$DECODED_DIR/AndroidManifest.xml"
[ -f "$MANIFEST" ] || die "no AndroidManifest.xml in $DECODED_DIR"

# --- strip attributes aapt2 cannot resolve ------------------------------------
# Newer platform attributes (e.g. android:pageSizeCompat, added in API 36) are
# not in apktool's bundled framework, and aapt2 hard-fails the whole build on
# them. Stripping is opt-in and reported, never silent.
if [ -n "$STRIP_ATTRS" ]; then
  IFS=',' read -r -a _attrs <<< "$STRIP_ATTRS"
  for attr in "${_attrs[@]}"; do
    attr="$(echo "$attr" | xargs)"   # trim
    [ -n "$attr" ] || continue
    if grep -q "android:${attr}=" "$MANIFEST"; then
      log "stripping unsupported attribute android:${attr}"
      # match both "android:attr="..." " and a bare android:attr="..."
      perl -0pi -e "s/\\s+android:${attr}=\"[^\"]*\"//g" "$MANIFEST"
    else
      warn "attribute android:${attr} not present, nothing to strip"
    fi
  done
fi

# --- locate build-tools -------------------------------------------------------
find_bt() {
  local tool="$1"
  if command -v "$tool" >/dev/null 2>&1; then command -v "$tool"; return; fi
  local root="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  [ -n "$root" ] || return 1
  find "$root/build-tools" -maxdepth 2 -name "$tool" 2>/dev/null | sort -V | tail -n1
}

ZIPALIGN="$(find_bt zipalign || true)"
APKSIGNER="$(find_bt apksigner || true)"

# --- build --------------------------------------------------------------------
UNSIGNED="$(mktemp -u /tmp/loader-unsigned-XXXXXX.apk)"
log "rebuilding $DECODED_DIR"
BUILD_LOG="$(mktemp)"
if ! run_apktool b "$DECODED_DIR" -o "$UNSIGNED" 2>&1 | tee "$BUILD_LOG"; then
  if grep -q "attribute android:.* not found" "$BUILD_LOG"; then
    warn "aapt2 rejected a platform attribute that apktool's framework does not know."
    warn "Re-run with: --strip-attrs <name[,name...]>  (e.g. --strip-attrs pageSizeCompat)"
    grep -o "attribute android:[A-Za-z0-9_]* not found" "$BUILD_LOG" | sort -u >&2
  fi
  die "apktool build failed (see log above)"
fi
rm -f "$BUILD_LOG"

STAGE="$UNSIGNED"
if [ -n "$ZIPALIGN" ]; then
  ALIGNED="$(mktemp -u /tmp/loader-aligned-XXXXXX.apk)"
  log "zipalign"
  "$ZIPALIGN" -p -f 4 "$UNSIGNED" "$ALIGNED" || die "zipalign failed"
  STAGE="$ALIGNED"
else
  warn "zipalign not found; skipping alignment (APK may still install)"
fi

# --- sign ---------------------------------------------------------------------
if [ -z "$KEYSTORE" ]; then
  KEYSTORE="$WORK_DIR/debug.keystore"
  mkdir -p "$WORK_DIR"
  if [ ! -f "$KEYSTORE" ]; then
    log "generating throwaway debug keystore at $KEYSTORE"
    keytool -genkeypair -v \
      -keystore "$KEYSTORE" -storepass "$PASS" -keypass "$PASS" \
      -alias "$ALIAS" -keyalg RSA -keysize 2048 -validity 10000 \
      -dname "CN=Loader Debug, OU=CI, O=Local, L=NA, S=NA, C=NA" \
      >/dev/null 2>&1 || die "keytool failed"
  fi
fi
need_file "$KEYSTORE"

# jarsigner is not always on PATH even when a JDK is present; look next to java.
JARSIGNER="$(command -v jarsigner || true)"
if [ -z "$JARSIGNER" ]; then
  _java="$(command -v java || true)"
  if [ -n "$_java" ]; then
    _cand="$(dirname "$(readlink -f "$_java")")/jarsigner"
    [ -x "$_cand" ] && JARSIGNER="$_cand"
  fi
fi

if [ -n "$APKSIGNER" ]; then
  log "signing (apksigner) -> $OUT_APK"
  "$APKSIGNER" sign \
    --ks "$KEYSTORE" --ks-pass "pass:$PASS" --key-pass "pass:$PASS" \
    --ks-key-alias "$ALIAS" --out "$OUT_APK" "$STAGE" || die "apksigner failed"
  "$APKSIGNER" verify --print-certs "$OUT_APK" | head -n 5 || true
elif [ -n "$JARSIGNER" ]; then
  warn "apksigner not found; falling back to jarsigner (v1 signing only)"
  warn "v1-only APKs are rejected on Android 11+ targets in many cases"
  cp "$STAGE" "$OUT_APK"
  "$JARSIGNER" -keystore "$KEYSTORE" -storepass "$PASS" -keypass "$PASS" \
    -sigalg SHA256withRSA -digestalg SHA-256 "$OUT_APK" "$ALIAS" \
    || die "jarsigner failed"
else
  die "no signing tool available (need apksigner from Android build-tools, or jarsigner from a JDK)"
fi

log "done: $OUT_APK"
sha256sum "$OUT_APK" 2>/dev/null || true
