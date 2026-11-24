#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
# dev/test_kit.sh - unpack a release package and install it into a scratch area, as a GitHub
# user would (no driver, no root). Linux/WSL:   bash dev/test_kit.sh dist/pi-GPIBTerm-X.tar.gz
set -euo pipefail
KIT="$(realpath "$1")"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
cd "$T"
tar xzf "$KIT"
D="$(find . -maxdepth 1 -type d -name 'pi-GPIBTerm-*' | head -1)"
[ -n "$D" ] || { echo "FAIL  package has no pi-GPIBTerm-<version> folder"; exit 1; }
echo "unpacked: $D ($(find "$D" -type f | wc -l) files)"
if grep -rl $'\r' "$D"/*.sh "$D"/pi/*.py "$D"/pi/*.sh "$D"/pi/examples/*.bas "$D"/pi/instruments/*/*.py "$D"/pi/instruments/*/examples/*.bas >/dev/null 2>&1; then
  echo "FAIL  CRLF line endings in the package"; exit 1
fi
mkdir -p home
bash "$D/install.sh" --no-driver --prefix "$T/opt/pi-gpibterm" --bindir "$T/bin" --home "$T/home" | tail -6
out="$("$T/bin/hpib" --sim -c 'ASK 723, "H1"')"
case "$out" in *E+0*) echo "PASS  the installed hpib answers: $out" ;; *) echo "FAIL  hpib: $out"; exit 1 ;; esac
"$T/bin/pi-gpibterm" --version
echo "PASS  release package installs and runs"
