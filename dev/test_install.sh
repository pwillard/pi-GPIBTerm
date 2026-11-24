#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
# dev/test_install.sh - install pi-GPIBTerm into a scratch area (no driver, no root) and
# exercise the installed commands with the simulator. Run on Linux/WSL from the project folder:
#     bash dev/test_install.sh
# shellcheck disable=SC2034   # 'out' is used inside the ok '...' test strings
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/home"
pass=0; fail=0
ok() { if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
P="$T/opt/pi-gpibterm"
W="$T/home/pi-gpibterm"
OPTS=(--no-driver --prefix "$P" --bindir "$T/bin" --home "$T/home")

# an earlier 1.x installation (hp3478a-gpib) to be replaced: old commands and ~/hp3478a
mkdir -p "$T/opt/hp3478a" "$T/bin" "$T/home/hp3478a/backups"
echo "1.6.0 installed" > "$T/opt/hp3478a/INSTALLED"
printf '#!/bin/sh\n# hp3478a - menu (hp3478a-gpib 1.6.0)\n' > "$T/bin/hp3478a"
printf '#!/bin/sh\n# old menu\n' > "$T/home/hp3478a/menu"
printf 'ADDRESS=22\n' > "$T/home/hp3478a/hp3478a.conf"
cp "$SRC/dev/sample_calram.txt" "$T/home/hp3478a/backups/calram_test.txt"

out="$(bash "$SRC/install.sh" "${OPTS[@]}" 2>&1)"
ok "install.sh finishes" '[[ "$out" == *"Done - pi-GPIBTerm"* ]]'
ok "core programs in the prefix" '[ -f "$P/hpibterm.py" ] && [ -f "$P/gpibterm_menu.py" ] && [ -f "$P/examples/bus_tour.bas" ]'
ok "HP 3478A module in the prefix" '[ -f "$P/instruments/hp3478a/module.py" ] && [ -f "$P/instruments/hp3478a/hp3478a_cal.py" ] && [ -f "$P/instruments/hp3478a/examples/3478a_calsave.bas" ]'
ok "no instrument programs in the core" '! ls "$P"/*3478* >/dev/null 2>&1'
ok "guides in prefix/docs (PDF and text)" '[ -f "$P/docs/HP-IB-Terminal-Guide.pdf" ] && [ -f "$P/docs/HP-IB-Terminal-Guide.md" ] && [ -f "$P/docs/pi-GPIBTerm-Setup-Guide.md" ] && [ -f "$P/docs/LICENSE" ]'
ok "no CRLF in installed files" '! grep -rl $'"'"'\r'"'"' --include=*.py --include=*.sh --include=*.bas "$P"'
for c in pi-gpibterm hpib gpib-driver-rebuild hp3478a-cal hp3478a-log; do
  ok "command $c" '[ -x "$T/bin/'"$c"'" ]'
done
ok "the old 1.x programs and menu command are gone" '[ ! -e "$T/opt/hp3478a" ] && [ ! -e "$T/bin/hp3478a" ]'
ok "the old hp3478a folder became pi-gpibterm, backups kept" '[ ! -e "$T/home/hp3478a" ] && [ -f "$W/backups/calram_test.txt" ]'
ok "the old meter address moved to the module setting" 'grep -q "^HP3478A_ADDRESS=22" "$W/pi-gpibterm.conf"'
ok "home folder: menu, programs, backups, logs" '[ -x "$W/menu" ] && [ -f "$W/programs/README.txt" ] && [ -d "$W/logs" ]'

out="$("$T/bin/hpib" --sim -c SCAN 2>&1)"
ok "hpib --sim works" '[[ "$out" == *"Listeners found: 23"* ]]'
out="$(cd "$W" && "$T/bin/hpib" --sim -c 'LOAD "examples/3478a_read"' -c RUN 2>&1)"
ok "hpib finds a module example as examples/..." '[[ "$out" == *" 1  "*" V"* ]]'
out="$(cd "$W" && "$T/bin/hpib" --sim -c 'FILES examples' 2>&1)"
ok "FILES examples lists core and module examples" '[[ "$out" == *"bus_tour.bas"* && "$out" == *"3478a_calsave.bas"* ]]'
out="$("$T/bin/hp3478a-cal" decode "$SRC/dev/sample_calram.txt" 2>&1)"
ok "hp3478a-cal decode works" '[[ "$out" == *"all used entries valid"* ]]'

# the menu, through a real pseudo-terminal (as at the keyboard)
while read -r line; do
  echo "$line"
  case "$line" in PASS*) pass=$((pass+1)) ;; FAIL*|TIMEOUT*) fail=$((fail+1)) ;; esac
done < <(python3 "$SRC/dev/test_menu_pty.py" "$W/menu" "$W" 2>&1)

# update: run again over an existing install with an old copy of the programs in the folder
echo "old" > "$W/hpibterm.py"
bash "$SRC/install.sh" "${OPTS[@]}" >/dev/null 2>&1
ok "re-install keeps the user's settings" 'grep -q "^HP3478A_ADDRESS=21" "$W/pi-gpibterm.conf"'
ok "re-install moves an old program copy aside" '[ ! -f "$W/hpibterm.py" ] && ls "$W"/old-programs-*/hpibterm.py >/dev/null'

bash "$SRC/uninstall.sh" --prefix "$P" --bindir "$T/bin" >/dev/null
ok "uninstall removes programs and all commands" '[ ! -e "$P" ] && [ -z "$(ls -A "$T/bin")" ]'
ok "uninstall keeps ~/pi-gpibterm" '[ -f "$W/backups/calram_test.txt" ]'

echo "install tests: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
