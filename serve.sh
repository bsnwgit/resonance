#!/usr/bin/env bash
# Static server for Resonance. Not an app, not a service —
# deliberately no systemd unit, so it needs no sudo.
#   ./serve.sh start | stop | restart | status | watchdog | install-cron
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$DIR/server.pid"
# Written by stop, removed by start: the difference between "somebody turned it
# off" and "it died". The watchdog is the only reader — without this it would
# fight a deliberate stop, and revive the server mid-restart while the old
# process is still releasing its sockets.
DOWNFILE="$DIR/server.stopped"
WATCHLOG="$DIR/watchdog.log"

# The display port is configurable from the admin page, so read it from the
# same place the server does. Environment still wins, for a one-off run.
#
# THE ADMIN PORT, not the display's. This anchored on http_port, which was the
# built-in display listener — and that listener is gone: every network profile
# is its own listener now and none of them is special, so a deployment can
# legitimately have nothing on the old display port at all. When that happened
# this script reported "down" for a server that was running, and its stop did
# nothing. The admin port is the one this server always binds.
cfg_port() {
  "$(command -v python3)" - "$DIR/app.json" <<'PY' 2>/dev/null || echo 9700
import json, sys
try:
    print(int(json.load(open(sys.argv[1]))["admin_port"]))
except Exception:
    print(9702)
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
    rm -f "$DOWNFILE"
    cd "$DIR"
    # the venv carries faster-whisper; fall back to system python (static
    # serving still works, /stt just reports unavailable)
    PY="$DIR/stt-venv/bin/python"
    [ -x "$PY" ] || PY="$(command -v python3)"
    # Keep the previous run's log. It is the only record of why the server
    # stopped, and nothing supervises this process — by the time anyone
    # notices it is down, a truncating restart has already erased the reason.
    [ -s "$DIR/server.log" ] && mv -f "$DIR/server.log" "$DIR/server.log.1"
    if [ -n "$PORT_EXPLICIT" ]; then
      PORT="$PORT_EXPLICIT" setsid nohup "$PY" "$DIR/serve.py" \
        > "$DIR/server.log" 2>&1 < /dev/null &
    else
      setsid nohup "$PY" "$DIR/serve.py" \
        > "$DIR/server.log" 2>&1 < /dev/null &
    fi
    # give it a moment to bind, but do not declare failure on a slow start
    p=""
    for _ in $(seq 1 30); do
      sleep 0.2
      p="$(pid_on_port)"
      [ -n "$p" ] && break
    done
    if [ -n "$p" ]; then
      echo "$p" > "$PIDFILE"
      echo "started on $PORT (pid $p)"
    else
      echo "did not come up on $PORT — see $DIR/server.log"
      exit 1
    fi
    ;;
  stop)
    : > "$DOWNFILE"
    p="$(running_pid)"
    if [ -z "$p" ]; then
      echo "not running"
      rm -f "$PIDFILE"
    else
      kill "$p"
      # Wait for it to actually go. Returning as soon as the signal is sent
      # means `stop && start` races the old process, which is still holding
      # the listening sockets — the restart then dies on "address already in
      # use" and leaves nothing running at all.
      for _ in $(seq 1 50); do
        kill -0 "$p" 2>/dev/null || break
        sleep 0.1
      done
      if kill -0 "$p" 2>/dev/null; then
        echo "pid $p did not exit after 5s — still running"
        exit 1
      fi
      echo "stopped $p"
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
  restart)
    # There was no restart verb, and asking for one printed the usage and
    # exited 1 — which looks close enough to "done" that a server can go on
    # running yesterday's code for hours while somebody wonders why a new
    # setting will not save. stop is idempotent, so this is safe from down.
    "$0" stop
    "$0" start
    ;;
  watchdog)
    # Recovery, for cron. Silent when there is nothing to do, so a two-minute
    # schedule does not mail anybody every two minutes. It starts the server
    # only when it is down and nobody asked for it to be down — a crash, an
    # OOM kill, a reboot. Not a supervisor: it cannot see a process wedge, only
    # one that is gone.
    [ -f "$DOWNFILE" ] && exit 0
    [ -n "$(running_pid)" ] && exit 0
    printf '%s  down — starting\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$WATCHLOG"
    "$0" start >> "$WATCHLOG" 2>&1
    ;;
  install-cron)
    # Boot start and crash recovery without root, which is the whole reason
    # there is no unit file. @reboot goes through watchdog rather than start so
    # that a server deliberately stopped before a reboot stays stopped after it.
    have="$(crontab -l 2>/dev/null)"
    case "$have" in
      *"$DIR/serve.sh watchdog"*)
        echo "already installed"; exit 0;;
    esac
    { [ -n "$have" ] && printf '%s\n' "$have"
      echo "@reboot $DIR/serve.sh watchdog"
      echo "*/2 * * * * $DIR/serve.sh watchdog"
    } | crontab -
    echo "installed: @reboot and every 2 minutes"
    ;;
  *) echo "usage: $0 start|stop|restart|status|watchdog|install-cron"; exit 1;;
esac
