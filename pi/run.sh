#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# run.sh - start one of the pi-GPIBTerm programs (used by the pi-gpibterm, hpib, ... commands)
# Part of pi-GPIBTerm v2.0.6
#
# Members of the 'gpib' group can use /dev/gpib0 directly (install.sh sets that up; it works
# after logging in again). Otherwise the program is started with sudo.
DIR="$(cd "$(dirname "$0")" && pwd)"
PROG="$1"
shift
if [ "$(id -u)" -ne 0 ] && [ -e /dev/gpib0 ] && [ ! -w /dev/gpib0 ]; then
    case " $* " in
        *" --sim "*|*" decode "*|*" --help "*|*" -h "*|*" --version "*) ;;   # no GPIB board needed
        *) [ "$PROG" = gpibterm_menu.py ] || exec sudo python3 "$DIR/$PROG" "$@" ;;
    esac
fi
exec python3 "$DIR/$PROG" "$@"
