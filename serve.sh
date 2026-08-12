#!/usr/bin/env bash
# Static server for Resonance. Not an app, not a service —
# deliberately no systemd unit, so it needs no sudo.
#   ./serve.sh start | stop | status
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$DIR/server.pid"

# The display port is configurable from the admin page, so read it from the
# same place the server does. Environment still wins, for a one-off run.
cfg_port() {
  "$(command -v python3)" - "$DIR/app.json" <<'PY' 2>/dev/null || echo 9700
import json, sys
try:
    print(int(json.load(open(sys.argv[1]))["http_port"]))
except Exception:
    print(9700)
PY
}
# Remember whether the caller asked for a specific port. If they did it is
# passed through and the server shifts all three; if they did not, the server
# reads app.json itself, so the configured HTTPS and admin ports are honoured
# instead of being derived from this one.
PORT_EXPLICIT="${PORT:-}"
PORT="${PORT:-$(cfg_port)}"

pid_on_port() { ss -ltnp 2>/dev/null | awk -v p=":$PORT\$" '$4 ~ p {print $NF}' \
                | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -1; }

# A pid is only ours if it is alive AND running this directory's serve.py.
# Never pattern-kill: every pid here is resolved exactly, then verified.
is_ours() {
  [ -n "${1:-}" ] || return 1
  kill -0 "$1" 2>/dev/null || return 1
  ps -p "$1" -o args= 2>/dev/null | grep -q "$DIR/serve.py"
}

# Prefer the recorded pid: after a port change the running process is still on
# the OLD port, so looking it up by the configured port would miss it entirely.
running_pid() {
  local p=""
  [ -f "$PIDFILE" ] && p="$(cat "$PIDFILE" 2>/dev/null)"
  if is_ours "$p"; then echo "$p"; return; fi
  p="$(pid_on_port)"
  if is_ours "$p"; then echo "$p"; return; fi
  echo ""
}

case "${1:-status}" in
  start)
    p="$(running_pid)"
    if [ -n "$p" ]; then echo "already running (pid $p)"; exit 0; fi
    cd "$DIR"
    # the venv carries faster-whisper; fall back to system python (static
    # serving still works, /stt just reports unavailable)
    PY="$DIR/stt-venv/bin/python"
    [ -x "$PY" ] || PY="$(command -v python3)"
    if [ -n "$PORT_EXPLICIT" ]; then
      PORT="$PORT_EXPLICIT" setsid nohup "$PY" "$DIR/serve.py" \
        > "$DIR/server.log" 2>&1 < /dev/null &
    else
      setsid nohup "$PY" "$DIR/serve.py" \
        > "$DIR/server.log" 2>&1 < /dev/null &
    fi
    sleep 1
    p="$(pid_on_port)"
    if [ -n "$p" ]; then
      echo "$p" > "$PIDFILE"
      echo "started on $PORT (pid $p)"
    else
      echo "did not come up on $PORT — see $DIR/server.log"
      exit 1
    fi
    ;;
  stop)
    p="$(running_pid)"
    if [ -z "$p" ]; then
      echo "not running"
      rm -f "$PIDFILE"
    else
      kill "$p" && echo "stopped $p"
      rm -f "$PIDFILE"
    fi
    ;;
  status)
    p="$(running_pid)"
    if [ -z "$p" ]; then
      echo "down"
    else
      echo "up (pid $p) — listening on:"
      ss -ltnp 2>/dev/null | grep "pid=$p," | awk '{print "   " $4}'
    fi
    ;;
  *) echo "usage: $0 start|stop|status"; exit 1;;
esac
