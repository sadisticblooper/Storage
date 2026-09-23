#!/usr/bin/env bash
# Shared helpers for APK analysis scripts.
# Requires: python3, apktool.jar, baksmali.jar, jadx (or jadx CLI jar).
set -uo pipefail

TOOLS_DIR="${TOOLS_DIR:-$PWD/tools}"
WORK_DIR="${WORK_DIR:-$PWD/work}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

need_file() { [ -f "$1" ] || die "missing required file: $1"; }

# Resolve a tool, preferring an explicit env override.
find_jar() {
  local name="$1"
  if [ -n "${!2:-}" ]; then echo "${!2}"; return; fi
  local hit
  hit="$(find "$TOOLS_DIR" -maxdepth 2 -iname "$name" 2>/dev/null | head -n1)"
  [ -n "$hit" ] || die "could not locate $name under $TOOLS_DIR (set $2)"
  echo "$hit"
}

run_apktool() {
  local jar; jar="$(find_jar 'apktool*.jar' APKTOOL_JAR)"
  java -jar "$jar" "$@"
}

run_baksmali() {
  local jar; jar="$(find_jar 'baksmali*.jar' BAKSMALI_JAR)"
  java -jar "$jar" "$@"
}

# apktool needs the framework cached; harmless if already present.
ensure_framework() {
  run_apktool if framework-res.apk >/dev/null 2>&1 || true
}
