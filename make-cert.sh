#!/usr/bin/env bash
# Self-signed cert for the HTTPS listener, so getUserMedia will run.
# Two rules that both cause a hard failure if broken:
#   - the SAN must carry the exact IP/host you type in the address bar; a
#     cert with only a CN is rejected outright by modern browsers
#   - validity must be <= 398 days. Chrome refuses anything longer with
#     ERR_CERT_VALIDITY_TOO_LONG, which can present as a blank page rather
#     than the usual click-through warning.
set -eu
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${1:-$(hostname -I | awk '{print $1}')}"

# openssl types every SAN entry itself: an IP: entry that isn't a literal
# address is rejected outright, so a hostname argument has to go in as DNS:.
# 127.0.0.1 and localhost stay in either way, minus a duplicate of the
# argument itself.
SAN=""
if [[ "$HOST" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  [ "$HOST" = "127.0.0.1" ] || SAN="IP:$HOST,"
else
  [ "$HOST" = "localhost" ] || SAN="DNS:$HOST,"
fi
SAN="${SAN}IP:127.0.0.1,DNS:localhost"

# Keep openssl quiet when it works (it chatters key-generation dots at
# stderr), but never swallow the reason when it doesn't -- a discarded
# stderr here leaves the caller with no cert and no explanation.
if ! err="$(openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout "$DIR/key.pem" -out "$DIR/cert.pem" \
  -subj "/CN=$HOST" \
  -addext "subjectAltName=$SAN" \
  2>&1 >/dev/null)"; then
  echo "make-cert.sh: openssl failed to generate a cert for '$HOST'" >&2
  printf '%s\n' "$err" >&2
  exit 1
fi

chmod 600 "$DIR/key.pem"
echo "wrote cert.pem / key.pem for $HOST"
openssl x509 -in "$DIR/cert.pem" -noout -ext subjectAltName
