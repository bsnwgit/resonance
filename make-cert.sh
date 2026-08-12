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
HOSTIP="${1:-$(hostname -I | awk '{print $1}')}"

openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout "$DIR/key.pem" -out "$DIR/cert.pem" \
  -subj "/CN=$HOSTIP" \
  -addext "subjectAltName=IP:$HOSTIP,IP:127.0.0.1,DNS:localhost" \
  2>/dev/null

chmod 600 "$DIR/key.pem"
echo "wrote cert.pem / key.pem for $HOSTIP"
openssl x509 -in "$DIR/cert.pem" -noout -ext subjectAltName
