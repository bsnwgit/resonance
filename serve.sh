#!/usr/bin/env bash
# Static server for Resonance. Not an app, not a service —
# deliberately no systemd unit, so it needs no sudo.
#   ./serve.sh start | stop | status
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-9700}"

pid_on_port() { ss -ltnp 2>/dev/null | awk -v p=":$PORT\$" '$4 ~ p {print $NF}' \
                | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -1; }

case "${1:-status}" in
  start)
    if [ -n "$(pid_on_port)" ]; then echo "already listening on $PORT (pid $(pid_on_port))"; exit 0; fi
    cd "$DIR"
    # the venv carries faster-whisper; fall back to system python (static
    # serving still works, /stt just reports unavailable)
    PY="$DIR/stt-venv/bin/python"
    [ -x "$PY" ] || PY="$(command -v python3)"
    PORT="$PORT" setsid nohup "$PY" "$DIR/serve.py" \
      > "$DIR/server.log" 2>&1 < /dev/null &
    sleep 1
    echo "started on $PORT (pid $(pid_on_port))"
    ;;
  stop)
    p="$(pid_on_port)"
    # exact pid resolved from the port — never pattern-kill on a shared box
    if [ -z "$p" ]; then echo "nothing on $PORT"; else kill "$p" && echo "stopped $p"; fi
    ;;
  status)
    p="$(pid_on_port)"
    if [ -z "$p" ]; then echo "down"; else echo "up on $PORT (pid $p)"; fi
    ;;
  *) echo "usage: $0 start|stop|status"; exit 1;;
esac
