#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
SYSTEMD_SRC="$REPO_ROOT/ops/deploy/systemd"
SYSTEMD_DST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
VELA_CFG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/vela"
VELA_ENV_PATH="$VELA_CFG_DIR/vela.env"

mkdir -p "$SYSTEMD_DST" "$VELA_CFG_DIR"

cp "$SYSTEMD_SRC"/vela-api.service "$SYSTEMD_DST"/
cp "$SYSTEMD_SRC"/vela-patrol.service "$SYSTEMD_DST"/
cp "$SYSTEMD_SRC"/vela-patrol.timer "$SYSTEMD_DST"/
cp "$SYSTEMD_SRC"/vela-night-cycle.service "$SYSTEMD_DST"/
cp "$SYSTEMD_SRC"/vela-night-cycle.timer "$SYSTEMD_DST"/

if [ ! -f "$VELA_ENV_PATH" ]; then
  cp "$SYSTEMD_SRC"/vela.env.example "$VELA_ENV_PATH"
fi

printf '%s\n' "Installed Vela user units into $SYSTEMD_DST"
printf '%s\n' "Created default environment file at $VELA_ENV_PATH"
printf '%s\n' "Next:"
printf '%s\n' "  systemctl --machine=knosence@.host --user daemon-reload"
printf '%s\n' "  systemctl --machine=knosence@.host --user enable --now vela-api.service vela-patrol.timer vela-night-cycle.timer"
