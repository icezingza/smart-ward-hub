#!/usr/bin/env bash
set -euo pipefail

: "${SW_MTLS_CERTFILE:?Set SW_MTLS_CERTFILE to the server certificate}"
: "${SW_MTLS_KEYFILE:?Set SW_MTLS_KEYFILE to the server private key}"
: "${SW_MTLS_CA_CERTS:?Set SW_MTLS_CA_CERTS to the trusted client CA bundle}"

exec uvicorn main:app \
  --host "${SW_BIND_HOST:-0.0.0.0}" \
  --port "${SW_PORT:-8443}" \
  --ssl-certfile "$SW_MTLS_CERTFILE" \
  --ssl-keyfile "$SW_MTLS_KEYFILE" \
  --ssl-ca-certs "$SW_MTLS_CA_CERTS" \
  --ssl-cert-reqs 2
